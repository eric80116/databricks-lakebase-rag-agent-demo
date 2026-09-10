#!/usr/bin/env bash
# ==============================================================================
# Create the Unity AI Gateway model-service fronting the Databricks-hosted LLM,
# with payload logging (inference table) into $CATALOG.$SCHEMA (#9 / #10).
# This is NOT a DAB resource (ai-gateway is a separate CLI), so it is scripted
# here and removed by scripts/teardown.sh. Idempotent.
#
# Usage: scripts/create_gateway.sh
# ==============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/../config.env" ] && source "$HERE/../config.env"

PROFILE="${PROFILE:-DEFAULT}"
CATALOG="${CATALOG:-dbx_agent_lakebase}"
SCHEMA="${SCHEMA:-rag}"
SVC="${GATEWAY_SERVICE_ID:-sentiva_llm}"
LLM="${LLM_ENDPOINT:-databricks-gemini-3-5-flash}"

FULL="model-services/${CATALOG}.${SCHEMA}.${SVC}"
echo "==> Gateway model-service: $FULL  ->  system.ai.${LLM}"

if databricks ai-gateway get-model-service "$FULL" --profile "$PROFILE" >/dev/null 2>&1; then
  echo "==> Model service already exists. Skipping create."
else
  databricks ai-gateway create-model-service "schemas/${CATALOG}.${SCHEMA}" "$SVC" \
    --comment "Sentiva RAG demo LLM gateway (usage tracking + payload logging)" \
    --json "{
      \"config\": {
        \"routing\": {
          \"destinations\": [{
            \"destination_type\": \"DESTINATION_TYPE_PAY_PER_TOKEN_FOUNDATION_MODEL\",
            \"name\": \"system.ai.${LLM}\",
            \"pay_per_token_config\": {\"model\": \"models/system.ai.${LLM}\"},
            \"traffic_percentage\": 100
          }]
        },
        \"inference_table\": {\"disabled\": false, \"parent\": \"schemas/${CATALOG}.${SCHEMA}\", \"table_name_prefix\": \"llm_inference\"}
      }
    }" --profile "$PROFILE"
fi

echo "==> Done. Service: $FULL"
