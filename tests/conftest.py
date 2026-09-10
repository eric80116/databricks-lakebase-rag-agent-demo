"""Shared fixtures for the Sentiva RAG test suite. Reads config.env; uses the
databricks CLI + HTTP so it runs from a laptop with a configured profile."""
import json
import os
import re
import subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_config():
    cfg, path = {}, os.path.join(ROOT, "config.env")
    if os.path.exists(path):
        for line in open(path):
            m = re.match(r'\s*export\s+(\w+)="?([^"\n]*)"?', line)
            if m:
                cfg[m.group(1)] = m.group(2)
    return cfg


CFG = _load_config()


def sh(args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


@pytest.fixture(scope="session")
def cfg():
    return CFG


@pytest.fixture(scope="session")
def profile():
    return CFG.get("PROFILE", "DEFAULT")


@pytest.fixture(scope="session")
def host(profile):
    data = json.loads(sh(["databricks", "auth", "env", "--profile", profile]))

    def find(o):
        if isinstance(o, dict):
            if "DATABRICKS_HOST" in o:
                return o["DATABRICKS_HOST"]
            for v in o.values():
                r = find(v)
                if r:
                    return r
        return None

    h = find(data)
    assert h, "DATABRICKS_HOST not found in `databricks auth env`"
    return h.rstrip("/")


@pytest.fixture(scope="session")
def token(profile):
    return json.loads(sh(["databricks", "auth", "token", "--profile", profile]))["access_token"]


def q(sql, profile):
    """Run a SQL query via the CLI aitools tool; return list-of-dicts (or [])."""
    out = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", sql, "--profile", profile],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(out.stdout)
        return d if isinstance(d, list) else []
    except Exception:
        return []


def app_url(name, profile):
    out = sh(["databricks", "apps", "get", name, "--profile", profile, "-o", "json"])
    return json.loads(out).get("url", "").rstrip("/")
