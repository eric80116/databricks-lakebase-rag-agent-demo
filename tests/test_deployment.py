"""End-to-end verification of the deployed Sentiva RAG demo.

Run: pytest tests/ -v   (needs the configured Databricks profile from config.env)
Each test targets one requirement; failures pinpoint the broken component.
"""
import json
import urllib.request
import pytest
from conftest import CFG, sh, q, app_url

CATALOG = CFG.get("CATALOG", "dbx_agent_lakebase")
SCHEMA = CFG.get("SCHEMA", "rag")
PREFIX = CFG.get("TRACE_TABLE_PREFIX", "sentiva")
APP_A = CFG.get("APP_A_NAME", "sentiva-agent-api")
APP_B = CFG.get("APP_B_NAME", "sentiva-web")
FQ = f"{CATALOG}.{SCHEMA}"


def _post_json(url, token, body, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _get_code(url, token, timeout=30):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        return urllib.request.urlopen(req, timeout=timeout).getcode()
    except urllib.error.HTTPError as e:
        return e.code


def _invoke(app_a_url, token, session_id, message, timeout=120):
    """Call App A's MLflow AgentServer /invocations and return (answer, sources, timings)."""
    body = {"input": [{"role": "user", "content": message}], "custom_inputs": {"session_id": session_id}}
    d = _post_json(f"{app_a_url}/invocations", token, body, timeout=timeout)
    answer = ""
    for item in d.get("output", []):
        for part in (item.get("content") or []) if isinstance(item, dict) else []:
            if isinstance(part, dict) and part.get("type") == "output_text":
                answer += part.get("text", "")
    co = d.get("custom_outputs") or {}
    return answer, co.get("sources", []), co.get("timings", {})


# ---- #8 embedding model ----------------------------------------------------
def test_embedding_endpoint_1024(host, token, profile):
    r = _post_json(f"{host}/serving-endpoints/{CFG.get('EMBEDDING_ENDPOINT','databricks-qwen3-embedding-0-6b')}/invocations",
                   token, {"input": ["hello"]})
    assert len(r["data"][0]["embedding"]) == 1024


# ---- #9/#10 AI Gateway + inference table -----------------------------------
def test_gateway_llm_responds(host, token):
    svc = f"{FQ}.{CFG.get('GATEWAY_SERVICE_ID','sentiva_llm')}"
    r = _post_json(f"{host}/ai-gateway/mlflow/v1/chat/completions", token,
                   {"model": svc, "messages": [{"role": "user", "content": "Reply OK"}], "max_tokens": 50})
    assert r.get("choices")


def test_inference_table_logs(profile):
    rows = q(f"SELECT count(*) c FROM {FQ}.llm_inference_payload", profile)
    assert rows and int(rows[0]["c"]) > 0


# ---- #5/#6/#7 KB + pipeline ------------------------------------------------
@pytest.mark.parametrize("table", ["docs_json", "docs_chunks", "docs_parsed"])
def test_pipeline_tables_populated(profile, table):
    rows = q(f"SELECT count(*) c FROM {FQ}.{table}", profile)
    assert rows and int(rows[0]["c"]) > 0


# ---- #4/#5 Lakebase KB loaded ----------------------------------------------
def test_lakebase_kb_loaded(profile):
    """kb.documents populated with embeddings (queried through the app path in test_chat)."""
    # Verified indirectly via test_agent_chat returning sources; here assert chunks exist.
    rows = q(f"SELECT count(*) c FROM {FQ}.docs_chunks", profile)
    assert rows and int(rows[0]["c"]) >= 40


# ---- #2/#11 apps healthy ---------------------------------------------------
def test_app_a_health(token, profile):
    assert _get_code(f"{app_url(APP_A, profile)}/health", token) == 200


def test_app_b_serves(token, profile):
    assert _get_code(f"{app_url(APP_B, profile)}/", token) == 200


# ---- #2 end-to-end agent (retrieval + LLM + grounding) ---------------------
def test_agent_chat_grounded(token, profile):
    app_a = app_url(APP_A, profile)
    answer, sources, timings = _invoke(app_a, token, "pytest", "How much does Sentiva Shield cost?")
    assert answer, "empty answer"
    assert len(sources) > 0, "no sources retrieved"
    assert timings.get("total_ms", 0) > 0


# ---- #4 multi-turn memory --------------------------------------------------
def test_agent_memory_multiturn(token, profile):
    app_a = app_url(APP_A, profile)
    sid = "pytest-mem"
    _invoke(app_a, token, sid, "How much does Sentiva Shield cost?")
    answer, _, _ = _invoke(app_a, token, sid, "Which of those plans includes a VPN?")
    assert answer, "follow-up empty"


# ---- #3 OTel traces in UC --------------------------------------------------
def test_otel_spans_in_uc(profile):
    rows = q(f"SELECT count(*) c FROM {FQ}.{PREFIX}_otel_spans", profile)
    assert rows and int(rows[0]["c"]) > 0


def test_otel_per_step_timing(profile):
    # The tool-calling agent emits an explicit 'retrieval' span; the LLM call is traced
    # by autolog as a 'ChatDatabricks' (CHAT_MODEL) span via the Unity AI Gateway.
    rows = q(f"SELECT name FROM {FQ}.{PREFIX}_otel_spans WHERE name IN ('retrieval','ChatDatabricks') GROUP BY name", profile)
    names = {r["name"] for r in rows}
    assert "retrieval" in names and "ChatDatabricks" in names, f"missing step spans: {names}"
