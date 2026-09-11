#!/usr/bin/env bash
# ==============================================================================
# Probe whether candidate model(s) can drive the TOOL-CALLING agent via the Unity
# AI Gateway, BEFORE you swap LLM_ENDPOINT. For each model it temporarily creates a
# gateway model-service routing to it, runs a LangGraph create_react_agent through the
# gateway with a mock tool, and reports WORKS / FAILS / SKIP. Temp services are deleted.
#
# Usage: scripts/test_model.sh <model-endpoint> [<model-endpoint> ...]
#   e.g. scripts/test_model.sh databricks-claude-opus-4-8 databricks-glm-5-3-flash
# ==============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
[ -f "$ROOT/config.env" ] && source "$ROOT/config.env"

[ "$#" -ge 1 ] || { echo "usage: scripts/test_model.sh <model-endpoint> [<model-endpoint> ...]"; exit 2; }

VENV="${SENTIVA_PROBE_VENV:-/tmp/sentiva_probe_venv}"
if [ ! -x "$VENV/bin/python" ]; then
  echo "==> Creating probe venv at $VENV ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
fi
# install the (pinned) agent stack the probe needs — matches src/app_agent/requirements.txt
"$VENV/bin/python" - <<'PY' 2>/dev/null || NEED_INSTALL=1
import importlib.metadata as m
for p,v in [("databricks-langchain","0.20.0"),("langgraph","1.2.11"),("langgraph-prebuilt","1.1.0"),("mcp","1.29.1")]:
    assert m.version(p)==v
PY
if [ "${NEED_INSTALL:-0}" = "1" ]; then
  echo "==> Installing probe dependencies (one-time) ..."
  "$VENV/bin/pip" install -q databricks-sdk databricks-langchain==0.20.0 langgraph==1.2.11 langgraph-prebuilt==1.1.0 mcp==1.29.1
fi

PROFILE="${PROFILE:-DEFAULT}" CATALOG="${CATALOG:-dbx_agent_lakebase}" SCHEMA="${SCHEMA:-rag}" \
  "$VENV/bin/python" "$ROOT/tests/model_probe.py" "$@"
