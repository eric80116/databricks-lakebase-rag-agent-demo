# Deployment — Sentiva RAG Agent Demo

How to deploy the whole demo end-to-end to a Databricks workspace, and how to tear it down
cleanly. **To target a different workspace, you only edit `config.env`.**

> "Sentiva" is a fictional brand; unrelated to any real company.

---

## 0. Architecture at a glance
- **Unity Catalog** `dbx_agent_lakebase.rag`: volume `raw_docs`, Delta tables (docs_json / docs_chunks / docs_parsed), the AI Gateway inference table (`llm_inference_payload`), and MLflow OTel trace tables (`sentiva_otel_spans/logs/metrics/annotations`).
- **Lakebase** (Postgres Autoscaling, one project): `kb.documents` (Lakebase Search: `lakebase_ann` + `lakebase_bm25`) and `mem.chat_history` (agent memory).
- **Unity AI Gateway** model-service `dbx_agent_lakebase.rag.sentiva_llm` → Gemini flash; usage tracking + inference table.
- **Models**: LLM defaults to `databricks-gemini-3-5-flash`; embedding `databricks-qwen3-embedding-0-6b` (1024-dim).
- **Job** `sentiva_ingest`: generate → load JSON → `ai_parse_document` / `ai_prep_search` chunking → embed → Lakebase + build indexes.
- **Apps**: App A `sentiva-agent-api` (FastAPI + LangChain, `/api/chat`); App B `sentiva-web` (React UI).
- **Observability**: MLflow 3 traces stored in OpenTelemetry format in Unity Catalog + an AI/BI dashboard `sentiva_agent_perf`.

---

## 1. Prerequisites
- **Databricks CLI** ≥ v0.294.0 (this demo used v1.14.0).
- Local tools: `python3`, `psql` (postgresql-client), `node`/`npm`, `envsubst` (gettext), `bash`.
- A CLI profile that can reach the target workspace. Permissions: able to create a catalog / Lakebase project / serving / apps (the demo used a workspace admin).
- Compute: a **serverless SQL warehouse** (serverless environment v3+ / DBR 17.3+). Note: `ai_parse_document` / `ai_prep_search` are only available in some regions — check Databricks' [AI function region availability](https://www.databricks.com/resources/feature-region-support) for your workspace.
- **Edit `config.env`**: the only file to change per environment (profile, catalog, schema, Lakebase project, warehouse, models, `CATALOG_STORAGE_ROOT`).
  - `CATALOG_STORAGE_ROOT`: some metastores require an explicit managed storage location. Leave it empty to have `scripts/detect_storage_root.sh` suggest one; or set `DEFAULT` if your metastore has default managed storage.

### ⚠️ Two toggles you MUST enable in the UI (not available via CLI)
These are manual checkpoints during deployment; `scripts/preflight.sh` verifies whether they are on:
1. **Lakebase Search**: Lakebase → your project → Settings → **Enable Lakebase Search** (irreversible; restarts the project compute). → enable after `bootstrap.sh` (STAGE 1) and before `bootstrap_search.sh` (STAGE 2).
2. **AI Prep Search preview**: Workspace → Settings → **Previews** → enable **AI Prep Search** (`ai_parse_document` does not need it; `ai_prep_search` does). → enable before running the ingest job.

---

## 2. Deploy (in order; includes 2 manual UI checkpoints)

```bash
source config.env

# STAGE 0 — preflight (non-destructive; state-aware; deploy.sh also runs it automatically)
./scripts/preflight.sh            # tools / auth / serverless warehouse / models / storage / bundle
# (it also checks Lakebase Search + ai_prep_search once the project exists — just re-run it later)

# STAGE 1 — catalog + Lakebase project
./scripts/bootstrap.sh
```
**[Manual UI checkpoints — details in §1 Prerequisites]** Enable the two UI toggles now:
**① Lakebase Search** before STAGE 2, and **② AI Prep Search** before STAGE 6.

```bash
# STAGE 2 — Lakebase Search extensions + kb/mem schemas & tables
./scripts/bootstrap_search.sh

# STAGE 3 — Unity AI Gateway model-service (usage tracking + inference table)
./scripts/create_gateway.sh

# STAGE 4 — build the React UI
( cd src/app_ui/frontend && npm install && npm run build )

# STAGE 5 — render app.yaml/SQL/dashboard from config.env, deploy the DAB,
#           deploy + start the apps, and grant the app service principal
./scripts/deploy.sh

# STAGE 6 — run the ingestion pipeline (generate → load → chunk → embed → Lakebase + indexes)
databricks bundle run sentiva_ingest -t dev --profile "$PROFILE"
```

> **Important details (already handled by the scripts/config — listed for understanding)**
> - Databricks Apps must listen on **`$DATABRICKS_APP_PORT`** (8000 in some workspaces, not 8080) — app.yaml uses `uvicorn ... --port ${DATABRICKS_APP_PORT:-8080}`.
> - The app service principal needs UC grants (`grant_app_access.sh` handles them): `USE CATALOG` / `USE SCHEMA` / `EXECUTE` / `CREATE TABLE` / `SELECT` / `MODIFY ON SCHEMA` + warehouse `CAN_USE`, plus Lakebase kb/mem grants.
> - MLflow-OTel-to-UC requires the experiment to be bound to a UC trace location **at creation time**, so grants must be in place before the app starts (deploy.sh orders this correctly).
> - Trace tables are owned by the app service principal; anyone querying them (dashboard / you) needs `GRANT SELECT`.

---

## 3. Verify
```bash
# one-click: preflight (infra) + 13 end-to-end tests + summary (auto-creates a pytest venv)
./scripts/test_all.sh
```
Other options:
```bash
pytest tests/ -v                 # just the 13 tests (needs pytest installed; see tests/README.md)
./scripts/preflight.sh    # just the infra checks
```
`test_all.sh` is a one-click entry point around `tests/` (same suite) plus preflight and env setup.

---

## 4. Teardown (avoid surprise cost)
```bash
./scripts/teardown.sh                          # reads config.env; keeps the catalog
./scripts/teardown.sh "" "" "" --drop-catalog  # also drop the catalog
./scripts/verify_teardown.sh                   # confirm all (billable) resources are gone
```
teardown does: `bundle destroy` (schema/volume/jobs/apps/dashboard) → delete the AI Gateway model-service → drop the inference table → delete the Lakebase project → clear `LAKEBASE_PROJECT_ACTUAL` from config.env → (optionally) drop the catalog.

> **Lakebase project-name safety**: `bootstrap.sh` creates `<LAKEBASE_PROJECT>-<random>` and records the actual name as `LAKEBASE_PROJECT_ACTUAL` in config.env (all later stages use it). Because a deleted Lakebase project name stays reserved for a while, teardown clears that record so the **next deploy uses a fresh suffix and never collides**.
> Cost note: the Lakebase suspend timeout defaults to 24h before scale-to-zero and is not settable via CLI — shorten it in the Lakebase compute settings if you want, or just rely on teardown. Always run teardown + verify when done.
