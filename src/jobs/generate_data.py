#!/usr/bin/env python3
"""Ensure Sentiva source docs (JSON + PDFs) exist in the volume.

Idempotent: if the volume already contains the docs (the common case — they are
uploaded at deploy time), this SKIPS generation and exits 0. Only if the volume
is empty does it try to (re)generate via the src/data_gen generators.

Runs as a Databricks serverless spark_python_task, where `__file__` is NOT defined,
so generator paths are resolved defensively (never at module import time).

Env: VOLUME_BASE (default /Volumes/dbx_agent_lakebase/rag/raw_docs)
"""
import os
import sys
import glob
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("generate_data")

VOLUME_BASE = os.getenv("VOLUME_BASE", "/Volumes/dbx_agent_lakebase/rag/raw_docs")
JSON_DIR = os.path.join(VOLUME_BASE, "raw_json")
PDF_DIR = os.path.join(VOLUME_BASE, "raw_pdf")


def _repo_root():
    """Best-effort locate the repo root (dir containing src/data_gen) without __file__."""
    candidates = []
    argv0 = sys.argv[0] if sys.argv and sys.argv[0] else ""
    if argv0:
        candidates.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(argv0)))))
    candidates.append(os.getcwd())
    # Walk up from cwd looking for src/data_gen
    d = os.getcwd()
    for _ in range(6):
        candidates.append(d)
        d = os.path.dirname(d)
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "src", "data_gen")):
            return c
    return None


def _generate():
    root = _repo_root()
    if not root:
        raise RuntimeError("Cannot locate src/data_gen to generate docs; upload docs to the volume instead.")
    os.makedirs(JSON_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)
    docs_py = os.path.join(root, "src", "data_gen", "generate_docs.py")
    pdfs_py = os.path.join(root, "src", "data_gen", "generate_pdfs.py")
    log.info("Generating JSON docs -> %s", JSON_DIR)
    subprocess.run([sys.executable, docs_py, "--out", JSON_DIR], check=True)
    try:
        import reportlab  # noqa: F401
        log.info("Generating PDFs -> %s", PDF_DIR)
        subprocess.run([sys.executable, pdfs_py, "--out", PDF_DIR], check=True)
    except ImportError:
        log.warning("reportlab not installed; skipping PDF generation.")


def main():
    os.makedirs(JSON_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)
    n_json = len(glob.glob(os.path.join(JSON_DIR, "*.json")))
    n_pdf = len(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    log.info("Volume check: %d JSON, %d PDF in %s", n_json, n_pdf, VOLUME_BASE)
    if n_json >= 40 and n_pdf >= 3:
        log.info("Docs already present in volume — skipping generation (idempotent).")
        return
    log.info("Docs missing/incomplete — generating.")
    _generate()
    log.info("Done. JSON=%d PDF=%d",
             len(glob.glob(os.path.join(JSON_DIR, "*.json"))),
             len(glob.glob(os.path.join(PDF_DIR, "*.pdf"))))


main()
