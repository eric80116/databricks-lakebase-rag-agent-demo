"""Sentiva RAG agent API (App A) — FastAPI, deployed as a Databricks App.

Endpoints:
  GET  /api/health      -> {"status":"ok"}
  POST /api/chat        -> {answer, sources[], timings{}, trace_id}
  POST /api/chat/stream -> Server-Sent Events: {type:token,text} ... {type:done,sources,timings,trace_id}
"""
import os
import json as _json
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

from models import ChatRequest, ChatResponse, Timings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sentiva-agent")

app = FastAPI(title="Sentiva RAG Agent API")

# --- MLflow tracing (best-effort) -------------------------------------------
_mlflow = None
try:
    import mlflow
    mlflow.set_tracking_uri("databricks")
    _exp = os.getenv("MLFLOW_EXPERIMENT", "/Shared/sentiva-rag-uc")
    # MLflow 3 GenAI tracing stored in OpenTelemetry format IN Unity Catalog
    # (writes via the Databricks API — reachable from the app; the artifact
    # storage host is NOT). Auto-creates <prefix>_otel_spans/logs/metrics tables.
    try:
        from mlflow.entities.trace_location import UnityCatalog
        mlflow.set_experiment(
            experiment_name=_exp,
            trace_location=UnityCatalog(
                catalog_name=os.getenv("TRACE_CATALOG", "dbx_agent_lakebase"),
                schema_name=os.getenv("TRACE_SCHEMA", "rag"),
                table_prefix=os.getenv("TRACE_TABLE_PREFIX", "sentiva"),
            ),
        )
        log.info("MLflow tracing -> Unity Catalog trace location (%s)", _exp)
    except Exception as e:
        log.warning("UC trace_location bind failed (%s); using plain experiment", e)
        mlflow.set_experiment(_exp)
    try:
        mlflow.langchain.autolog()  # traces the LangGraph react agent (nodes / ChatDatabricks / tool)
    except Exception as e:
        log.warning("langchain autolog unavailable: %s", e)
    _mlflow = mlflow
    log.info("MLflow tracing enabled")
except Exception as e:
    log.warning("MLflow unavailable, tracing disabled: %s", e)


@app.get("/")
def root():
    return {"status": "ok", "service": "sentiva-agent-api", "endpoints": ["/api/health", "/api/chat"]}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Import here so /api/health stays up even if deps/DB aren't ready.
    import agent

    trace_id = ""
    try:
        if _mlflow is not None:
            with _mlflow.start_span(name="chat") as span:
                try:
                    span.set_inputs({"session_id": req.session_id, "message": req.message})
                except Exception:
                    pass
                answer, sources, timings = agent.answer(req.session_id, req.message)
                try:
                    trace_id = getattr(span, "trace_id", "") or getattr(span, "request_id", "")
                except Exception:
                    trace_id = ""
        else:
            answer, sources, timings = agent.answer(req.session_id, req.message)
    except Exception as e:
        log.exception("chat failed")
        return JSONResponse(status_code=500, content={"error": str(e)})

    if not trace_id and _mlflow is not None:
        try:
            trace_id = _mlflow.get_last_active_trace_id() or ""
        except Exception:
            trace_id = ""

    return ChatResponse(
        answer=answer,
        sources=sources,
        timings=Timings(**timings),
        trace_id=trace_id or "",
    )


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    """Stream the answer token-by-token as Server-Sent Events (first token in ~1-2s)."""
    import agent

    def gen():
        try:
            for ev in agent.stream_answer(req.session_id, req.message):
                yield f"data: {_json.dumps(ev)}\n\n"
        except Exception as e:  # surface as a final SSE error event
            log.exception("chat stream failed")
            yield f"data: {_json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
