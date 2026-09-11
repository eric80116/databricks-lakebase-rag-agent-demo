"""LangChain chat model that routes through OUR Unity AI Gateway model-service.

Uses databricks_langchain.ChatDatabricks (the Databricks-recommended client) with
`use_ai_gateway=True` and `model=<gateway model-service>`, so the agent's LLM calls flow
through the Unity AI Gateway (usage tracking + inference-table payload logging, #9/#10).
Auth is handled by the injected WorkspaceClient (app SP creds, auto-refreshed).

The underlying foundation model is chosen at the GATEWAY level (the model-service's
routing destination, driven by LLM_ENDPOINT), so swapping models is a gateway-config
change — the agent code is model-agnostic. Use a model whose tool-call format round-trips
through the gateway's unified surface (deepseek / Llama / Mistral); Gemini 2.5/3.x
reasoning models drop their thought_signature on tool calls and can't tool-call here.
"""
import os
from databricks.sdk import WorkspaceClient
from databricks_langchain import ChatDatabricks

# The gateway MODEL-SERVICE fully-qualified name (catalog.schema.service) — ChatDatabricks
# takes `model=`, not `endpoint=`.
GATEWAY_SERVICE = os.getenv("GATEWAY_SERVICE", "dbx_agent_lakebase.rag.sentiva_llm")


def build_llm(max_tokens: int = 1024):
    # `temperature` is deliberately NOT sent: several models (e.g. Claude Opus, GPT-5.x)
    # reject it, and omitting it maximizes model-swap compatibility. Set TEMPERATURE in
    # the env to opt back in for a model that supports it.
    kwargs = {}
    temp = os.getenv("TEMPERATURE")
    if temp:
        kwargs["temperature"] = float(temp)
    return ChatDatabricks(
        workspace_client=WorkspaceClient(),  # app SP creds auto-injected at runtime
        model=GATEWAY_SERVICE,
        use_ai_gateway=True,
        max_tokens=max_tokens,
        **kwargs,
    )
