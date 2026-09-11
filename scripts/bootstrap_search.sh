#!/usr/bin/env bash
# ==============================================================================
# Sentiva RAG Demo — bootstrap STAGE 2 (run AFTER enabling Lakebase Search in UI)
#   - Installs lakebase_vector + lakebase_text extensions
#   - Creates kb + mem schemas and tables (scripts/lakebase_init.sql)
# Fails clearly if Lakebase Search was not enabled in the UI yet.
# Idempotent — safe to re-run.
#
# Usage: scripts/bootstrap_search.sh [PROFILE] [LAKEBASE_PROJECT]
# ==============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/../config.env" ] && source "$HERE/../config.env"

PROFILE="${1:-${PROFILE:-DEFAULT}}"
PROJECT="${2:-${LAKEBASE_PROJECT_ACTUAL:-${LAKEBASE_PROJECT:-sentiva-rag}}}"

first_name() { python3 -c "import json,sys; d=json.load(sys.stdin); d=d if isinstance(d,list) else next(iter(d.values())); print(d[0]['name'])"; }

echo "==> [STAGE 2] Lakebase Search init for project '$PROJECT'"

BRANCH=$(databricks postgres list-branches "projects/$PROJECT" --profile "$PROFILE" -o json | first_name)
ENDPOINT=$(databricks postgres list-endpoints "$BRANCH" --profile "$PROFILE" -o json | first_name)
DBNAME=$(databricks postgres list-databases "$BRANCH" --profile "$PROFILE" -o json | python3 -c "
import json,sys
d=json.load(sys.stdin); d=d if isinstance(d,list) else next(iter(d.values()))
print(d[0].get('status',{}).get('postgres_database') or 'databricks_postgres')")

HOST=$(databricks postgres get-endpoint "$ENDPOINT" --profile "$PROFILE" -o json \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['status']['hosts']['host'])")
TOKEN=$(databricks postgres generate-database-credential "$ENDPOINT" --profile "$PROFILE" -o json \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
PGUSER=$(databricks current-user me --profile "$PROFILE" -o json \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['emails'][0]['value'])")

command -v psql >/dev/null 2>&1 || { echo "!! psql not found. Install postgresql-client."; exit 1; }

echo "==> Applying scripts/lakebase_init.sql via psql (host=$HOST)..."
OUT=$(PGPASSWORD="$TOKEN" psql "host=$HOST user=$PGUSER dbname=$DBNAME sslmode=require" \
  -v ON_ERROR_STOP=0 -f "$(dirname "$0")/lakebase_init.sql" 2>&1)
echo "$OUT"

if echo "$OUT" | grep -qi 'must be loaded via shared_preload_libraries'; then
  echo
  echo "!! Lakebase Search is NOT enabled yet. Enable it in the UI first:"
  echo "   Lakebase -> project '$PROJECT' -> Settings -> Enable Lakebase Search"
  exit 1
fi

echo "==> STAGE 2 complete. Next steps (see docs/DEPLOYMENT.md §2):"
echo "    STAGE 3: scripts/create_gateway.sh"
echo "    STAGE 4: cd src/app_ui/frontend && npm install && npm run build"
echo "    STAGE 5: scripts/deploy.sh"
echo "    [UI] enable the AI Prep Search preview, then"
echo "    STAGE 6: databricks bundle run sentiva_ingest -t dev --profile $PROFILE"
