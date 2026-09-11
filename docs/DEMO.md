# Demo Guide — Sentiva RAG Agent

How to interact with the agent (UI and API), and how to track each Q&A's quality and
per-step latency in Databricks.

> "Sentiva" is a fictional brand. The knowledge base covers 5 product lines
> (Shield / Alert / Family / ID / Scan) across 4 languages (EN / JA / FR / DE).

URLs are workspace-specific — get them with `databricks apps get <app> -o json` (field `url`).
Placeholders below:
- App B (demo UI): `https://<app-b-url>`
- App A (API): `https://<app-a-url>`
- Dashboard: `/dashboardsv3/<dashboard-id>/published`

---

## 1. Interact via the UI (App B — the simulated product website)
1. Open App B: `https://<app-b-url>`
2. The home screen shows **quick-question cards** (multilingual). Click any to send, e.g.:
   - "How much does Sentiva Shield cost?"
   - 「Sentiva Shield の設定方法を教えて」
   - « Comment Sentiva Alert détecte-t-il les arnaques ? »
   - „Was kann Sentiva Family für Kinder tun?"
3. Or type your own question (the agent replies **in the question's language**).
4. Under each reply you can expand **Sources** (retrieved KB chunks: product / language / source), and see **timings** (retrieval / LLM / total ms) and the **trace_id** (links to the MLflow trace).
5. Conversations have **memory**: follow-up questions in the same session use prior context (stored in Lakebase `mem.chat_history`).

## 2. Interact via the API (App A — the endpoint a product website integrates with)
Endpoint: `POST https://<app-a-url>/api/chat`

```bash
# get a token (or just use App B's "Copy token" button)
TOKEN=$(databricks auth token --profile <your-profile> | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
# single-line command (avoids line-continuation being split by the shell)
curl -s -X POST "https://<app-a-url>/api/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"session_id":"demo-001","message":"Sentiva Shield の料金プランを教えて"}' | python3 -m json.tool
```
> App B's **Developer / API access** panel has a "Copy runnable command" button that copies a
> single-line command with the token already embedded — paste and run.

Response:
```json
{
  "answer": "…answer in the question's language…",
  "sources": [{"title":"…","source_uri":"sentiva-kb://shield/pricing","product":"Sentiva Shield","lang":"ja"}],
  "timings": {"retrieval_ms": 120, "llm_ms": 640, "total_ms": 780},
  "trace_id": "tr-…"
}
```
Health check: `GET https://<app-a-url>/api/health`.

> Product-web integration: call `/api/chat` the same way and pass your own conversation id as
> `session_id` to keep memory across turns.

---

## 3. Track quality & per-step latency (MLflow tracing, #3)
Every `/api/chat` call produces an MLflow **trace** (OpenTelemetry spans) with sub-spans for
**retrieval**, **LLM call**, etc., capturing token usage and per-step timing.

### 3.1 Inspect a single Q&A in the MLflow UI
- Workspace → **Experiments** → select the experiment (default `/Shared/sentiva-rag-traces`) → **Traces** tab.
- Open a trace to see the span tree: start/end time and duration per step, inputs/outputs, token counts.
- The `trace_id` returned by the API maps directly to a trace here.

### 3.2 Analyze with SQL (traces stored as OTel in UC)
Each Q&A's spans (including per-step `retrieval` / `llm` / `chat` timing) land in
`dbx_agent_lakebase.rag.sentiva_otel_spans` (OpenTelemetry format, MLflow 3 → Unity Catalog):
```sql
-- per-request latency by step (ms)
SELECT trace_id,
       min(time) AS request_time,
       max(CASE WHEN name='retrieval' THEN (end_time_unix_nano-start_time_unix_nano)/1e6 END) AS retrieval_ms,
       max(CASE WHEN name='llm'       THEN (end_time_unix_nano-start_time_unix_nano)/1e6 END) AS llm_ms,
       max(CASE WHEN name='chat'      THEN (end_time_unix_nano-start_time_unix_nano)/1e6 END) AS total_ms
FROM dbx_agent_lakebase.rag.sentiva_otel_spans
GROUP BY trace_id ORDER BY request_time DESC;

-- average latency per step
SELECT name AS step, avg((end_time_unix_nano-start_time_unix_nano)/1e6) AS avg_ms, count(*) n
FROM dbx_agent_lakebase.rag.sentiva_otel_spans WHERE name IN ('retrieval','llm') GROUP BY name;
```
The span `attributes` (VARIANT) hold inputs/outputs and more. There are also
`sentiva_otel_logs/metrics/annotations` tables.

### 3.3 AI Gateway usage / payload (#10)
- Each LLM call's request/response payload is logged to the inference table:
  `dbx_agent_lakebase.rag.llm_inference_payload`
- Workspace-wide usage/cost is also in the system tables (usage tracking).
```sql
SELECT * FROM dbx_agent_lakebase.rag.llm_inference_payload ORDER BY 1 DESC LIMIT 20;
```

---

## 4. AI/BI Dashboard (#13)
- Workspace → **Dashboards** → **"Sentiva RAG — Agent Performance"** (DAB resource `sentiva_agent_perf`).
- Contents: total requests, average total/LLM latency, **latency trend (total / llm / retrieval lines)**, **average latency per step**, and a recent-requests table.
- Source: `dbx_agent_lakebase.rag.sentiva_otel_spans` (definition in `dashboards/sentiva_agent.lvdash.json`).

---

## 5. Suggested demo script (for a customer walkthrough)
1. Click a Japanese card in the UI → show a multilingual answer + Sources.
2. Ask a follow-up → show memory.
3. Call `/api/chat` with curl → show the endpoint a product website can integrate with.
4. Open Experiments → open that trace → show per-step latency and tokens.
5. Open the AI/BI dashboard → show overall performance and the latency breakdown.
6. Open `llm_inference_payload` → show the AI Gateway's governance / auditability.
