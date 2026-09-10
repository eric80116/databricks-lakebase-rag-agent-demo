#!/usr/bin/env bash
# ==============================================================================
# Sentiva RAG — one-click "test all functions".
#   1. preflight --full (infra prerequisites, incl. Lakebase Search + ai_prep_search)
#   2. pytest tests/ -v (13 end-to-end checks against the deployed demo)
# Auto-creates a venv for pytest (avoids PEP 668). Skip preflight: SKIP_PREFLIGHT=1
#
# Usage: scripts/test_all.sh
# ==============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

echo "================= 1/2  PREFLIGHT ================="
if [ "${SKIP_PREFLIGHT:-0}" != "1" ]; then
  "$HERE/preflight.sh" --full || { echo "!! Preflight failed — fix ✗ items (or SKIP_PREFLIGHT=1 to force tests)."; exit 1; }
else
  echo "(skipped)"
fi

echo
echo "================= 2/2  TEST SUITE (pytest) ================="
VENV="${SENTIVA_VENV:-/tmp/sentiva_venv}"
PY="$VENV/bin/python"
if [ ! -x "$PY" ]; then
  echo "==> creating venv at $VENV ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q pytest
fi
"$PY" -m pytest tests/ -v
RC=$?

echo
if [ "$RC" -eq 0 ]; then
  echo "✅ ALL FUNCTIONS PASSED (preflight + 13 e2e tests)."
else
  echo "❌ Some tests failed (see above). Exit $RC."
fi
exit $RC
