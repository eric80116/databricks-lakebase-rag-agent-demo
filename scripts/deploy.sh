#!/usr/bin/env bash
# ==============================================================================
# Sentiva RAG — portable deploy (run AFTER bootstrap.sh + [UI: enable Lakebase
# Search] + bootstrap_search.sh + [UI: enable AI Prep Search preview]).
# Renders app.yaml + SQL from config.env, deploys DAB, deploys+starts apps, grants.
# Everything workspace-specific comes from config.env — no hardcoded values.
#
# Usage: scripts/deploy.sh
# ==============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
source "$ROOT/config.env"
# Use the actual (suffixed) Lakebase project recorded by bootstrap.sh, if any.
LAKEBASE_PROJECT="${LAKEBASE_PROJECT_ACTUAL:-${LAKEBASE_PROJECT:-sentiva-rag}}"

# Preflight: verify prerequisites before deploying (skip with SKIP_PREFLIGHT=1).
if [ "${SKIP_PREFLIGHT:-0}" != "1" ]; then
  "$HERE/preflight.sh" || { echo "!! Preflight failed — aborting deploy (SKIP_PREFLIGHT=1 to override)."; exit 1; }
fi

APP_A="${APP_A_NAME:-sentiva-agent-api}"
APP_B="${APP_B_NAME:-sentiva-web}"

# --- derive composite values ------------------------------------------------
export GATEWAY_SERVICE="${CATALOG}.${SCHEMA}.${GATEWAY_SERVICE_ID}"
export LAKEBASE_ENDPOINT="projects/${LAKEBASE_PROJECT}/branches/production/endpoints/primary"
export AGENT_APP_NAME="$APP_A"
export EMBEDDING_ENDPOINT MLFLOW_EXPERIMENT RETRIEVAL_K

echo "==> Rendering app.yaml from config.env..."
envsubst '$GATEWAY_SERVICE $EMBEDDING_ENDPOINT $LAKEBASE_ENDPOINT $MLFLOW_EXPERIMENT $RETRIEVAL_K $CATALOG $SCHEMA $TRACE_TABLE_PREFIX $WAREHOUSE_ID' \
  < "$ROOT/src/app_agent/app.yaml.tmpl" > "$ROOT/src/app_agent/app.yaml"
envsubst '$AGENT_APP_NAME' \
  < "$ROOT/src/app_ui/app.yaml.tmpl" > "$ROOT/src/app_ui/app.yaml"

echo "==> Rendering SQL catalog/schema from config.env..."
for f in "$ROOT"/src/jobs/sql/*.sql; do
  sed -i.bak -E "s#[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.(docs_json|docs_chunks|docs_parsed)#${CATALOG}.${SCHEMA}.\1#g" "$f"
  sed -i.bak "s#/Volumes/[A-Za-z0-9_]*/[A-Za-z0-9_]*/raw_docs#/Volumes/${CATALOG}/${SCHEMA}/raw_docs#g" "$f"
  rm -f "$f.bak"
done
echo "==> Rendering dashboard catalog/schema from config.env..."
sed -i.bak -E "s#[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.(${TRACE_TABLE_PREFIX}_otel_[a-z]+)#${CATALOG}.${SCHEMA}.\1#g" "$ROOT/dashboards/sentiva_agent.lvdash.json"
rm -f "$ROOT/dashboards/sentiva_agent.lvdash.json.bak"

echo "==> Deploying DAB (vars from config.env)..."
export BUNDLE_VAR_catalog="$CATALOG" BUNDLE_VAR_schema="$SCHEMA" \
  BUNDLE_VAR_lakebase_project="$LAKEBASE_PROJECT" BUNDLE_VAR_warehouse_id="$WAREHOUSE_ID" \
  BUNDLE_VAR_llm_endpoint="$LLM_ENDPOINT" BUNDLE_VAR_embedding_endpoint="$EMBEDDING_ENDPOINT" \
  BUNDLE_VAR_gateway_service_id="$GATEWAY_SERVICE_ID" BUNDLE_VAR_mlflow_experiment="$MLFLOW_EXPERIMENT" \
  BUNDLE_VAR_volume="${VOLUME:-raw_docs}" \
  BUNDLE_VAR_app_a_name="$APP_A" BUNDLE_VAR_app_b_name="$APP_B"
databricks bundle deploy -t dev --profile "$PROFILE"

# Create the Unity AI Gateway model-service now that the UC schema exists (bundle deploy
# created it). Idempotent — skips if it already exists.
echo "==> Creating Unity AI Gateway model-service..."
"$HERE/create_gateway.sh"

# workspace files root where the bundle uploaded source
EMAIL=$(databricks current-user me --profile "$PROFILE" -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['userName'])")
SRC="/Workspace/Users/${EMAIL}/.bundle/sentiva-rag/dev/files/src"

# Grant the app SP FIRST (the app binds its UC trace location at startup, which
# needs CREATE TABLE already in place). The app object + SP exist after bundle deploy.
echo "==> Granting App A SP access to Lakebase + UC (before app start)..."
databricks apps start "$APP_A" --profile "$PROFILE" 2>/dev/null || true  # ensure SP/compute exist
"$HERE/grant_app_access.sh" "$PROFILE" "$APP_A" "$LAKEBASE_PROJECT" || true

echo "==> Deploying + starting apps..."
# 'apps deploy' requires the app compute to already be RUNNING, so start each app
# (idempotent; waits for compute) BEFORE deploying its source. App A was started above.
databricks apps deploy "$APP_A" --source-code-path "$SRC/app_agent" --profile "$PROFILE" || true
databricks apps start "$APP_B" --profile "$PROFILE" 2>/dev/null || true
databricks apps deploy "$APP_B" --source-code-path "$SRC/app_ui" --profile "$PROFILE" || true

# Trace tables are created lazily by the SP on the first trace and are SP-owned;
# warm up + grant SELECT so the dashboard and tests can read them.
"$HERE/grant_trace_access.sh" "$PROFILE" || true

echo "==> Deploy complete."
databricks apps get "$APP_A" --profile "$PROFILE" -o json | python3 -c "import json,sys;print('App A:',json.load(sys.stdin).get('url'))"
databricks apps get "$APP_B" --profile "$PROFILE" -o json | python3 -c "import json,sys;print('App B:',json.load(sys.stdin).get('url'))"
