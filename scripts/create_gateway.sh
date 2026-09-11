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

# Detect the current routing destination (empty if the service doesn't exist yet).
CUR=$(databricks ai-gateway get-model-service "$FULL" --profile "$PROFILE" -o json 2>/dev/null \
  | python3 -c "import json,sys
try:
    d=json.load(sys.stdin); dests=d.get('config',{}).get('routing',{}).get('destinations',[])
    print(dests[0].get('name','') if dests else '')
except Exception: print('')" 2>/dev/null || echo "")

if [ "$CUR" = "system.ai.${LLM}" ]; then
  echo "==> Model service already routes to system.ai.${LLM}. Skipping."
else
  # config.routing can't be updated in place, so to SWAP the model we delete + recreate.
  # The inference table isn't dropped with the service, so drop it too (avoids "table
  # already exists" on recreate). Changing LLM_ENDPOINT in config.env + re-running this
  # (or deploy.sh) is therefore all it takes to switch the model.
  if [ -n "$CUR" ]; then
    echo "==> Destination changed ($CUR -> system.ai.${LLM}); recreating service..."
    databricks ai-gateway delete-model-service "$FULL" --profile "$PROFILE" >/dev/null 2>&1 || true
    databricks experimental aitools tools query \
      "DROP TABLE IF EXISTS ${CATALOG}.${SCHEMA}.llm_inference_payload" --profile "$PROFILE" >/dev/null 2>&1 || true
  fi
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
