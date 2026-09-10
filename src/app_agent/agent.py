"""Sentiva RAG agent — LangChain chain: retrieve (Lakebase) -> prompt -> gateway LLM -> memory.

Uses LangChain Runnables so mlflow.langchain.autolog() traces the chain; adds explicit
mlflow spans around retrieval and the LLM call to guarantee per-step timing (#3).
"""
import time

try:
    import mlflow
except Exception:  # tracing is best-effort
    mlflow = None

from langchain_core.runnables import RunnableLambda

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


# LangChain Runnable wrapping the gateway LLM (traced by autolog).
_llm_runnable = RunnableLambda(lambda msgs: gateway_llm.chat(msgs, max_tokens=1024))


def answer(session_id: str, message: str):
    t0 = time.perf_counter()

    with _span("retrieval"):
        rows = retriever.retrieve(message)
        context = retriever.context_block(rows)
        sources = retriever.to_sources(rows)
    t_retr = time.perf_counter()

    history = memory.load_history(session_id)
    msgs = _build_messages(message, context, history)

    with _span("llm"):
        answer_text, usage = _llm_runnable.invoke(msgs)
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
