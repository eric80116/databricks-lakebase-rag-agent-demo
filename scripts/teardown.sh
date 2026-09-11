#!/usr/bin/env bash
# ==============================================================================
# Sentiva RAG Demo — full teardown (avoid unexpected cost).
# Removes: DAB-managed resources, the Lakebase project, the AI Gateway endpoint,
# and (optionally) the catalog.
#
# Usage: scripts/teardown.sh [--drop-catalog] [PROFILE] [CATALOG] [LAKEBASE_PROJECT]
#   --drop-catalog : also drop the catalog (position-independent flag; default keeps it)
#   positional PROFILE/CATALOG/LAKEBASE_PROJECT override config.env (rarely needed)
# ==============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/../config.env" ] && source "$HERE/../config.env"

# Parse args: --drop-catalog can appear anywhere; other args are positional overrides.
DROP_CATALOG=""; POSN=()
for arg in "$@"; do
  case "$arg" in
    --drop-catalog) DROP_CATALOG="--drop-catalog" ;;
    *) POSN+=("$arg") ;;
  esac
done
PROFILE="${POSN[0]:-${PROFILE:-DEFAULT}}"
CATALOG="${POSN[1]:-${CATALOG:-dbx_agent_lakebase}}"
PROJECT="${POSN[2]:-${LAKEBASE_PROJECT_ACTUAL:-${LAKEBASE_PROJECT:-sentiva-rag}}}"
CONFIG_FILE="$HERE/../config.env"
SCHEMA="${SCHEMA:-rag}"
GATEWAY_SERVICE_ID="${GATEWAY_SERVICE_ID:-sentiva_llm}"

echo "!! This will DESTROY the Sentiva RAG demo on profile '$PROFILE'."
read -r -p "Type 'destroy' to continue: " CONFIRM
[ "$CONFIRM" = "destroy" ] || { echo "Aborted."; exit 1; }

echo "==> Destroying DAB-managed resources..."
# Pass the same vars used at deploy so bundle validation (which destroy runs) passes
# — notably warehouse_id, whose databricks.yml default is empty.
export BUNDLE_VAR_catalog="$CATALOG" BUNDLE_VAR_schema="$SCHEMA" \
  BUNDLE_VAR_lakebase_project="$PROJECT" BUNDLE_VAR_warehouse_id="${WAREHOUSE_ID:-}" \
  BUNDLE_VAR_llm_endpoint="${LLM_ENDPOINT:-databricks-gemini-3-5-flash}" \
  BUNDLE_VAR_embedding_endpoint="${EMBEDDING_ENDPOINT:-databricks-qwen3-embedding-0-6b}" \
  BUNDLE_VAR_gateway_service_id="${GATEWAY_SERVICE_ID:-sentiva_llm}" \
  BUNDLE_VAR_mlflow_experiment="${MLFLOW_EXPERIMENT:-/Shared/sentiva-rag-traces}" \
  BUNDLE_VAR_volume="${VOLUME:-raw_docs}" \
  BUNDLE_VAR_app_a_name="${APP_A_NAME:-sentiva-agent-api}" BUNDLE_VAR_app_b_name="${APP_B_NAME:-sentiva-web}"
databricks bundle destroy -t dev --profile "$PROFILE" --auto-approve || echo "   (bundle destroy skipped/failed — continuing)"

echo "==> Deleting Unity AI Gateway model-service (if present)..."
databricks ai-gateway delete-model-service "model-services/${CATALOG}.${SCHEMA:-rag}.${GATEWAY_SERVICE_ID:-sentiva_llm}" --profile "$PROFILE" 2>/dev/null || echo "   (not present)"
echo "==> Dropping inference payload table (if present)..."
databricks experimental aitools tools query "DROP TABLE IF EXISTS ${CATALOG}.${SCHEMA:-rag}.llm_inference_payload" --profile "$PROFILE" 2>/dev/null || echo "   (skip)"

# The MLflow experiment lives in the workspace (NOT the catalog), so bundle destroy
# leaves it behind. Its UC trace-location binding (catalog.schema.prefix) is fixed at
# creation, so a stale experiment makes the NEXT deploy skip recreating the otel tables
# (which WERE dropped with the schema) -> traces fail with TABLE_DOES_NOT_EXIST. Delete it.
echo "==> Deleting MLflow experiment '${MLFLOW_EXPERIMENT:-/Shared/sentiva-rag-traces}' (frees the trace-location binding)..."
EXP_ID=$(databricks experiments get-by-name "${MLFLOW_EXPERIMENT:-/Shared/sentiva-rag-traces}" --profile "$PROFILE" -o json 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('experiment') or d).get('experiment_id',''))" 2>/dev/null || echo "")
if [ -n "$EXP_ID" ]; then
  databricks experiments delete-experiment "$EXP_ID" --profile "$PROFILE" 2>/dev/null \
    && echo "   deleted experiment $EXP_ID" || echo "   (delete failed — remove it in the MLflow UI)"
else
  echo "   (experiment not present)"
fi

echo "==> Deleting Lakebase project '$PROJECT' (all branches/data)..."
databricks postgres delete-project "projects/$PROJECT" --profile "$PROFILE" 2>/dev/null \
  || echo "   (not present or already deleted)"
# Clear the recorded actual name so the NEXT bootstrap creates a fresh suffixed project
# (a deleted Lakebase project name lingers/reserved for a while — avoids collision).
if [ -f "$CONFIG_FILE" ] && grep -q '^export LAKEBASE_PROJECT_ACTUAL=' "$CONFIG_FILE"; then
  sed -i.bak '/^export LAKEBASE_PROJECT_ACTUAL=/d; /^# Auto-managed by bootstrap.sh/d' "$CONFIG_FILE" && rm -f "$CONFIG_FILE.bak"
  echo "==> Cleared LAKEBASE_PROJECT_ACTUAL from config.env (next deploy uses a new suffix)."
fi

if [ "$DROP_CATALOG" = "--drop-catalog" ]; then
  echo "==> Dropping catalog '$CATALOG' (CASCADE)..."
  databricks catalogs delete "$CATALOG" --force --profile "$PROFILE" 2>/dev/null \
    || echo "   (catalog delete failed — drop remaining schemas manually)"
else
  echo "==> Catalog '$CATALOG' left in place (pass --drop-catalog to remove)."
fi

echo "==> Teardown complete. Verify in the workspace that no serving endpoints / apps / Lakebase compute remain billable."
