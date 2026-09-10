"""Hybrid KB retrieval from Lakebase: pgvector/lakebase_ann (semantic) + tsvector (keyword)."""
import os
import requests
from databricks.sdk.core import Config
from lakebase import run_query

_cfg = Config()
EMBEDDING_ENDPOINT = os.getenv("EMBEDDING_ENDPOINT", "databricks-qwen3-embedding-0-6b")
_EMB_URL = f"{_cfg.host.rstrip('/')}/serving-endpoints/{EMBEDDING_ENDPOINT}/invocations"
K = int(os.getenv("K", "5"))


def _auth_headers():
    h = {"Content-Type": "application/json"}
    try:
        h.update(_cfg.authenticate())
    except Exception:
        tok = os.getenv("DATABRICKS_TOKEN")
        if tok:
            h["Authorization"] = f"Bearer {tok}"
    return h


def embed(text: str):
    resp = requests.post(_EMB_URL, headers=_auth_headers(), json={"input": [text]}, timeout=30)
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def _vec_literal(vec):
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def retrieve(query: str, k: int = None):
    """Return up to k KB chunks via vector search UNION keyword search (deduped)."""
    k = k or K
    qvec = _vec_literal(embed(query))

    vector_sql = """
        SELECT id, content, product, lang, source_uri, category,
               1 - (embedding <=> %(qvec)s::vector) AS score, 'vector' AS via
        FROM kb.documents
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %(qvec)s::vector
        LIMIT %(k)s
    """
    rows = run_query(vector_sql, {"qvec": qvec, "k": k})

    # Keyword pass (language-agnostic 'simple' config); merge + dedupe by id.
    try:
        kw_sql = """
            SELECT id, content, product, lang, source_uri, category,
                   ts_rank(content_tsv, websearch_to_tsquery('simple', %(q)s)) AS score,
                   'keyword' AS via
            FROM kb.documents
            WHERE content_tsv @@ websearch_to_tsquery('simple', %(q)s)
            ORDER BY score DESC
            LIMIT %(k)s
        """
        rows += run_query(kw_sql, {"q": query, "k": k})
    except Exception:
        pass

    seen, merged = set(), []
    for r in sorted(rows, key=lambda x: x.get("score") or 0, reverse=True):
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        merged.append(r)
        if len(merged) >= k:
            break
    return merged


def to_sources(rows):
    out = []
    for r in rows:
        title = f"{r.get('product') or 'Sentiva'} · {r.get('category') or 'info'}"
        out.append({
            "title": title,
            "source_uri": r.get("source_uri") or "",
            "product": r.get("product") or "",
            "lang": r.get("lang") or "",
        })
    return out


def context_block(rows):
    blocks = []
    for i, r in enumerate(rows, 1):
        blocks.append(f"[{i}] ({r.get('product')}, {r.get('lang')}) {r.get('content')}")
    return "\n\n".join(blocks)
