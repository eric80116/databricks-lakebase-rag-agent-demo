"""Call the Unity AI Gateway model-service (OpenAI-compatible chat route).

Routes through OUR gateway so usage tracking + inference-table payload logging
apply (requirements #9/#10). Handles gemini reasoning-model responses where
`content` is a list of parts [{"type":"text","text":...,"thoughtSignature":...}].
"""
import os
import requests
from databricks.sdk.core import Config

_cfg = Config()  # SP creds auto-injected in the Databricks App runtime

GATEWAY_SERVICE = os.getenv("GATEWAY_SERVICE", "dbx_agent_lakebase.rag.sentiva_llm")
_URL = f"{_cfg.host.rstrip('/')}/ai-gateway/mlflow/v1/chat/completions"


def _auth_headers() -> dict:
    h = {"Content-Type": "application/json"}
    try:
        h.update(_cfg.authenticate())  # {"Authorization": "Bearer ..."}
    except Exception:
        tok = os.getenv("DATABRICKS_TOKEN")
        if tok:
            h["Authorization"] = f"Bearer {tok}"
    return h


def _extract_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content
                 if isinstance(p, dict) and p.get("type") == "text"]
        return "".join(parts).strip()
    return str(content)


def chat(messages, max_tokens: int = 1024, temperature: float = 0.2, timeout: int = 60):
    """Return (answer_text, usage_dict). `messages` is OpenAI-style list."""
    body = {
        "model": GATEWAY_SERVICE,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    resp = requests.post(_URL, headers=_auth_headers(), json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    msg = (data.get("choices") or [{}])[0].get("message", {})
    return _extract_text(msg), data.get("usage", {})
