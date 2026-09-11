#!/usr/bin/env bash
# ==============================================================================
# Sentiva RAG — verify teardown removed everything (avoid surprise cost).
# Run AFTER scripts/teardown.sh. Non-destructive. Exits non-zero if any resource
# that could still incur cost is found.
#
# Usage: scripts/verify_teardown.sh [PROFILE]
# ==============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/../config.env" ] && source "$HERE/../config.env"

PROFILE="${1:-${PROFILE:-DEFAULT}}"
CATALOG="${CATALOG:-dbx_agent_lakebase}"; SCHEMA="${SCHEMA:-rag}"
APP_A="${APP_A_NAME:-sentiva-agent-api}"; APP_B="${APP_B_NAME:-sentiva-web}"
SVC="${GATEWAY_SERVICE_ID:-sentiva_llm}"
# resolve the (possibly suffixed) project name that teardown targeted
PROJECT="${LAKEBASE_PROJECT_ACTUAL:-${LAKEBASE_PROJECT:-sentiva-rag}}"

FAILS=0; WARNS=0
pass(){ printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn(){ printf "  \033[33m⚠\033[0m %s\n" "$1"; WARNS=$((WARNS+1)); }
fail(){ printf "  \033[31m✗\033[0m %s\n" "$1"; FAILS=$((FAILS+1)); }

echo "== apps (billable compute) =="
for A in "$APP_A" "$APP_B"; do
  # Existence is decided by whether `apps get` returns app JSON (has "name") or an
  # error ("... does not exist"). Parsing state directly mis-fires on the error text.
  OUT=$(databricks apps get "$A" --profile "$PROFILE" -o json 2>&1)
  if ! printf '%s' "$OUT" | grep -q '"name"'; then pass "app removed: $A"
  else
    ST=$(printf '%s' "$OUT" | python3 -c "import json,sys
try: print(json.load(sys.stdin).get('compute_status',{}).get('state','') or '')
except: print('')" 2>/dev/null)
    if printf '%s' "$ST" | grep -qiE 'DELETING|STOPPED'; then warn "app '$A' is $ST (being removed) — re-check shortly"
    else fail "app still active: $A ($ST)"; fi
  fi
done

echo "== job =="
JOBHIT=$(databricks jobs list --profile "$PROFILE" -o json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin); js=d if isinstance(d,list) else d.get('jobs',[])
print(sum(1 for j in js if 'Sentiva RAG Ingest' in (j.get('settings',{}) or {}).get('name','')))" 2>/dev/null || echo 0)
[ "${JOBHIT:-0}" = "0" ] && pass "ingest job removed" || fail "ingest job still exists ($JOBHIT)"

echo "== dashboard =="
DHIT=$(databricks lakeview list --profile "$PROFILE" -o json 2>/dev/null | python3 -c "
import json,sys
try:
  d=json.load(sys.stdin); ds=d if isinstance(d,list) else d.get('dashboards',[])
  print(sum(1 for x in ds if 'Sentiva RAG' in x.get('display_name','') and x.get('lifecycle_state','')!='TRASHED'))
except: print(0)" 2>/dev/null || echo 0)
[ "${DHIT:-0}" = "0" ] && pass "dashboard removed" || warn "dashboard may still exist ($DHIT) — check /dashboards"

echo "== AI Gateway model-service =="
if databricks ai-gateway get-model-service "model-services/${CATALOG}.${SCHEMA}.${SVC}" --profile "$PROFILE" >/dev/null 2>&1; then
  fail "model-service still exists: ${CATALOG}.${SCHEMA}.${SVC}"
else pass "AI Gateway model-service removed"; fi

echo "== inference table =="
if databricks experimental aitools tools query "SELECT 1 FROM ${CATALOG}.${SCHEMA}.llm_inference_payload LIMIT 1" --profile "$PROFILE" >/dev/null 2>&1; then
  warn "inference table still queryable (ok if you kept the catalog/schema)"
else pass "inference table gone"; fi

echo "== Lakebase project (billable compute) =="
LIVE=$(databricks postgres list-projects --profile "$PROFILE" -o json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin); ps=d if isinstance(d,list) else d.get('projects',[])
print('yes' if any(p.get('project_id')=='$PROJECT' for p in ps) else 'no')" 2>/dev/null || echo no)
if [ "$LIVE" = "no" ]; then pass "Lakebase project removed: $PROJECT"
else warn "Lakebase project '$PROJECT' still listed (deleted names linger ~a while; compute should be stopped). Re-check later."; fi

echo "== stray serving endpoints (sentiva*) =="
SE=$(databricks serving-endpoints list --profile "$PROFILE" -o json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin); es=d if isinstance(d,list) else d.get('endpoints',[])
print(sum(1 for e in es if 'sentiva' in e.get('name','').lower()))" 2>/dev/null || echo 0)
[ "${SE:-0}" = "0" ] && pass "no stray sentiva serving endpoints" || fail "sentiva serving endpoint(s) remain ($SE)"

echo "== catalog =="
if databricks catalogs get "$CATALOG" --profile "$PROFILE" >/dev/null 2>&1; then
  warn "catalog '$CATALOG' still present (expected unless you ran teardown --drop-catalog)"
else pass "catalog '$CATALOG' removed"; fi

echo
echo "== summary: $FAILS fail, $WARNS warn =="
if [ "$FAILS" -eq 0 ]; then echo "✅ Teardown verified — no billable Sentiva resources remain."; exit 0
else echo "❌ Some resources remain (see ✗). Investigate to avoid cost."; exit 1; fi
