#!/usr/bin/env bash
# ==============================================================================
# Suggest a catalog managed-storage root for the CURRENT workspace.
# Lists external locations the current principal can WRITE to (ALL_PRIVILEGES /
# CREATE_* / owner), and highlights one whose name matches the workspace host.
# Prints candidates; prints a single RECOMMENDED= line if it can pick confidently.
# Does NOT modify anything. Use its output to fill CATALOG_STORAGE_ROOT in config.env.
#
# Usage: scripts/detect_storage_root.sh [PROFILE] [CATALOG]
# ==============================================================================
set -euo pipefail
PROFILE="${1:-${PROFILE:-DEFAULT}}"
CATALOG="${2:-${CATALOG:-dbx_agent_lakebase}}"

# Derive a token from the workspace host (e.g. the workspace-name tokens -> matching external-location names)
HOST=$(databricks auth env --profile "$PROFILE" 2>/dev/null | python3 -c "import json,sys
try: print(json.load(sys.stdin).get('DATABRICKS_HOST',''))
except: print('')" 2>/dev/null || echo "")
ME=$(databricks current-user me --profile "$PROFILE" -o json | python3 -c "import json,sys; print(json.load(sys.stdin)['emails'][0]['value'])")

echo "==> Workspace host: $HOST"
echo "==> Principal: $ME"
echo "==> External locations you can write to:"

databricks external-locations list --profile "$PROFILE" -o json 2>/dev/null | python3 - "$HOST" "$ME" "$PROFILE" "$CATALOG" <<'PY'
import json, subprocess, sys, re
host, me, profile, catalog = sys.argv[1:5]
data = json.load(sys.stdin)
locs = data if isinstance(data, list) else data.get("external_locations", [])
# token(s) from host to match location names
host_tokens = [t for t in re.split(r'[^a-z0-9]+', host.lower()) if len(t) >= 5 and t not in ('https','cloud','databricks','com','sandbox','serverless')]

writable = []
for e in locs:
    name = e.get("name",""); url = e.get("url",""); owner = e.get("owner","")
    if e.get("read_only"): continue
    ok = (owner == me)
    if not ok:
        try:
            g = subprocess.run(["databricks","grants","get","external-location",name,"--profile",profile,"-o","json"],
                               capture_output=True, text=True, timeout=25)
            pas = json.loads(g.stdout or "{}").get("privilege_assignments",[])
            for a in pas:
                if a.get("principal")==me and any(p in ("ALL_PRIVILEGES","CREATE_EXTERNAL_TABLE","CREATE_MANAGED_STORAGE","CREATE_EXTERNAL_VOLUME") for p in a.get("privileges",[])):
                    ok = True; break
        except Exception:
            pass
    if ok:
        score = sum(1 for t in host_tokens if t in name.lower())
        writable.append((score, name, url))

writable.sort(reverse=True)
for score, name, url in writable[:15]:
    star = " <== matches workspace" if score>0 else ""
    print(f"   [{name}] {url}{star}")

best = [w for w in writable if w[0] > 0]
if len(best) >= 1:
    print()
    print(f"RECOMMENDED={best[0][2].rstrip('/')}/{catalog}")
    print("   (add this to config.env as CATALOG_STORAGE_ROOT, after confirming it is correct)")
elif writable:
    print()
    print("No single confident match. Pick one of the writable locations above and set")
    print("CATALOG_STORAGE_ROOT=<url>/"+catalog+" in config.env.")
else:
    print("   (none found — you may have default managed storage: try CATALOG_STORAGE_ROOT=DEFAULT)")
PY
