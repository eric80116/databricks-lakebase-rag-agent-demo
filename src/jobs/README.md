# Sentiva RAG Data Ingestion Pipeline

This pipeline automates the complete data ingestion workflow for the Sentiva RAG demo. It handles multilingual document generation, processing, chunking, embedding, and Lakebase (Postgres) indexing.

## Architecture

The ingestion pipeline consists of 6 tasks in a DAG:

```
generate_data
    ↓
    ├─→ load_json → chunk_json ──→┐
    │                               ├─→ embed_and_load
    ├─→ parse_pdf → chunk_pdf ─────┘
```

### Task Breakdown

1. **generate_data** (Python)
   - Invokes `src/data_gen/generate_docs.py` to create 48 multilingual JSON documents
   - Invokes `src/data_gen/generate_pdfs.py` to create 3 PDF files with tables
   - Writes to `/Volumes/dbx_agent_lakebase/rag/raw_docs/raw_json/` and `raw_pdf/`

2. **load_json** (SQL)
   - Reads JSON files using `read_files(..., format => 'json')`
   - Flattens into `dbx_agent_lakebase.rag.docs_json` table
   - Schema: doc_id, product, lang, category, title, source_uri, body, faqs, metadata

3. **chunk_json** (SQL)
   - Calls `ai_prep_search(body)` to chunk JSON documents
   - Explodes `document.contents[]` array
   - Creates `dbx_agent_lakebase.rag.docs_chunks` with: id, source_uri, product, lang, category, chunk_pos, chunk_to_retrieve, chunk_to_embed, metadata

4. **parse_pdf** (SQL)
   - Reads binary PDFs using `read_files(..., format => 'binaryFile')`
   - Calls `ai_parse_document(content)` to extract elements
   - Creates `dbx_agent_lakebase.rag.docs_parsed` with: id, path, filename, product, lang, parsed VARIANT, extracted_text
   - Derives product/language from filename (e.g., `sentiva-shield-datasheet-en.pdf` → product=Sentiva Shield, lang=en)

5. **chunk_pdf** (SQL)
   - Calls `ai_prep_search(parsed)` on the VARIANT output from parse_pdf
   - Appends to `docs_chunks` with category='datasheet'

6. **embed_and_load** (Python)
   - Reads all chunks from `docs_chunks` via Spark or SDK
   - Batches chunks (50 at a time) and calls embedding endpoint
   - UPSERTs into Lakebase `kb.documents` table via psycopg3
   - Creates vector index (cosine similarity) and BM25 text search index
   - Runs ANALYZE on the table

## Prerequisites

### Workspace/Cluster Setup

- **Warehouse**: Serverless SQL warehouse id: `45f87476ae315351`
- **Embedding Endpoint**: `databricks-qwen3-embedding-0-6b`
  - OpenAI-style POST endpoint
  - Input: `{"input": ["text1", "text2", ...]}`
  - Output: `{"data": [{"embedding": [...1024 floats...]}]}`
  - Dimension: 1024

### Databricks Features

- **ai_parse_document** (Beta): Requires workspace-level preview toggle
  - Converts binary PDFs to structured VARIANT
  - Returns: `{document.elements[], document.pages[]}`
  
- **ai_prep_search** (Beta): Requires workspace-level preview toggle
  - Input: VARIANT (from ai_parse_document) OR STRING (document text)
  - Output: `{document.contents[]}` where each element has:
    - `chunk_id`, `chunk_position`, `chunk_to_retrieve`, `chunk_to_embed`, `metadata`, `pages`
  - Handles context-aware chunking and enrichment

### Lakebase Setup

- **Project**: `sentiva-rag`
- **Table**: `kb.documents` (already exists)
  - Schema: `(id TEXT PK, source_uri TEXT, product TEXT, lang TEXT, category TEXT, chunk_pos INT, content TEXT, embedding vector(1024), metadata JSONB, created_at TIMESTAMPTZ, content_tsv tsvector GENERATED)`
  - Extensions: `lakebase_vector`, `lakebase_text` (both enabled)
  - Index types: `lakebase_ann` (vector), `lakebase_bm25` (text search)

- **Connection**: Configure via environment variables or Databricks profile
  - `PGHOST`: Lakebase endpoint host (get via `databricks postgres get-endpoint ...`)
  - `PGUSER`: Current user's email
  - `PGPASSWORD`: Fresh credential (get via `databricks postgres generate-database-credential ...`)
  - `PGDATABASE`: `databricks_postgres`
  - `PGSSLMODE`: `require`

### Python Dependencies

```bash
pip install -r src/jobs/requirements.txt
# For PDF generation (optional):
pip install reportlab
```

## Running the Pipeline

### Deploy the Bundle

```bash
# Deploy DAB to dev workspace
databricks bundle deploy -t dev --profile DEFAULT

# Validate the deployment
databricks bundle validate -t dev --profile DEFAULT
```

### Run the Job

```bash
# Run the full ingestion pipeline
databricks bundle run sentiva_ingest -t dev --profile DEFAULT

# Or run via databricks CLI:
databricks jobs run-now --job-id <job_id> --profile DEFAULT
```

### Monitor Progress

```bash
# Check job status
databricks jobs get-run --run-id <run_id> --profile DEFAULT

# View job logs
databricks jobs get-run-output --run-id <run_id> --profile DEFAULT
```

## File Organization

```
src/jobs/
├── sql/
│   ├── 01_load_json.sql       # Load JSON documents
│   ├── 02_chunk_json.sql      # Chunk JSON using ai_prep_search
│   ├── 03_parse_pdf.sql       # Parse PDFs and extract text
│   └── 04_chunk_pdf.sql       # Chunk PDFs and append to docs_chunks
├── embed_and_load.py          # Embedding + Lakebase loader
├── generate_data.py           # Data generation wrapper
├── requirements.txt           # Python dependencies
└── README.md                  # This file

resources/
└── ingest.job.yml            # DAB job definition

src/data_gen/
├── generate_docs.py          # JSON doc generator (48 docs, 4 languages)
└── generate_pdfs.py          # PDF generator (3 PDFs with tables)
```

## Troubleshooting

### Issue: `ai_prep_search` function not found
- The function requires a workspace-level preview toggle
- Contact Databricks Support to enable it

### Issue: `ai_parse_document` not found
- Same as above; requires preview toggle

### Issue: Embedding endpoint connection fails
- Verify the endpoint name: `databricks-qwen3-embedding-0-6b`
- Check workspace host in `.databricks/config`
- Ensure OAuth token is valid: `databricks auth token`

### Issue: Lakebase connection fails
- Verify endpoint details:
  ```bash
  databricks postgres get-endpoint sentiva-rag -o json
  ```
- Generate fresh credentials:
  ```bash
  databricks postgres generate-database-credential sentiva-rag -o json
  ```
- Check network connectivity to Lakebase endpoint

### Issue: Vector index creation fails
- Verify `lakebase_vector` extension is enabled
- Check pgvector format: must be `'[1.0, 2.0, ...]'::vector`

## Data Flow

```
Raw Documents (Volume)
├── raw_json/
│   └── *.json (48 files, 4 languages)
│        ↓
│   docs_json (Delta table)
│        ↓
│   docs_chunks (Delta table)
│
└── raw_pdf/
    └── *.pdf (3 files)
         ↓
    docs_parsed (Delta table with VARIANT)
         ↓
    docs_chunks (Delta table, appended)

docs_chunks (Delta table with all chunks)
     ↓
Embedding Endpoint (batch API)
     ↓
kb.documents (Lakebase)
     ↓
Vector Index + BM25 Index
```

## Notes

- The pipeline is idempotent: running it multiple times will replace tables and UPSERT into Lakebase
- Chunks are identified by `<doc_id>#<chunk_position>` to avoid duplicates
- Metadata includes original JSON metadata + extraction context from PDFs
- All timestamps use `current_timestamp()` for consistency
- UTF-8 encoding is fully supported for multilingual content

## Related Documentation

- Databricks AI Functions: https://docs.databricks.com/en/genai/ai-functions/index.html
- Lakebase (Postgres Autoscaling): https://docs.databricks.com/en/lakebase/index.html
- Vector Search + Embeddings: https://docs.databricks.com/en/generative-ai/embeddings/index.html
