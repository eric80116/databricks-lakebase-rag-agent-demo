# 部署文檔 — Sentiva RAG Agent Demo

端到端部署到一個 Databricks workspace,以及乾淨清除。**換 workspace 只需編輯 `config.env`。**

> 品牌為虛構 **Sentiva**;與任何真實品牌無關。

---

## 0. 架構速覽
- **Unity Catalog** `dbx_agent_lakebase.rag`:volume `raw_docs`、Delta(docs_json/docs_chunks/docs_parsed)、AI Gateway inference table(`llm_inference_payload`)、MLflow OTel trace 表(`sentiva_otel_spans/logs/metrics/annotations`)。
- **Lakebase**(Postgres Autoscaling,project `sentiva-rag`):`kb.documents`(Lakebase Search:`lakebase_ann`+`lakebase_bm25`)、`mem.chat_history`(agent 記憶)。
- **Unity AI Gateway** model-service `dbx_agent_lakebase.rag.sentiva_llm` → gemini-flash;usage tracking + inference table。
- **模型**:LLM 預設 `databricks-gemini-3-5-flash`(2.5 已退役);embedding `databricks-qwen3-embedding-0-6b`(1024)。
- **Job** `sentiva_ingest`:產生資料 → 載入 → `ai_parse_document`/`ai_prep_search` 切塊 → embed → Lakebase + 建索引。
- **Apps**:App A `sentiva-agent-api`(FastAPI+LangChain,`/api/chat`);App B `sentiva-web`(React UI)。
- **觀測**:MLflow 3 trace 以 OTel 格式存 UC;AI/BI dashboard `sentiva_agent_perf`。

---

## 1. 前置作業
- **Databricks CLI** ≥ v0.294.0(本 demo v1.14.0)。
- 本機工具:`python3`、`psql`(postgresql-client)、`node`/`npm`、`envsubst`(gettext)、`bash`。
- CLI profile(可存取目標 workspace)。權限:能建 catalog / Lakebase project / serving / apps(demo 用 workspace admin)。
- Region:AI functions 需 **Serverless SQL Warehouse** 且 US/EU。
- **編輯 `config.env`**:唯一需按環境修改的檔(profile、catalog、schema、Lakebase project、warehouse、模型、`CATALOG_STORAGE_ROOT`)。

### ⚠️ 必須手動在 UI 開啟的兩個開關(CLI 無法設定)
這兩項是部署過程中的手動 checkpoint,`scripts/preflight.sh --full` 會自動驗證是否已開:
1. **Lakebase Search**:Lakebase → project `sentiva-rag` → Settings → **Enable Lakebase Search**(不可逆、會重啟 compute)。→ 在 `bootstrap.sh`(STAGE 1)之後、`bootstrap_search.sh`(STAGE 2)之前開。
2. **AI Prep Search preview**:Workspace → Settings → **Previews** → 開啟 **AI Prep Search**(`ai_parse_document` 不需;`ai_prep_search` 需)。→ 在跑 ingest job 之前開。
  - `CATALOG_STORAGE_ROOT`:此 metastore 需明確 managed storage。留空可跑 `scripts/detect_storage_root.sh` 自動建議;或設 `DEFAULT`(若 metastore 有預設 managed storage)。

---

## 2. 部署(依序;含 2 個手動 UI checkpoint)

```bash
source config.env

# STAGE 0 — preflight（非破壞性,驗證所有前置條件;deploy.sh 也會自動先跑）
./scripts/preflight.sh            # 部署前先跑,確認工具/認證/serverless warehouse/模型/storage/bundle
# （bootstrap + 兩個 UI 開關完成後,可再跑完整版檢查 Lakebase Search + ai_prep_search）
./scripts/preflight.sh --full

# STAGE 1 — catalog + Lakebase project
./scripts/bootstrap.sh
```
**[手動 UI #1]** Lakebase → project `sentiva-rag` → **Settings → Enable Lakebase Search**(不可逆、重啟 compute)。

**[手動 UI #2]** Workspace → Settings → **Previews** → 開啟 **AI Prep Search**(`ai_parse_document` 不需;`ai_prep_search` 需)。

```bash
# STAGE 2 — Lakebase Search 擴充 + kb/mem schema/表
./scripts/bootstrap_search.sh

# STAGE 3 — Unity AI Gateway model-service(usage tracking + inference table)
./scripts/create_gateway.sh

# STAGE 4 — build React UI
( cd src/app_ui/frontend && npm install && npm run build )

# STAGE 5 — 渲染 app.yaml/SQL/dashboard + 部署 DAB + 部署/啟動 apps + 授權 SP
./scripts/deploy.sh

# STAGE 6 — 跑資料管線(產生→載入→切塊→embed→Lakebase→索引)
databricks bundle run sentiva_ingest -t dev --profile "$PROFILE"
```

> **重要細節(都已內建於腳本/設定,列出供理解)**
> - Databricks Apps 監聽 **`$DATABRICKS_APP_PORT`(此環境 8000,非 8080)** — app.yaml 用 `uvicorn ... --port ${DATABRICKS_APP_PORT:-8080}`。
> - App SP 需 UC 權限(`grant_app_access.sh` 自動處理):`USE CATALOG`/`USE SCHEMA`/`EXECUTE`/`CREATE TABLE`/`SELECT`/`MODIFY ON SCHEMA` + warehouse `CAN_USE`;以及 Lakebase kb/mem 授權。
> - MLflow OTel→UC 需 experiment **建立時**綁 UC trace location,故授權必須在 app 啟動前(deploy.sh 已排序)。
> - OTel 表由 app SP 建立/擁有;查詢者(dashboard/你)需 `GRANT SELECT`(deploy 後可對 group 授權)。

---

## 3. 驗證
```bash
# 一鍵:preflight(基礎設施)+ 13 項端到端測試 + 總結(自動備好 pytest venv)
./scripts/test_all.sh
```
其他跑法:
```bash
pytest tests/ -v            # 只跑 13 項測試(需已裝 pytest;見 tests/README.md)
./scripts/preflight.sh --full   # 只驗基礎設施(工具/認證/warehouse/模型/storage/Lakebase Search/ai_prep_search)
```
`test_all.sh` 只是 `tests/` 的一鍵入口(複用同一套測試),另加 preflight 與環境備置。

---

## 4. 清除(避免非預期花費)
```bash
./scripts/teardown.sh                 # 讀 config.env;保留 catalog
./scripts/teardown.sh "" "" "" --drop-catalog   # 連 catalog 一起刪
./scripts/verify_teardown.sh          # 驗證所有(會計費)資源都已移除
```
teardown:`bundle destroy`(schema/volume/jobs/apps/dashboard)→ 刪 AI Gateway model-service → drop inference table → 刪 Lakebase project → 清除 config.env 的 `LAKEBASE_PROJECT_ACTUAL` → (選)刪 catalog。
> **Lakebase 專案名稱防呆**:`bootstrap.sh` 會建立 `<LAKEBASE_PROJECT>-<隨機>` 並把實際名稱記到 config.env 的 `LAKEBASE_PROJECT_ACTUAL`(所有後續階段都用它)。因為已刪除的 Lakebase 專案名稱會保留一段時間,teardown 會清掉該記錄,**下次部署自動用新後綴、不會撞名**。
> 成本備註:Lakebase suspend timeout 預設 24h(CLI 改不動);demo 結束務必 teardown + verify(見 §5)。

---

## 5. 需 UI 的項目(彙整)
CLI 無法設定、必須在 workspace UI 手動處理(`preflight.sh --full` 會驗證前兩項):
1. **Lakebase Search** — 見 §1(Enable Lakebase Search)。
2. **AI Prep Search preview** — 見 §1(Previews → AI Prep Search)。
3. (選)**Lakebase suspend timeout** — 預設 24h 才 scale-to-zero;CLI 改不動。要更省成本可在 Lakebase 的 compute 設定調短,或直接靠 §4 teardown 移除。
