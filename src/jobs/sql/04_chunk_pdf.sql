-- Step 4: Semantic chunking of parsed PDFs with ai_prep_search(parsed) -> append docs_chunks.
INSERT INTO dbx_agent_lakebase.rag.docs_chunks
SELECT
  CONCAT(prepped.doc_id, '#', c.value:chunk_position::int) AS id,
  prepped.source_path AS source_uri,
  prepped.product,
  prepped.lang,
  prepped.category,
  c.value:chunk_position::int          AS chunk_pos,
  c.value:chunk_to_retrieve::string    AS chunk_to_retrieve,
  c.value:chunk_to_embed::string       AS chunk_to_embed,
  to_json(c.value:metadata)            AS metadata
FROM (
  SELECT id AS doc_id, source_path, product, lang, category, ai_prep_search(parsed) AS ps
  FROM dbx_agent_lakebase.rag.docs_parsed
  WHERE parsed IS NOT NULL
) AS prepped,
LATERAL variant_explode(prepped.ps:document:contents) AS c;
