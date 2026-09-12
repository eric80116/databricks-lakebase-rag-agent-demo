"""Sentiva agent — served by MLflow AgentServer (Databricks' recommended agent serving).

Registers @invoke / @stream handlers with the AgentServer (see app.py). The agent body is
a LangGraph create_react_agent: `search_knowledge_base` retrieves from Lakebase Search; the
LLM goes through OUR Unity AI Gateway (gateway_chat.ChatDatabricks). Memory is Lakebase;
retrieval sources + per-step timings ride in custom_outputs. AgentServer provides the
FastAPI endpoints (/responses, /invocations), streaming, and MLflow tracing.
"""
import logging
import threading
import time
import uuid

import mlflow
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    to_chat_completions_input,
)

import gateway_chat
import memory
import retriever
from agent_utils import get_session_id, process_agent_astream_events

log = logging.getLogger("sentiva-agent")
mlflow.langchain.autolog()

SYSTEM_PROMPT = (
    "You are the support assistant for Sentiva, a consumer digital-safety company "
    "(products: Sentiva Shield, Alert, Family, ID, Scan). ALWAYS call the "
    "search_knowledge_base tool before answering, and answer using ONLY its results. "
    "Reply in the SAME language as the user's question. If the results don't contain the "
    "answer, say you don't have that information. Be concise and friendly. Do not invent "
    "prices, features, or facts."
)
_ROLE_MAP = {"human": "user", "user": "user", "ai": "assistant", "assistant": "assistant"}

# Per-request capture: the tool runs off-thread, so pass a request id via RunnableConfig
# and let the tool record sources/timing into this registry keyed by that id.
_REG = {}
_LOCK = threading.Lock()
_RID = "sentiva_rid"


@tool
def search_knowledge_base(query: str, config: RunnableConfig = None) -> str:
    """Search the Sentiva product knowledge base (multilingual: EN/JA/FR/DE) and return
    the most relevant passages. Always call this before answering a product question."""
    t = time.perf_counter()
    try:
        with mlflow.start_span(name="retrieval"):
            rows = retriever.retrieve(query)
    except Exception:
        rows = retriever.retrieve(query)
    dt = (time.perf_counter() - t) * 1000
    rid = ((config or {}).get("configurable") or {}).get(_RID)
    if rid:
        with _LOCK:
            e = _REG.get(rid)
            if e is not None:
                seen = {s.get("source_uri") for s in e["sources"]}
                for s in retriever.to_sources(rows):
                    if s.get("source_uri") not in seen:
                        e["sources"].append(s)
                        seen.add(s.get("source_uri"))
                e["retr_ms"] += dt
    return retriever.context_block(rows)


_GRAPH = None


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = create_react_agent(
            gateway_chat.build_llm(max_tokens=1024),
            tools=[search_knowledge_base],
            prompt=SYSTEM_PROMPT,
        )
    return _GRAPH


def _messages(request: ResponsesAgentRequest, session_id: str):
    """Lakebase memory history + the current request input, as chat-completions messages."""
    msgs = [
        {"role": _ROLE_MAP.get(h.get("role"), "user"), "content": (h.get("content") or "").strip()}
        for h in memory.load_history(session_id)
        if (h.get("content") or "").strip()
    ]
    msgs += to_chat_completions_input([i.model_dump() for i in request.input])
    return msgs


def _last_user_text(request: ResponsesAgentRequest) -> str:
    for it in reversed([i.model_dump() for i in request.input]):
        if it.get("role") == "user":
            c = it.get("content")
            if isinstance(c, list):
                return "".join(p.get("text", "") for p in c if isinstance(p, dict)).strip()
            return (c or "").strip() if isinstance(c, str) else str(c or "")
    return ""


@stream()
async def stream_handler(request: ResponsesAgentRequest):
    session_id = get_session_id(request) or "default"
    if session_id:
        try:
            mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
        except Exception:
            pass
    rid = uuid.uuid4().hex
    with _LOCK:
        _REG[rid] = {"sources": [], "retr_ms": 0.0}
    t0 = time.perf_counter()
    user_text = _last_user_text(request)
    answer_parts = []
    try:
        async for ev in process_agent_astream_events(
            _graph().astream(
                input={"messages": _messages(request, session_id)},
                config={"configurable": {_RID: rid}},
                stream_mode=["updates", "messages"],
            )
        ):
            delta = getattr(ev, "delta", None)
            if delta:
                answer_parts.append(delta)
            yield ev

        total_ms = (time.perf_counter() - t0) * 1000
        with _LOCK:
            entry = _REG.get(rid, {})
        sources = entry.get("sources", [])
        retr_ms = entry.get("retr_ms", 0.0)
        answer_text = "".join(answer_parts)
        try:
            memory.save_message(session_id, "human", user_text)
            memory.save_message(session_id, "ai", answer_text)
        except Exception:
            pass
        timings = {
            "retrieval_ms": round(retr_ms, 1),
            "llm_ms": round(max(total_ms - retr_ms, 0.0), 1),
            "total_ms": round(total_ms, 1),
        }
        # final event carrying sources + timings for the UI (custom_outputs is a
        # top-level field on ResponsesAgentStreamEvent)
        yield ResponsesAgentStreamEvent(
            type="response.custom_outputs",
            custom_outputs={"sources": sources, "timings": timings},
        )
    finally:
        with _LOCK:
            _REG.pop(rid, None)


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    outputs = []
    custom = {}
    async for ev in stream_handler(request):
        if getattr(ev, "type", "") == "response.output_item.done":
            outputs.append(ev.item)
        elif getattr(ev, "custom_outputs", None):
            custom = ev.custom_outputs
    return ResponsesAgentResponse(output=outputs, custom_outputs=custom)
