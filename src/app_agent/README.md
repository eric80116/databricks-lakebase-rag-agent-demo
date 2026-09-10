# App A — Sentiva RAG Agent API

FastAPI + LangChain agent, deployed as a Databricks App. Retrieves from Lakebase
(hybrid vector + keyword), calls the LLM via the Unity AI Gateway, keeps memory in
Lakebase, and traces every request with MLflow.

## Endpoints
- `GET /api/health` → `{"status":"ok"}`
- `POST /api/chat` `{session_id, message}` → `{answer, sources[], timings{retrieval_ms,llm_ms,total_ms}, trace_id}`

## Env vars (set in app.yaml / app resources)
| Var | Purpose | Default |
|---|---|---|
| GATEWAY_SERVICE | Unity AI Gateway model-service name | dbx_agent_lakebase.rag.sentiva_llm |
| EMBEDDING_ENDPOINT | Embedding serving endpoint | databricks-qwen3-embedding-0-6b |
| LAKEBASE_ENDPOINT | Lakebase endpoint path (for credential) | projects/sentiva-rag/branches/production/endpoints/primary |
| MLFLOW_EXPERIMENT | Experiment for traces | /Shared/sentiva-rag |
| K | retrieval top-k | 5 |
| PGHOST/PGDATABASE/PGUSER/PGSSLMODE | injected by the `postgres` app resource | — |

## Deploy notes / verify at deploy
- Wire a `postgres` app resource (branch + database) so PG env vars are injected.
- Run `scripts/grant_app_access.sh` after deploy so the app SP can read `kb` and read/write `mem`.
- **Verify:** Lakebase credential path — `lakebase.py` tries the SDK `postgres.generate_database_credential`; if the SDK shape differs, set `PGPASSWORD` via the resource or adjust `_fresh_token()`.
- **Verify:** trace-id API — `app.py` reads `span.trace_id`/`request_id` then falls back to `get_last_active_trace_id()`.
- LLM responses are gemini reasoning-model shaped (`content` = list of parts); `gateway_llm._extract_text` handles both list and string.

## Local
`pip install -r requirements.txt && uvicorn app:app --port 8080` (needs a Databricks profile in env and network to the workspace; DB calls need Lakebase reachable).
