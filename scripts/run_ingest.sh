#!/usr/bin/env bash
# ==============================================================================
# Run the ingestion job (STAGE 5). Sources config.env for the profile + DAB vars
# so it works from any shell (no need to export $PROFILE / BUNDLE_VAR_* yourself).
#
# Usage: scripts/run_ingest.sh
# ==============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/../config.env" ] && source "$HERE/../config.env"

PROFILE="${PROFILE:-DEFAULT}"
LAKEBASE_PROJECT="${LAKEBASE_PROJECT_ACTUAL:-${LAKEBASE_PROJECT:-sentiva-rag}}"

export BUNDLE_VAR_catalog="${CATALOG:-dbx_agent_lakebase}" BUNDLE_VAR_schema="${SCHEMA:-rag}" \
  BUNDLE_VAR_lakebase_project="$LAKEBASE_PROJECT" BUNDLE_VAR_warehouse_id="${WAREHOUSE_ID:-}" \
  BUNDLE_VAR_llm_endpoint="${LLM_ENDPOINT:-databricks-gemini-3-5-flash}" \
  BUNDLE_VAR_embedding_endpoint="${EMBEDDING_ENDPOINT:-databricks-qwen3-embedding-0-6b}" \
  BUNDLE_VAR_gateway_service_id="${GATEWAY_SERVICE_ID:-sentiva_llm}" \
  BUNDLE_VAR_mlflow_experiment="${MLFLOW_EXPERIMENT:-/Shared/sentiva-rag-traces}" \
  BUNDLE_VAR_volume="${VOLUME:-raw_docs}" \
  BUNDLE_VAR_app_a_name="${APP_A_NAME:-sentiva-agent-api}" BUNDLE_VAR_app_b_name="${APP_B_NAME:-sentiva-web}"

echo "==> Running ingestion job (profile=$PROFILE)..."
databricks bundle run sentiva_ingest -t dev --profile "$PROFILE"
