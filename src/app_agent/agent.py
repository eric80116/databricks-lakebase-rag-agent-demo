"""Sentiva agent — MLflow ResponsesAgent interface over a LangGraph create_react_agent.

A tool-calling agent: the LLM (routed through OUR Unity AI Gateway via ChatDatabricks)
decides when to call `search_knowledge_base` (Lakebase Search), reads the results, and
answers. Wrapped in the MLflow `ResponsesAgent` interface (Databricks' recommended way to
author an agent on Databricks Apps). Swapping the model is a gateway-config change, so the
agent is model-agnostic — see gateway_chat.py. (Reasoning models like Gemini 2.5/3.x can't
tool-call via the gateway's unified surface; use deepseek / Claude / Llama.)

Tracing (#3): mlflow.langchain.autolog() (enabled in app.py) captures the LangGraph spans
(agent / ChatDatabricks / tool); the tool adds an explicit `retrieval` span. Sources and
per-step timings are captured per request via ContextVars and returned in custom_outputs.
"""
import time
import uuid
import threading

try:
    import mlflow
except Exception:  # tracing is best-effort
    mlflow = None

from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

import retriever
import memory
import gateway_chat

SYSTEM_PROMPT = (
    "You are the support assistant for Sentiva, a consumer digital-safety company "
    "(products: Sentiva Shield, Alert, Family, ID, Scan). ALWAYS call the "
    "search_knowledge_base tool before answering, and answer using ONLY its results. "
    "Reply in the SAME language as the user's question. If the results don't contain the "
    "answer, say you don't have that information. Be concise and friendly. Do not invent "
    "prices, features, or facts."
)

_ROLE_MAP = {"human": "user", "user": "user", "ai": "assistant", "assistant": "assistant"}

# Per-request capture. LangGraph runs the tool on a different thread, so neither
# ContextVar nor threading.local reaches back. Instead we pass a request id through the
# graph's RunnableConfig (configurable), and the tool records sources/timing into this
# registry keyed by that id. A lock makes it safe across concurrent requests.
_REGISTRY = {}
_REG_LOCK = threading.Lock()
_REQ_ID_KEY = "sentiva_req_id"


@tool
def search_knowledge_base(query: str, config: RunnableConfig = None) -> str:
    """Search the Sentiva product knowledge base (multilingual: EN/JA/FR/DE) and return
    the most relevant passages. Always call this before answering a product question."""
    t = time.perf_counter()
    if mlflow is not None:
        try:
            with mlflow.start_span(name="retrieval"):
                rows = retriever.retrieve(query)
        except Exception:
            rows = retriever.retrieve(query)
    else:
        rows = retriever.retrieve(query)
    dt = (time.perf_counter() - t) * 1000

    # record sources/timing into the per-request registry (keyed by the id passed via
    # RunnableConfig), deduped across possibly-multiple tool calls
    rid = ((config or {}).get("configurable") or {}).get(_REQ_ID_KEY)
    if rid is not None:
        with _REG_LOCK:
            entry = _REGISTRY.get(rid)
            if entry is not None:
                seen = {s.get("source_uri") for s in entry["sources"]}
                for s in retriever.to_sources(rows):
                    if s.get("source_uri") not in seen:
                        entry["sources"].append(s)
                        seen.add(s.get("source_uri"))
                entry["retr_ms"] += dt
    return retriever.context_block(rows)


_GRAPH = None


def _graph():
    """Build the react agent once (lazy — needs the app runtime's SP creds)."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = create_react_agent(
            gateway_chat.build_llm(max_tokens=1024),
            tools=[search_knowledge_base],
            prompt=SYSTEM_PROMPT,
        )
    return _GRAPH


def _msg_text(msg) -> str:
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
    if isinstance(content, list):  # some models return content parts
        return "".join(
            (p.get("text", "") if isinstance(p, dict) else str(p)) for p in content
        ).strip()
    return (content or "").strip() if isinstance(content, str) else str(content or "")


def _run_agent(session_id: str, message: str):
    """Run the react agent for one turn. Returns (answer_text, sources, timings)."""
    rid = uuid.uuid4().hex
    with _REG_LOCK:
        _REGISTRY[rid] = {"sources": [], "retr_ms": 0.0}
    t0 = time.perf_counter()

    history = memory.load_history(session_id)
    msgs = [
        {"role": _ROLE_MAP.get(h.get("role"), "user"), "content": (h.get("content") or "").strip()}
        for h in history
        if (h.get("content") or "").strip()
    ]
    msgs.append({"role": "user", "content": message})

    try:
        result = _graph().invoke(
            {"messages": msgs},
            config={"configurable": {_REQ_ID_KEY: rid}},
        )
        answer_text = _msg_text(result["messages"][-1])
        total_ms = (time.perf_counter() - t0) * 1000
        with _REG_LOCK:
            entry = _REGISTRY.get(rid, {})
        retr_ms = entry.get("retr_ms", 0.0)
        sources = entry.get("sources", [])
    finally:
        with _REG_LOCK:
            _REGISTRY.pop(rid, None)

    # persist turn (best-effort)
    try:
        memory.save_message(session_id, "human", message)
        memory.save_message(session_id, "ai", answer_text)
    except Exception:
        pass

    timings = {
        "retrieval_ms": round(retr_ms, 1),
        "llm_ms": round(max(total_ms - retr_ms, 0.0), 1),
        "total_ms": round(total_ms, 1),
    }
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
    """Tool-calling RAG agent served through the MLflow ResponsesAgent interface.

    `predict` takes a ResponsesAgentRequest (current turn in `input`, conversation key in
    `custom_inputs.session_id`) and returns the answer as a text output item; retrieval
    sources and per-step timings ride in `custom_outputs`.
    """

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        ci = request.custom_inputs or {}
        session_id = ci.get("session_id", "default")
        message = _last_user_text(request.input)
        answer_text, sources, timings = _run_agent(session_id, message)
        item = self.create_text_output_item(text=answer_text, id=str(uuid.uuid4()))
        return ResponsesAgentResponse(
            output=[item],
            custom_outputs={"sources": sources, "timings": timings},
        )


def _last_user_text(items) -> str:
    for it in reversed(list(items or [])):
        role = getattr(it, "role", None)
        content = getattr(it, "content", None)
        if role is None and isinstance(it, dict):
            role, content = it.get("role"), it.get("content")
        if role == "user":
            if isinstance(content, list):
                return "".join(
                    (p.get("text", "") if isinstance(p, dict) else str(p)) for p in content
                ).strip()
            return content.strip() if isinstance(content, str) else str(content or "")
    return ""


AGENT = SentivaAgent()


def _output_text(resp: ResponsesAgentResponse) -> str:
    for it in (resp.output or []):
        d = it if isinstance(it, dict) else (it.model_dump() if hasattr(it, "model_dump") else {})
        for part in (d.get("content") or []):
            if isinstance(part, dict) and part.get("type") == "output_text":
                return part.get("text", "")
    return ""


def answer(session_id: str, message: str):
    """Back-compat helper for app.py — runs the turn through the ResponsesAgent interface
    and unpacks (answer_text, sources, timings)."""
    req = ResponsesAgentRequest(
        input=[{"role": "user", "content": message}],
        custom_inputs={"session_id": session_id},
    )
    resp = AGENT.predict(req)
    co = resp.custom_outputs or {}
    return _output_text(resp), co.get("sources", []), co.get("timings", {})
