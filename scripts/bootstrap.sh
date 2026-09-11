#!/usr/bin/env bash
# ==============================================================================
# Sentiva RAG Demo — bootstrap STAGE 1 (resources NOT managed by DAB)
#   1. Unity Catalog catalog
#   2. Lakebase (Postgres Autoscaling) project + primary endpoint
# Then STOPS with instructions: you must enable Lakebase Search in the UI
# (irreversible), and afterwards run scripts/bootstrap_search.sh (STAGE 2).
# This ordering avoids a mid-deploy failure on the manual UI step.
# Idempotent — safe to re-run.
#
# Usage: scripts/bootstrap.sh [PROFILE] [CATALOG] [LAKEBASE_PROJECT]
# ==============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

# Load per-environment config (the only file to edit per deployment).
[ -f "$HERE/../config.env" ] && source "$HERE/../config.env"

PROFILE="${1:-${PROFILE:-DEFAULT}}"
CATALOG="${2:-${CATALOG:-dbx_agent_lakebase}}"
PROJECT_BASE="${3:-${LAKEBASE_PROJECT:-sentiva-rag}}"
STORAGE_ROOT="${CATALOG_STORAGE_ROOT:-}"
CONFIG_FILE="$HERE/../config.env"

echo "==> [STAGE 1] Profile=$PROFILE  Catalog=$CATALOG  LakebaseProject(base)=$PROJECT_BASE"

# --- 1. Catalog (managed storage root handling) -----------------------------
if databricks catalogs get "$CATALOG" --profile "$PROFILE" >/dev/null 2>&1; then
  echo "==> Catalog '$CATALOG' already exists."
elif [ -z "$STORAGE_ROOT" ]; then
  echo "!! CATALOG_STORAGE_ROOT is empty in config.env. This metastore may need an"
  echo "   explicit managed storage root. Running detection to suggest one:"
  echo
  "$HERE/detect_storage_root.sh" "$PROFILE" "$CATALOG" || true
  echo
  echo "!! Set CATALOG_STORAGE_ROOT in config.env (or 'DEFAULT' if default managed"
  echo "   storage works in your metastore), then re-run scripts/bootstrap.sh."
  exit 1
elif [ "$STORAGE_ROOT" = "DEFAULT" ]; then
  echo "==> Creating catalog '$CATALOG' (default managed storage)..."
  databricks catalogs create "$CATALOG" --profile "$PROFILE" \
    --comment "Sentiva RAG demo (fictional brand; no real-brand names)" >/dev/null
else
  echo "==> Creating catalog '$CATALOG' with storage_root=$STORAGE_ROOT ..."
  databricks catalogs create "$CATALOG" --storage-root "$STORAGE_ROOT" --profile "$PROFILE" \
    --comment "Sentiva RAG demo (fictional brand; no real-brand names)" >/dev/null
fi

# --- 2. Lakebase project ----------------------------------------------------
# A deleted Lakebase project name lingers (reserved) for a while, so reusing a fixed
# name after teardown collides. We create "<base>-<random>" and record the actual name
# in config.env (LAKEBASE_PROJECT_ACTUAL); all later stages + teardown read that.
proj_exists() {
  databricks postgres list-projects --profile "$PROFILE" -o json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin); ps=d if isinstance(d,list) else d.get('projects',[])
print('yes' if any(p.get('project_id')=='$1' for p in ps) else 'no')" 2>/dev/null || echo no
}

PROJECT="${LAKEBASE_PROJECT_ACTUAL:-}"
if [ -n "$PROJECT" ] && [ "$(proj_exists "$PROJECT")" = "yes" ]; then
  echo "==> Reusing Lakebase project '$PROJECT' (recorded in config.env)."
else
  PROJECT="${PROJECT_BASE}-$(python3 -c 'import secrets;print(secrets.token_hex(3))')"
  echo "==> Creating Lakebase project '$PROJECT' (a few minutes)..."
  databricks postgres create-project "$PROJECT" \
    --json "{\"spec\": {\"display_name\": \"Sentiva RAG Demo\"}}" \
    --profile "$PROFILE" >/dev/null
  if grep -q '^export LAKEBASE_PROJECT_ACTUAL=' "$CONFIG_FILE" 2>/dev/null; then
    sed -i.bak "s#^export LAKEBASE_PROJECT_ACTUAL=.*#export LAKEBASE_PROJECT_ACTUAL=\"$PROJECT\"#" "$CONFIG_FILE" && rm -f "$CONFIG_FILE.bak"
  else
    printf '\n# Auto-managed by bootstrap.sh — actual (suffixed) Lakebase project. Removed by teardown.sh.\nexport LAKEBASE_PROJECT_ACTUAL="%s"\n' "$PROJECT" >> "$CONFIG_FILE"
  fi
  echo "==> Recorded LAKEBASE_PROJECT_ACTUAL=$PROJECT in config.env"
fi

cat <<EOF

==============================================================================
STAGE 1 complete. MANUAL STEP REQUIRED (cannot be done via CLI):

  1. Open the workspace UI -> Lakebase -> project '$PROJECT'
  2. Settings -> Lakebase Search -> "Enable Lakebase Search"
     (WARNING: this restarts the project compute and is IRREVERSIBLE)

Then run STAGE 2:

  scripts/bootstrap_search.sh $PROFILE $PROJECT

Followed by:

  databricks bundle deploy -t dev --profile $PROFILE
==============================================================================
EOF
