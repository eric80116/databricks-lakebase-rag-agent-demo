"""Sentiva RAG agent — MLflow ResponsesAgent interface over an always-retrieve RAG flow.

Adopts the official `ResponsesAgent` interface (Databricks' recommended way to author
an agent deployed on Databricks Apps). The body is a deterministic RAG chain:
retrieve (Lakebase Search) -> prompt -> Unity AI Gateway LLM -> memory. It is not a
tool-calling agent — for this single-domain product-Q&A use case, always retrieving is
more reliable than letting the model decide. Explicit MLflow spans around retrieval and
the LLM call provide the per-step timing captured in the UC OTel trace tables (#3).
"""
import time
import uuid

try:
    import mlflow
except Exception:  # tracing is best-effort
    mlflow = None

from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

import retriever
import memory
import gateway_llm

SYSTEM_PROMPT = (
    "You are the support assistant for Sentiva, a consumer digital-safety company "
    "(products: Sentiva Shield, Alert, Family, ID, Scan). Answer the user's question "
    "using ONLY the provided context. Reply in the SAME language as the user's question. "
    "If the context does not contain the answer, say you don't have that information. "
    "Be concise and friendly. Do not invent prices, features, or facts not in the context."
)


_ROLE_MAP = {"human": "user", "user": "user", "ai": "assistant", "assistant": "assistant"}


def _build_messages(question: str, context: str, history: list) -> list:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    # Map stored memory roles (LangChain 'human'/'ai') to OpenAI roles ('user'/'assistant').
    # Invalid roles make the gateway reject the request (400). Skip empty content.
    for h in history:
        content = (h.get("content") or "").strip()
        if not content:
            continue
        msgs.append({"role": _ROLE_MAP.get(h.get("role"), "user"), "content": content})
    user = f"Context:\n{context}\n\nQuestion: {question}"
    msgs.append({"role": "user", "content": user})
    return msgs


def _span(name):
    """mlflow span context manager, or a no-op if mlflow unavailable."""
    if mlflow is not None:
        try:
            return mlflow.start_span(name=name)
        except Exception:
            pass
    from contextlib import nullcontext
    return nullcontext()


def _last_user_text(items) -> str:
    """Extract the latest user message text from ResponsesAgent input items."""
    for it in reversed(list(items or [])):
        role = getattr(it, "role", None)
        content = getattr(it, "content", None)
        if role is None and isinstance(it, dict):
            role, content = it.get("role"), it.get("content")
        if role == "user":
            if isinstance(content, list):  # content parts [{type,text}, ...]
                return "".join(
                    (p.get("text", "") if isinstance(p, dict) else str(p)) for p in content
                ).strip()
            return content.strip() if isinstance(content, str) else str(content or "")
    return ""


def _run_rag(session_id: str, message: str):
    """The RAG body: retrieve -> prompt -> gateway LLM -> persist memory. Returns
    (answer_text, sources, timings). Emits 'retrieval' and 'llm' spans for #3."""
    t0 = time.perf_counter()

    with _span("retrieval"):
        rows = retriever.retrieve(message)
        context = retriever.context_block(rows)
        sources = retriever.to_sources(rows)
    t_retr = time.perf_counter()

    history = memory.load_history(session_id)
    msgs = _build_messages(message, context, history)

    with _span("llm"):
        answer_text, usage = gateway_llm.chat(msgs, max_tokens=1024)
        if mlflow is not None and usage:
            try:
                mlflow.update_current_trace(tags={"total_tokens": str(usage.get("total_tokens", ""))})
            except Exception:
                pass
    t_llm = time.perf_counter()

    # persist turn (best-effort)
    try:
        memory.save_message(session_id, "human", message)
        memory.save_message(session_id, "ai", answer_text)
    except Exception:
        pass

    timings = {
        "retrieval_ms": round((t_retr - t0) * 1000, 1),
        "llm_ms": round((t_llm - t_retr) * 1000, 1),
        "total_ms": round((t_llm - t0) * 1000, 1),
    }
    # Persist per-step metrics as trace tags (queryable metadata; survives even if
    # the detailed span artifact can't upload from the app's network).
    if mlflow is not None:
        try:
            mlflow.update_current_trace(tags={
                "retrieval_ms": str(timings["retrieval_ms"]),
                "llm_ms": str(timings["llm_ms"]),
                "total_ms": str(timings["total_ms"]),
                "n_sources": str(len(sources)),
                "products": ",".join(sorted({s.get("product", "") for s in sources})),
                "langs": ",".join(sorted({s.get("lang", "") for s in sources})),
            })
        except Exception:
            pass
    return answer_text, sources, timings


class SentivaAgent(ResponsesAgent):
    """Always-retrieve RAG served through the MLflow ResponsesAgent interface.

    `predict` takes a ResponsesAgentRequest (the current turn in `input`, the
    conversation key in `custom_inputs.session_id`) and returns the answer as a text
    output item; retrieval sources and per-step timings ride in `custom_outputs`.
    """

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        ci = request.custom_inputs or {}
        session_id = ci.get("session_id", "default")
        message = _last_user_text(request.input)
        answer_text, sources, timings = _run_rag(session_id, message)
        item = self.create_text_output_item(text=answer_text, id=str(uuid.uuid4()))
        return ResponsesAgentResponse(
            output=[item],
            custom_outputs={"sources": sources, "timings": timings},
        )


AGENT = SentivaAgent()


def _output_text(resp: ResponsesAgentResponse) -> str:
    # ResponsesAgentResponse validates output items into OutputItem models, so
    # normalize via model_dump() (dict passthrough if it's already a dict).
    for it in (resp.output or []):
        d = it if isinstance(it, dict) else (it.model_dump() if hasattr(it, "model_dump") else {})
        for part in (d.get("content") or []):
            if isinstance(part, dict) and part.get("type") == "output_text":
                return part.get("text", "")
    return ""


def answer(session_id: str, message: str):
    """Back-compat helper for app.py — runs the turn through the ResponsesAgent
    interface and unpacks (answer_text, sources, timings)."""
    req = ResponsesAgentRequest(
        input=[{"role": "user", "content": message}],
        custom_inputs={"session_id": session_id},
    )
    resp = AGENT.predict(req)
    co = resp.custom_outputs or {}
    return _output_text(resp), co.get("sources", []), co.get("timings", {})
