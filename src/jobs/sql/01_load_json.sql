-- Step 1: Load multilingual JSON docs from the volume into a bronze Delta table.
-- Files are pretty-printed single-object JSON => multiLine => true. Columns are top-level.
CREATE OR REPLACE TABLE dbx_agent_lakebase.rag.docs_json AS
SELECT
  doc_id,
  product,
  lang,
  category,
  title,
  source_uri,
  body,
  to_json(faqs)     AS faqs,
  to_json(metadata) AS metadata,
  current_timestamp() AS loaded_at
FROM read_files(
  '/Volumes/dbx_agent_lakebase/rag/raw_docs/raw_json/',
  format => 'json',
  multiLine => true,
  recursiveFileLookup => true
)
WHERE doc_id IS NOT NULL;
