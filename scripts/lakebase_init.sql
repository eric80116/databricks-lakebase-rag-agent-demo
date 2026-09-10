-- Sentiva RAG demo — Lakebase Search init (run AFTER enabling Lakebase Search in the project UI).
-- KB "search" = lakebase_vector (semantic ANN, lakebase_ann index) + lakebase_text (BM25, lakebase_bm25 index).
-- Idempotent. Indexes are built by the embed job AFTER bulk load (BM25 needs corpus stats at build time).

CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE;  -- installs pgvector as dependency
CREATE EXTENSION IF NOT EXISTS lakebase_text;            -- BM25 full-text

SELECT extname, extversion FROM pg_extension
 WHERE extname IN ('lakebase_vector','lakebase_text','vector') ORDER BY extname;

CREATE SCHEMA IF NOT EXISTS kb;
CREATE SCHEMA IF NOT EXISTS mem;

-- Knowledge base: one row per chunk. Embedding dim = 1024 (Qwen3-Embedding-0.6B, verified).
CREATE TABLE IF NOT EXISTS kb.documents (
  id          TEXT PRIMARY KEY,
  source_uri  TEXT,
  product     TEXT,          -- Sentiva product line (Shield/Alert/Family/ID/Scan)
  lang        TEXT,          -- ja / fr / de / en
  category    TEXT,          -- overview / pricing / features / setup / privacy / troubleshooting
  chunk_pos   INT,
  content     TEXT NOT NULL, -- chunk_to_retrieve (returned to the agent)
  embedding   vector(1024),  -- from chunk_to_embed
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Defensive: ensure columns exist even if an older table shape was created earlier.
ALTER TABLE kb.documents ADD COLUMN IF NOT EXISTS category TEXT;

-- Keyword column for BM25 (language-agnostic 'simple' config for multilingual content).
ALTER TABLE kb.documents
  ADD COLUMN IF NOT EXISTS content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED;

-- Remove the earlier pgvector-era GIN index; Lakebase Search uses lakebase_bm25 instead (built by embed job).
DROP INDEX IF EXISTS kb.idx_documents_tsv;

-- Agent memory: chat message history keyed by session.
CREATE TABLE IF NOT EXISTS mem.chat_history (
  id          BIGSERIAL PRIMARY KEY,
  session_id  TEXT NOT NULL,
  role        TEXT NOT NULL,   -- human / ai / system
  content     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON mem.chat_history (session_id, id);

-- NOTE: KB search indexes are created by the embed job after data load:
--   CREATE INDEX idx_documents_ann  ON kb.documents USING lakebase_ann  (embedding vector_cosine_ops);
--   CREATE INDEX idx_documents_bm25 ON kb.documents USING lakebase_bm25 (content_tsv);
