-- Step 3: OCR/parse PDFs with ai_parse_document -> VARIANT (elements/tables/pages/layout).
-- binaryFile columns: path, content, length, modificationTime (no `filename`/`size`).
CREATE OR REPLACE TABLE dbx_agent_lakebase.rag.docs_parsed AS
SELECT
  md5(path)                                   AS id,
  path                                        AS source_path,
  element_at(split(path, '/'), -1)            AS filename,
  CASE
    WHEN element_at(split(path, '/'), -1) LIKE '%shield%' THEN 'Sentiva Shield'
    WHEN element_at(split(path, '/'), -1) LIKE '%family%' THEN 'Sentiva Family'
    WHEN element_at(split(path, '/'), -1) LIKE '%plans%'  THEN 'Sentiva Plans'
    ELSE 'Sentiva Document'
  END                                         AS product,
  COALESCE(NULLIF(regexp_extract(element_at(split(path, '/'), -1), '-([a-z]{2})\\.pdf$', 1), ''), 'en') AS lang,
  'datasheet'                                 AS category,
  ai_parse_document(content)                  AS parsed,
  current_timestamp()                         AS parsed_at
FROM read_files(
  '/Volumes/dbx_agent_lakebase/rag/raw_docs/raw_pdf/',
  format => 'binaryFile',
  recursiveFileLookup => true
);
