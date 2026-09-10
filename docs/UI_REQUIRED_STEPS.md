# UI-required steps (CLI/API 無法完成的項目)

> 這裡記錄所有「必須在 Databricks UI 手動操作」的項目,因為目前 CLI/API 不支援。
> 每項標註:狀態、影響、決策。

## 1. Lakebase Search 擴充套件 (lakebase_vector / lakebase_text) — 需 UI 啟用
來源:https://docs.databricks.com/aws/en/oltp/projects/lakebase-search#install-extensions

- **正確啟用方式(UI,非 CLI)**:Lakebase project → 左側 **Settings** → **Lakebase Search** → **Enable Lakebase Search**。
- **啟用後才可執行(psql)**:
  ```sql
  CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE;  -- 會一併裝 pgvector
  CREATE EXTENSION IF NOT EXISTS lakebase_text;            -- BM25 全文
  ```
- **索引**:向量 `CREATE INDEX ON kb.documents USING lakebase_ann (embedding vector_cosine_ops);`;BM25 `USING lakebase_bm25 (content_tsv)`(BM25 於建置時計算語料統計,**須在資料載入後才建**)。
- **⚠️ 不可逆 / 影響**:啟用會**重啟專案所有 compute(中斷現有連線)**,且**啟用後無法關閉**(Beta)。
- **前置**:Postgres 16+(本專案 PG 17 ✅);專案需具 Beta access。
- **CLI 現況**:`databricks postgres` 無此開關,必須在 UI 操作。
- **CLI 可行替代(若不啟用)**:`vector`(pgvector 0.8.0 已確認)做語意向量 + Postgres 原生 `tsvector`/GIN 做關鍵字 → 等價混合搜尋,全自動化免 UI。
- **決策**:✅ 已啟用(2026-09-10,使用者於 UI 操作)。extensions 已裝:`lakebase_vector 1.1.0`、`lakebase_text 0.1.1`、`vector 0.8.0`。
- **部署順序(重要)**:因為啟用是手動 UI 步驟,部署拆兩段避免中斷:
  1. `scripts/bootstrap.sh`(建 catalog + Lakebase project,然後停下)
  2. **手動**:UI 啟用 Lakebase Search
  3. `scripts/bootstrap_search.sh`(建 extensions + schema/表)
  4. `databricks bundle deploy -t dev`

## 2. Lakebase compute suspend timeout(scale-to-zero 閒置時間)
- **現況**:預設 `suspend_timeout_duration = 86400s`(24 小時)才 scale-to-zero。
- **CLI 現況**:`update-endpoint` / `update-project` 對 `suspend_timeout_duration` 回報 `Unknown field path in update_mask`,無法用 CLI 設定。
- **影響**:1 CU 於閒置 24h 才休眠,demo 期間會有 idle 成本(teardown 腳本可完全移除)。
- **待確認 (UI)**:Lakebase project → Compute/Endpoint 設定,將 suspend timeout 調短(如 5 分鐘)。
- **決策**:✅ 使用者選擇「留預設,靠 teardown 控成本」。demo 結束即跑 `scripts/teardown.sh` 完全移除。

## 3. AI Gateway inference table / usage tracking
- ✅ 全程 CLI 完成,**無需 UI**。用 `databricks ai-gateway create-model-service` 建 `dbx_agent_lakebase.rag.sentiva_llm`,已開 usage tracking + inference table(`llm_inference_payload`),實測寫入成功。

## 4. AI Prep Search Preview — 需 UI 啟用
- **現況**:呼叫 `ai_prep_search()` 回報 `PERMISSION_DENIED: AI Prep Search Preview is not enabled. A workspace admin must enable it in workspace preview settings.`
- **需 UI (admin)**:Workspace → Settings → **Previews** → 開啟 **AI Prep Search**(或名稱相近的 preview 項)。
- **對比**:`ai_parse_document()` **不需** preview,已實測可用(輸出含 table/bbox)。
- **CLI 可行替代(若不啟用)**:用簡單的 Python/SQL 切塊器(依段落/字數切),不需 preview。功能陽春一點但可跑。
- **決策**:⏳ 等使用者確認(啟用 preview 用原生 ai_prep_search,或用 fallback 切塊器)。
