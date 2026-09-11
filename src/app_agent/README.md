# App A — Sentiva RAG Agent API

FastAPI, deployed as a Databricks App. The agent is a LangGraph `create_react_agent`
(tool-calling) wrapped in the MLflow `ResponsesAgent` interface: `search_knowledge_base`
is a tool that retrieves from Lakebase (hybrid vector + keyword); the LLM is called via
`ChatDatabricks(use_ai_gateway=True)` → the Unity AI Gateway; memory is in Lakebase; every
request is traced with MLflow (autolog + an explicit `retrieval` span). The model is chosen
at the gateway (routing destination), so the agent is model-agnostic — see `gateway_chat.py`.

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
- Retrieval sources/timings are captured per request via a registry keyed by an id passed
  through the graph's `RunnableConfig` (the tool runs on a different thread, so ContextVar
  / threading.local don't reach back).
- Model swap = change `LLM_ENDPOINT` in config.env + re-run `scripts/create_gateway.sh`
  (it recreates the service since the gateway routing can't be updated in place). Use a
  tool-calling-capable, non-reasoning model (deepseek / Llama / Mistral) — Gemini 2.5/3.x
  drop their thought_signature on tool calls.

## Local
`pip install -r requirements.txt && uvicorn app:app --port 8080` (needs a Databricks profile in env and network to the workspace; DB calls need Lakebase reachable).
