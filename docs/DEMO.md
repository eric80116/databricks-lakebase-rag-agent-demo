# Demo 操作文檔 — Sentiva RAG Agent

本文件說明如何與 agent 互動(UI 與 API),以及如何在 Databricks 追蹤每次問答的成效與各環節耗時。

> Sentiva 為虛構品牌。KB 內容涵蓋 5 條產品線(Shield/Alert/Family/ID/Scan)× 4 語系(日/法/德/英)。

URL 為 workspace 專屬,用 `databricks apps get <app> -o json` 取 `url`。本次部署(<your-profile>)實際值:
- App B(demo UI):`https://<app-b-url>`
- App A(API):`https://<app-a-url>`
- Dashboard:`/dashboardsv3/<dashboard-id>/published`

---

## 1. 透過 UI 互動(App B — 模擬產品網站)
1. 開啟 App B:`https://<sentiva-web-app-url>`
2. 首頁會顯示**常問問題字卡**(多語系),點任一張即送出,例如:
   - "How much does Sentiva Shield cost?"
   - 「Sentiva Shield の料金プランを教えて」
   - « Comment Sentiva Alert détecte-t-il les arnaques ? »
   - „Was kann Sentiva Family für Kinder tun?"
3. 或直接在輸入框輸入問題(agent 會用**提問的語言**回答)。
4. 回覆下方可展開 **Sources**(引用的知識庫片段:產品/語系/來源)、以及 **timings**(retrieval / LLM / total 毫秒)與 **trace_id**(對應 MLflow 追蹤)。
5. 對話具**記憶**:同一 session 可追問(記憶存於 Lakebase `mem.chat_history`)。

## 2. 透過 API 互動(App A — 給既有 product web 串接的 endpoint)
Endpoint:`POST https://<sentiva-agent-api-url>/api/chat`

```bash
# 取 token(或直接用 App B 的「Copy token」按鈕)
TOKEN=$(databricks auth token --profile <your-profile> | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
# 單行指令(避免換行接續被終端機拆開)
curl -s -X POST "https://<sentiva-agent-api-url>/api/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"session_id":"demo-001","message":"Sentiva Shield の料金プランを教えて"}' | python3 -m json.tool
```
> App B 的 **Developer / API access** 面板有「Copy runnable command」按鈕,會複製**已內嵌 token 的單行指令**,貼上即可跑。
回傳:
```json
{
  "answer": "…（以提問語言回答）…",
  "sources": [{"title":"…","source_uri":"sentiva-kb://shield/pricing","product":"Sentiva Shield","lang":"ja"}],
  "timings": {"retrieval_ms": 120, "llm_ms": 640, "total_ms": 780},
  "trace_id": "tr-…"
}
```
健康檢查:`GET https://<sentiva-agent-api-url>/api/health`。

> product web 整合:以相同格式呼叫 `/api/chat`,`session_id` 帶你端的對話 id 即可延續記憶。

---

## 3. 追蹤每次問答的成效與各環節耗時(MLflow Tracing,#3)
每次 `/api/chat` 都會用 `mlflow.langchain.autolog()` 產生一條 **trace**(OpenTelemetry span),含子 span:**檢索(retrieval)**、**LLM 呼叫** 等,並記錄 token 使用與各段耗時。

### 3.1 在 MLflow UI 看單次問答
- Workspace → **Experiments** → 選 experiment(預設 `/Shared/sentiva-rag-traces`)→ **Traces** 分頁。
- 點一條 trace 可看 span 樹:每個環節的**開始/結束時間、耗時**、輸入/輸出、token 數。
- UI 回傳的 `trace_id` 可直接對應到這裡。

### 3.2 用 SQL 分析(trace 以 OTel 格式存 UC)
每次問答的 spans(含 `retrieval`/`llm`/`chat` 每步耗時)存於 `dbx_agent_lakebase.rag.sentiva_otel_spans`(OpenTelemetry 格式,MLflow 3 → UC)。每步耗時:
```sql
-- 每次請求各環節耗時(毫秒)
SELECT trace_id,
       min(time) AS request_time,
       max(CASE WHEN name='retrieval' THEN (end_time_unix_nano-start_time_unix_nano)/1e6 END) AS retrieval_ms,
       max(CASE WHEN name='llm'       THEN (end_time_unix_nano-start_time_unix_nano)/1e6 END) AS llm_ms,
       max(CASE WHEN name='chat'      THEN (end_time_unix_nano-start_time_unix_nano)/1e6 END) AS total_ms
FROM dbx_agent_lakebase.rag.sentiva_otel_spans
GROUP BY trace_id ORDER BY request_time DESC;

-- 每步平均耗時
SELECT name AS step, avg((end_time_unix_nano-start_time_unix_nano)/1e6) AS avg_ms, count(*) n
FROM dbx_agent_lakebase.rag.sentiva_otel_spans WHERE name IN ('retrieval','llm') GROUP BY name;
```
span 的 `attributes`(VARIANT)含輸入/輸出等細節。另有 `sentiva_otel_logs/metrics/annotations`。

### 3.3 AI Gateway 用量 / payload(#10)
- 每次 LLM 呼叫的 request/response payload 記於 inference table:
  `dbx_agent_lakebase.rag.llm_inference_payload`
- 全域用量/成本另見 system tables(usage tracking)。
```sql
SELECT * FROM dbx_agent_lakebase.rag.llm_inference_payload ORDER BY 1 DESC LIMIT 20;
```

---

## 4. AI/BI Dashboard(#13)
- Workspace → **Dashboards** → **"Sentiva RAG — Agent Performance"**(DAB 資源 `sentiva_agent_perf`)。
- 內容:總請求數、平均 total/LLM 耗時、**延遲趨勢(total/llm/retrieval 分線)**、**各步驟平均耗時**、近期請求明細。
- 資料來源:`dbx_agent_lakebase.rag.sentiva_otel_spans`(定義見 `dashboards/sentiva_agent.lvdash.json`)。

---

## 5. Demo 建議腳本(給客戶展示)
1. 先用 UI 點一張日文字卡 → 展示多語回答 + Sources。
2. 追問一句(展示記憶)。
3. 用 curl 打 `/api/chat` → 展示「product web 可直接串接的 endpoint」。
4. 切到 Experiments → 打開該次 trace → 展示各環節耗時與 token。
5. 打開 AI/BI dashboard → 展示整體成效與延遲分解。
6. 打開 `llm_inference_payload` → 展示 AI Gateway 的治理/可稽核性。
