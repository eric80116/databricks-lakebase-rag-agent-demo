#!/usr/bin/env bash
# ==============================================================================
# Sentiva RAG — preflight checks. Non-destructive: verifies every prerequisite
# BEFORE deploying so you don't fail halfway. Prints PASS/WARN/FAIL and exits
# non-zero if any hard requirement is missing.
#
# Usage: scripts/preflight.sh   (no flags; state-aware)
# Auto-detects state: the Lakebase-Search / ai_prep_search checks run only once the
# Lakebase project exists (i.e. after bootstrap + the UI toggles). Run it as often as
# you like — it checks whatever is applicable right now. No flags needed.
# ==============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
FAILS=0; WARNS=0
pass(){ printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn(){ printf "  \033[33m⚠\033[0m %s\n" "$1"; WARNS=$((WARNS+1)); }
fail(){ printf "  \033[31m✗\033[0m %s\n" "$1"; FAILS=$((FAILS+1)); }

echo "== config.env =="
if [ -f "$ROOT/config.env" ]; then source "$ROOT/config.env"; pass "config.env loaded"; else fail "config.env missing"; fi
PROFILE="${PROFILE:-DEFAULT}"; CATALOG="${CATALOG:-dbx_agent_lakebase}"; SCHEMA="${SCHEMA:-rag}"
LAKEBASE_PROJECT="${LAKEBASE_PROJECT_ACTUAL:-${LAKEBASE_PROJECT:-sentiva-rag}}"
for v in PROFILE CATALOG SCHEMA LAKEBASE_PROJECT WAREHOUSE_ID LLM_ENDPOINT EMBEDDING_ENDPOINT GATEWAY_SERVICE_ID; do
  [ -n "${!v:-}" ] && pass "config: $v=${!v}" || fail "config: $v not set"
done

echo "== local tools =="
for t in databricks python3 psql node npm envsubst; do
  command -v "$t" >/dev/null 2>&1 && pass "$t present" || { [ "$t" = "node" ] || [ "$t" = "npm" ] && warn "$t missing (needed to build React App B)" || fail "$t missing"; }
done
if command -v databricks >/dev/null 2>&1; then
  CV=$(databricks --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  pass "databricks CLI v$CV"
fi

echo "== auth / profile =="
if databricks current-user me --profile "$PROFILE" >/dev/null 2>&1; then
  ME=$(databricks current-user me --profile "$PROFILE" -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['emails'][0]['value'])")
  pass "authenticated as $ME (profile $PROFILE)"
else
  fail "cannot authenticate with profile '$PROFILE' (databricks auth login)"
fi
HOST=$(databricks auth env --profile "$PROFILE" 2>/dev/null | python3 -c "import json,sys
def f(o):
 if isinstance(o,dict):
  if 'DATABRICKS_HOST' in o: return o['DATABRICKS_HOST']
  for v in o.values():
   r=f(v)
   if r: return r
print(f(json.load(sys.stdin)) or '')" 2>/dev/null)
[ -n "$HOST" ] && pass "workspace $HOST" || warn "could not resolve workspace host"

echo "== serverless SQL warehouse (ai_parse_document / ai_prep_search) =="
WH=$(databricks warehouses get "$WAREHOUSE_ID" --profile "$PROFILE" -o json 2>/dev/null)
if [ -n "$WH" ]; then
  SVL=$(echo "$WH" | python3 -c "import json,sys;print(json.load(sys.stdin).get('enable_serverless_compute'))" 2>/dev/null)
  [ "$SVL" = "True" ] && pass "warehouse $WAREHOUSE_ID is serverless" || fail "warehouse $WAREHOUSE_ID is NOT serverless (ai functions require serverless)"
else
  fail "warehouse $WAREHOUSE_ID not found"
fi

echo "== model endpoints =="
TOKEN=$(databricks auth token --profile "$PROFILE" 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
if [ -n "$TOKEN" ] && [ -n "$HOST" ]; then
  # embedding: expect 1024-dim
  EDIM=$(curl -s "$HOST/serving-endpoints/$EMBEDDING_ENDPOINT/invocations" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"input":["x"]}' | python3 -c "import json,sys
try: print(len(json.load(sys.stdin)['data'][0]['embedding']))
except: print(0)" 2>/dev/null)
  [ "$EDIM" = "1024" ] && pass "embedding $EMBEDDING_ENDPOINT OK (dim $EDIM)" || fail "embedding $EMBEDDING_ENDPOINT not usable (dim=$EDIM)"
  # LLM: catch deprecation / unavailability
  LRESP=$(curl -s -o /tmp/pf_llm.json -w "%{http_code}" "$HOST/serving-endpoints/$LLM_ENDPOINT/invocations" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"OK"}],"max_tokens":10}')
  if [ "$LRESP" = "200" ]; then pass "LLM $LLM_ENDPOINT responds (200)"
  elif grep -qi deprecated /tmp/pf_llm.json; then fail "LLM $LLM_ENDPOINT is DEPRECATED — pick another in config.env"
  else warn "LLM $LLM_ENDPOINT returned HTTP $LRESP (check availability)"; fi
else
  warn "skipped model checks (no token/host)"
fi

echo "== catalog managed storage =="
if [ "${CATALOG_STORAGE_ROOT:-}" = "DEFAULT" ]; then pass "CATALOG_STORAGE_ROOT=DEFAULT (relies on metastore default managed storage)"
elif [ -n "${CATALOG_STORAGE_ROOT:-}" ]; then pass "CATALOG_STORAGE_ROOT set ($CATALOG_STORAGE_ROOT)"
else warn "CATALOG_STORAGE_ROOT empty — run scripts/detect_storage_root.sh and set it (this metastore needs it)"; fi

echo "== bundle validate =="
export BUNDLE_VAR_warehouse_id="${WAREHOUSE_ID:-}" BUNDLE_VAR_catalog="$CATALOG" BUNDLE_VAR_schema="$SCHEMA" \
  BUNDLE_VAR_lakebase_project="$LAKEBASE_PROJECT" BUNDLE_VAR_gateway_service_id="${GATEWAY_SERVICE_ID:-sentiva_llm}" \
  BUNDLE_VAR_mlflow_experiment="${MLFLOW_EXPERIMENT:-/Shared/sentiva-rag-traces}" BUNDLE_VAR_volume="${VOLUME:-raw_docs}" \
  BUNDLE_VAR_app_a_name="${APP_A_NAME:-sentiva-agent-api}" BUNDLE_VAR_app_b_name="${APP_B_NAME:-sentiva-web}" \
  BUNDLE_VAR_llm_endpoint="${LLM_ENDPOINT:-databricks-gemini-3-5-flash}" BUNDLE_VAR_embedding_endpoint="${EMBEDDING_ENDPOINT:-databricks-qwen3-embedding-0-6b}"
if databricks bundle validate -t dev --profile "$PROFILE" >/tmp/pf_bundle.txt 2>&1; then pass "bundle validate OK"
else fail "bundle validate failed (see /tmp/pf_bundle.txt)"; fi

# These need the Lakebase project to exist (post-bootstrap) + the UI toggles done.
PROJECT_EXISTS=$(databricks postgres list-projects --profile "$PROFILE" -o json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin); ps=d if isinstance(d,list) else d.get('projects',[])
print('yes' if any(p.get('project_id')=='$LAKEBASE_PROJECT' for p in ps) else 'no')" 2>/dev/null || echo no)
if [ "$PROJECT_EXISTS" = "yes" ]; then
  echo "== Lakebase Search + AI Prep Search (project exists — verifying UI toggles) =="
  # ai_prep_search preview
  APS=$(databricks experimental aitools tools query "SELECT ai_prep_search('hello world test') AS r" --profile "$PROFILE" 2>&1)
  if echo "$APS" | grep -qi 'not enabled'; then fail "AI Prep Search preview NOT enabled (Workspace Settings -> Previews)"
  elif echo "$APS" | grep -qi 'contents\|chunk\|\['; then pass "ai_prep_search works"
  else warn "ai_prep_search check inconclusive: $(echo "$APS" | head -c 80)"; fi
  # Lakebase Search extensions (needs project + UI enable)
  EP="projects/${LAKEBASE_PROJECT}/branches/production/endpoints/primary"
  LH=$(databricks postgres get-endpoint "$EP" --profile "$PROFILE" -o json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin)['status']['hosts']['host'])" 2>/dev/null)
  if [ -n "$LH" ] && command -v psql >/dev/null 2>&1; then
    LT=$(databricks postgres generate-database-credential "$EP" --profile "$PROFILE" -o json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])" 2>/dev/null)
    EXT=$(PGPASSWORD="$LT" psql "host=$LH user=${ME:-} dbname=databricks_postgres sslmode=require" -tA -c "SELECT string_agg(extname,',') FROM pg_extension WHERE extname IN ('lakebase_vector','lakebase_text')" 2>/dev/null)
    echo "$EXT" | grep -q lakebase_vector && pass "Lakebase Search extensions installed ($EXT)" || fail "Lakebase Search NOT enabled — UI: project Settings -> Enable Lakebase Search, then bootstrap_search.sh"
  else
    warn "skipped Lakebase Search check (psql missing)"
  fi
else
  echo "== Lakebase Search + AI Prep Search =="
  warn "Lakebase project not created yet — re-run preflight after bootstrap + the UI toggles to verify these"
fi

echo "== MANUAL UI steps (CLI cannot do these; enable in the workspace UI) =="
echo "  1. Lakebase project '${LAKEBASE_PROJECT:-sentiva-rag}' -> Settings -> Enable Lakebase Search (irreversible)"
echo "     (needed AFTER bootstrap.sh; auto-verified when you re-run preflight)"
echo "  2. Workspace -> Settings -> Previews -> enable 'AI Prep Search'"
echo "     (needed before running the ingest job; auto-verified when you re-run preflight)"

echo
echo "== summary: $FAILS fail, $WARNS warn =="
[ "$FAILS" -eq 0 ] && { echo "Preflight PASSED — safe to proceed."; exit 0; } || { echo "Preflight FAILED — fix the ✗ items before deploying."; exit 1; }
