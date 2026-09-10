-- Step 2: Semantic chunking of JSON docs with ai_prep_search(body) -> docs_chunks.
-- Databricks VARIANT: navigate with ':' and explode arrays with LATERAL variant_explode.
CREATE OR REPLACE TABLE dbx_agent_lakebase.rag.docs_chunks AS
SELECT
  CONCAT(prepped.doc_id, '#', c.value:chunk_position::int) AS id,
  prepped.source_uri,
  prepped.product,
  prepped.lang,
  prepped.category,
  c.value:chunk_position::int          AS chunk_pos,
  c.value:chunk_to_retrieve::string    AS chunk_to_retrieve,
  c.value:chunk_to_embed::string       AS chunk_to_embed,
  to_json(c.value:metadata)            AS metadata
FROM (
  SELECT doc_id, source_uri, product, lang, category, ai_prep_search(body) AS ps
  FROM dbx_agent_lakebase.rag.docs_json
  WHERE body IS NOT NULL
) AS prepped,
LATERAL variant_explode(prepped.ps:document:contents) AS c;
