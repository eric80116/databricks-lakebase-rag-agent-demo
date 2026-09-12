#!/usr/bin/env bash
# ==============================================================================
# Grant SELECT on the MLflow OTel trace tables to account users.
#
# The trace tables (<prefix>_otel_spans/logs/metrics/annotations + _trace_*) are
# created LAZILY by App A's service principal on the first trace, and the SP owns
# them — so the deploying user and the AI/BI dashboard cannot read them until
# granted. This script fires one warm-up request to create the tables, waits for
# the async span export to flush, then grants SELECT. Idempotent; best-effort.
#
# Runs as the deploying user (must be able to GRANT on the tables — catalog owner
# or metastore admin, which the demo assumes).
#
# Usage: scripts/grant_trace_access.sh [PROFILE]
# ==============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/../config.env" ] && source "$HERE/../config.env"

PROFILE="${1:-${PROFILE:-DEFAULT}}"
CATALOG="${CATALOG:-dbx_agent_lakebase}"; SCHEMA="${SCHEMA:-rag}"
APP_A="${APP_A_NAME:-sentiva-agent-api}"; PREFIX="${TRACE_TABLE_PREFIX:-sentiva}"

URL=$(databricks apps get "$APP_A" --profile "$PROFILE" -o json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('url',''))" 2>/dev/null || echo "")
TOKEN=$(databricks auth token --profile "$PROFILE" -o json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
[ -z "$URL" ] && { echo "   (App A URL not found — skipping trace grant)"; exit 0; }

echo "==> Warming up App A to create the trace tables (lazy on first trace)..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 -H "Authorization: Bearer $TOKEN" "$URL/health" 2>/dev/null || echo 000)
  [ "$code" = "200" ] && break
  sleep 5
done
curl -s -m 60 -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"input":[{"role":"user","content":"warm up"}],"custom_inputs":{"session_id":"warmup-trace"}}' \
  "$URL/invocations" >/dev/null 2>&1 || true

echo "==> Waiting for span export to flush + tables to appear..."
FOUND=""
for i in $(seq 1 12); do
  python3 -c "import time;time.sleep(5)"
  HIT=$(databricks experimental aitools tools query \
    "SHOW TABLES IN ${CATALOG}.${SCHEMA} LIKE '${PREFIX}_otel_spans'" --profile "$PROFILE" -o json 2>/dev/null \
    | python3 -c "import json,sys
try: print(len(json.load(sys.stdin)))
except: print(0)" 2>/dev/null || echo 0)
  if [ "${HIT:-0}" != "0" ]; then FOUND="yes"; break; fi
done
[ -z "$FOUND" ] && { echo "   (trace tables not created yet — re-run this script after some traffic)"; exit 0; }

echo "==> Granting SELECT on trace tables to \`account users\`..."
TABLES=$(databricks experimental aitools tools query \
  "SHOW TABLES IN ${CATALOG}.${SCHEMA}" --profile "$PROFILE" -o json 2>/dev/null \
  | python3 -c "import json,sys
d=json.load(sys.stdin)
print(' '.join(r['tableName'] for r in d if r['tableName'].startswith('${PREFIX}_otel') or r['tableName'].startswith('${PREFIX}_trace')))" 2>/dev/null || echo "")
for T in $TABLES; do
  databricks experimental aitools tools query \
    "GRANT SELECT ON TABLE ${CATALOG}.${SCHEMA}.${T} TO \`account users\`" --profile "$PROFILE" >/dev/null 2>&1 \
    && echo "   ok: $T" || echo "   (grant failed: $T)"
done
echo "==> Trace-table access granted."
