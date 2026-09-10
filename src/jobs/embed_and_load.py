#!/usr/bin/env python3
"""Embed docs_chunks (Qwen3) and UPSERT into Lakebase kb.documents + build indexes.

Serverless job task. Args (from the DAB job, all portable via ${var.*}):
  --catalog --schema --embedding-endpoint --lakebase-endpoint
Reads chunks via Spark; embeds via the serving endpoint REST; writes to Lakebase
with psycopg3; Lakebase token via POST /api/2.0/postgres/credentials.
"""
import argparse
import logging
import requests
import psycopg
from databricks.sdk import WorkspaceClient
from pyspark.sql import SparkSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("embed_and_load")

p = argparse.ArgumentParser()
p.add_argument("--catalog", default="dbx_agent_lakebase")
p.add_argument("--schema", default="rag")
p.add_argument("--embedding-endpoint", default="databricks-qwen3-embedding-0-6b")
p.add_argument("--lakebase-endpoint", default="projects/sentiva-rag/branches/production/endpoints/primary")
p.add_argument("--batch", type=int, default=40)
args, _ = p.parse_known_args()

CATALOG, SCHEMA = args.catalog, args.schema
CHUNKS_TABLE = f"{CATALOG}.{SCHEMA}.docs_chunks"

w = WorkspaceClient()
HOST = w.config.host.rstrip("/")


def _auth_header():
    return w.config.authenticate()  # {"Authorization": "Bearer ..."}


def embed(texts):
    r = requests.post(
        f"{HOST}/serving-endpoints/{args.embedding_endpoint}/invocations",
        headers={**_auth_header(), "Content-Type": "application/json"},
        json={"input": texts}, timeout=120,
    )
    r.raise_for_status()
    return [d["embedding"] for d in r.json()["data"]]


def lakebase_conn():
    ep_info = w.api_client.do("GET", f"/api/2.0/postgres/{args.lakebase_endpoint}")
    host = ep_info["status"]["hosts"]["host"]
    cred = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": args.lakebase_endpoint})
    token = cred["token"]
    me = w.current_user.me().user_name
    return psycopg.connect(host=host, dbname="databricks_postgres", user=me,
                           password=token, sslmode="require", connect_timeout=20)


def vlit(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def main():
    spark = SparkSession.builder.getOrCreate()
    rows = spark.table(CHUNKS_TABLE).select(
        "id", "source_uri", "product", "lang", "category", "chunk_pos",
        "chunk_to_retrieve", "chunk_to_embed", "metadata"
    ).collect()
    log.info("read %d chunks from %s", len(rows), CHUNKS_TABLE)
    if not rows:
        log.warning("no chunks; nothing to load")
        return

    conn = lakebase_conn()
    conn.autocommit = False
    upserted = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), args.batch):
            batch = rows[i:i + args.batch]
            vecs = embed([(r["chunk_to_embed"] or r["chunk_to_retrieve"] or " ") for r in batch])
            for r, v in zip(batch, vecs):
                cur.execute(
                    """INSERT INTO kb.documents
                         (id, source_uri, product, lang, category, chunk_pos, content, embedding, metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector,%s::jsonb)
                       ON CONFLICT (id) DO UPDATE SET
                         content=EXCLUDED.content, embedding=EXCLUDED.embedding,
                         product=EXCLUDED.product, lang=EXCLUDED.lang, category=EXCLUDED.category,
                         source_uri=EXCLUDED.source_uri, metadata=EXCLUDED.metadata""",
                    (r["id"], r["source_uri"], r["product"], r["lang"], r["category"],
                     int(r["chunk_pos"] or 0), r["chunk_to_retrieve"], vlit(v),
                     r["metadata"] if isinstance(r["metadata"], str) else "{}"),
                )
                upserted += 1
            conn.commit()
            log.info("upserted %d/%d", min(i + args.batch, len(rows)), len(rows))

    # Build KB search indexes (Lakebase Search) after load, then ANALYZE.
    with conn.cursor() as cur:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_ann ON kb.documents USING lakebase_ann (embedding vector_cosine_ops)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_bm25 ON kb.documents USING lakebase_bm25 (content_tsv)")
        cur.execute("ANALYZE kb.documents")
    conn.commit()
    conn.close()
    log.info("done: upserted %d rows + indexes", upserted)


main()
