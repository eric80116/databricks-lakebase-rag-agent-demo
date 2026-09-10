#!/usr/bin/env bash
# ==============================================================================
# Grant App A's service principal access to the Lakebase kb + mem schemas.
# The schemas are owned by the deploying user (created in bootstrap_search.sh),
# so the app SP (CAN_CONNECT_AND_CREATE only) needs explicit grants.
# Run AFTER `databricks apps deploy sentiva-agent-api`.
#
# Usage: scripts/grant_app_access.sh [PROFILE] [APP_NAME] [LAKEBASE_PROJECT]
# ==============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/../config.env" ] && source "$HERE/../config.env"

PROFILE="${1:-${PROFILE:-DEFAULT}}"
APP="${2:-sentiva-agent-api}"
PROJECT="${3:-${LAKEBASE_PROJECT:-sentiva-rag}}"

first_name() { python3 -c "import json,sys; d=json.load(sys.stdin); d=d if isinstance(d,list) else next(iter(d.values())); print(d[0]['name'])"; }

CATALOG="${CATALOG:-dbx_agent_lakebase}"
SCHEMA="${SCHEMA:-rag}"

SP=$(databricks apps get "$APP" --profile "$PROFILE" -o json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('service_principal_client_id',''))")
[ -n "$SP" ] || { echo "!! Could not resolve service principal for app '$APP'. Deploy the app first."; exit 1; }
echo "==> App '$APP' service principal: $SP"

# --- Unity Catalog grants: SP must see the AI Gateway model-service + catalog/schema,
#     and be able to auto-create/write the MLflow OTel trace tables (#3). ---
echo "==> Granting UC USE / EXECUTE / CREATE / MODIFY to $SP ..."
for STMT in \
  "GRANT USE CATALOG ON CATALOG \`$CATALOG\` TO \`$SP\`" \
  "GRANT USE SCHEMA ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$SP\`" \
  "GRANT EXECUTE ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$SP\`" \
  "GRANT CREATE TABLE ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$SP\`" \
  "GRANT SELECT ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$SP\`" \
  "GRANT MODIFY ON SCHEMA \`$CATALOG\`.\`$SCHEMA\` TO \`$SP\`" ; do
  databricks experimental aitools tools query "$STMT" --profile "$PROFILE" >/dev/null 2>&1 \
    && echo "   ok: $STMT" || echo "   (skip/failed) $STMT"
done

# SP needs to use the SQL warehouse MLflow uses to write trace tables.
if [ -n "${WAREHOUSE_ID:-}" ]; then
  echo "==> Granting CAN_USE on warehouse $WAREHOUSE_ID to $SP ..."
  databricks permissions update warehouses "$WAREHOUSE_ID" \
    --json "{\"access_control_list\":[{\"service_principal_name\":\"$SP\",\"permission_level\":\"CAN_USE\"}]}" \
    --profile "$PROFILE" >/dev/null 2>&1 && echo "   ok" || echo "   (skip/failed)"
fi

BRANCH=$(databricks postgres list-branches "projects/$PROJECT" --profile "$PROFILE" -o json | first_name)
ENDPOINT=$(databricks postgres list-endpoints "$BRANCH" --profile "$PROFILE" -o json | first_name)
HOST=$(databricks postgres get-endpoint "$ENDPOINT" --profile "$PROFILE" -o json | python3 -c "import json,sys; print(json.load(sys.stdin)['status']['hosts']['host'])")
TOKEN=$(databricks postgres generate-database-credential "$ENDPOINT" --profile "$PROFILE" -o json | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
PGUSER=$(databricks current-user me --profile "$PROFILE" -o json | python3 -c "import json,sys; print(json.load(sys.stdin)['emails'][0]['value'])")

echo "==> Granting on kb (read) and mem (read/write) to $SP ..."
PGPASSWORD="$TOKEN" psql "host=$HOST user=$PGUSER dbname=databricks_postgres sslmode=require" -v ON_ERROR_STOP=0 <<SQL
-- Lakebase maps the Databricks identity to a Postgres role named by the client id.
GRANT USAGE ON SCHEMA kb  TO "$SP";
GRANT SELECT ON ALL TABLES IN SCHEMA kb  TO "$SP";
ALTER DEFAULT PRIVILEGES IN SCHEMA kb  GRANT SELECT ON TABLES TO "$SP";

GRANT USAGE ON SCHEMA mem TO "$SP";
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA mem TO "$SP";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA mem TO "$SP";
ALTER DEFAULT PRIVILEGES IN SCHEMA mem GRANT SELECT, INSERT ON TABLES TO "$SP";
SQL

echo "==> Grants applied (verify with \\dp in psql if needed)."
