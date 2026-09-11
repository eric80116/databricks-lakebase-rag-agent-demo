#!/usr/bin/env python3
"""Probe whether a model can drive the TOOL-CALLING agent via the Unity AI Gateway.

For each model endpoint given, this temporarily creates a gateway model-service routing to
it, runs a LangGraph create_react_agent (ChatDatabricks -> the gateway) with a mock tool,
and reports WORKS / FAILS (with the reason). It cleans up the temp service afterwards.

Use it BEFORE swapping LLM_ENDPOINT so you know a candidate model can tool-call. Reasoning
models whose tool-call format needs a provider-native round-trip (Gemini 2.5/3.x drop their
thought_signature on the gateway's unified surface) will report FAILS.

Usage:
  python tests/model_probe.py <model-endpoint> [<model-endpoint> ...]
Env (from config.env): PROFILE, CATALOG, SCHEMA.
"""
import json
import os
import subprocess
import sys
import time
import uuid

PROFILE = os.environ.get("PROFILE") or os.environ.get("DATABRICKS_CONFIG_PROFILE", "DEFAULT")
# WorkspaceClient() (used by ChatDatabricks) authenticates via DATABRICKS_CONFIG_PROFILE.
os.environ["DATABRICKS_CONFIG_PROFILE"] = PROFILE
CATALOG = os.environ.get("CATALOG", "dbx_agent_lakebase")
SCHEMA = os.environ.get("SCHEMA", "rag")


def _cli(*args):
    return subprocess.run(["databricks", *args, "--profile", PROFILE],
                          capture_output=True, text=True)


def _create_service(svc, model):
    body = {"config": {"routing": {"destinations": [{
        "destination_type": "DESTINATION_TYPE_PAY_PER_TOKEN_FOUNDATION_MODEL",
        "name": f"system.ai.{model}",
        "pay_per_token_config": {"model": f"models/system.ai.{model}"},
        "traffic_percentage": 100,
    }]}}}
    r = _cli("ai-gateway", "create-model-service", f"schemas/{CATALOG}.{SCHEMA}", svc,
             "--json", json.dumps(body))
    return r.returncode == 0, (r.stderr or r.stdout)


def _probe(model):
    # a FRESH, unique service per model — reusing one name hits routing-propagation lag
    # (a recreated same-name service can still serve the previous destination for a while).
    svc_id = f"sentiva_probe_{uuid.uuid4().hex[:8]}"
    full = f"model-services/{CATALOG}.{SCHEMA}.{svc_id}"
    ok, msg = _create_service(svc_id, model)
    if not ok:
        return "SKIP", f"gateway service create failed: {msg.strip()[:160]}"
    try:
        svc = f"{CATALOG}.{SCHEMA}.{svc_id}"
        os.environ["GATEWAY_SERVICE"] = svc
        time.sleep(6)  # brief settle for the fresh service

        from databricks.sdk import WorkspaceClient
        from databricks_langchain import ChatDatabricks
        from langchain_core.tools import tool
        from langgraph.prebuilt import create_react_agent

        calls = []

        @tool
        def search_knowledge_base(query: str) -> str:
            """Search the Sentiva product knowledge base."""
            calls.append(query)
            return "[1] (Sentiva Shield, en) Sentiva Shield Basic is $29.99/year for one device."

        # match the agent: no temperature (many models reject it); only max_tokens
        llm = ChatDatabricks(workspace_client=WorkspaceClient(), model=svc,
                             use_ai_gateway=True, max_tokens=400)
        agent = create_react_agent(
            llm, tools=[search_knowledge_base],
            prompt="You are Sentiva support. ALWAYS call search_knowledge_base first, then answer using ONLY its results.")
        result = agent.invoke({"messages": [{"role": "user", "content": "How much does Sentiva Shield cost?"}]})
        final = result["messages"][-1].content
        if isinstance(final, list):
            final = "".join(p.get("text", "") for p in final if isinstance(p, dict))
        if calls and final.strip():
            return "WORKS", f"{len(calls)} tool call(s); answer: {final.strip()[:70]}"
        return "PARTIAL", f"no tool call or empty answer (tool calls={calls})"
    except Exception as e:
        m = str(e)
        if "thought_signature" in m:
            return "FAILS", "reasoning model — thought_signature dropped on tool calls (not tool-callable via the unified gateway)"
        return "FAILS", m.replace("\n", " ")[:200]
    finally:
        # only remove the temp probe service; it has no inference table, so nothing else
        # to clean (must NOT touch the production llm_inference_payload table).
        _cli("ai-gateway", "delete-model-service", full)


def main():
    models = sys.argv[1:]
    if not models:
        print(__doc__)
        sys.exit(2)
    print(f"Probing {len(models)} model(s) for tool-calling via the Unity AI Gateway "
          f"(profile={PROFILE}, {CATALOG}.{SCHEMA})\n")
    results = []
    for m in models:
        print(f"--- {m} ---", flush=True)
        status, detail = _probe(m)
        icon = {"WORKS": "✅", "FAILS": "❌", "SKIP": "⚠️", "PARTIAL": "⚠️"}.get(status, "?")
        print(f"  {icon} {status}: {detail}\n", flush=True)
        results.append((m, status))
    print("=== summary ===")
    for m, s in results:
        print(f"  {s:8} {m}")
    # non-zero exit if any candidate outright FAILS
    sys.exit(1 if any(s == "FAILS" for _, s in results) else 0)


if __name__ == "__main__":
    main()
