"""Lakebase (Postgres) connection helper with OAuth token refresh.

Connection values come from env vars injected by the app's `postgres` resource:
  PGHOST, PGDATABASE (default databricks_postgres), PGUSER, PGSSLMODE (require).
The password is a short-lived OAuth token. We prefer an injected PGPASSWORD; if
absent/expired we regenerate one via the Databricks SDK for the endpoint named by
LAKEBASE_ENDPOINT. Connections are recreated on auth failure.
"""
import os
import threading
import psycopg

_LOCK = threading.Lock()
_CONN = None


def _endpoint_path() -> str:
    return os.getenv("LAKEBASE_ENDPOINT",
                     "projects/sentiva-rag/branches/production/endpoints/primary")


def _fresh_token() -> str:
    """Generate a Lakebase (Autoscaling) credential via the postgres credentials REST API.
    Version-robust: uses the raw api_client. Falls back to PGPASSWORD env if present."""
    from databricks.sdk import WorkspaceClient
    ep = _endpoint_path()
    try:
        w = WorkspaceClient()
        resp = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": ep})
        tok = resp.get("token") if isinstance(resp, dict) else getattr(resp, "token", None)
        if tok:
            return tok
    except Exception as e:
        fb = os.getenv("PGPASSWORD")
        if fb:
            return fb
        raise RuntimeError(f"Lakebase credential generation failed for endpoint '{ep}': {e}")
    fb = os.getenv("PGPASSWORD")
    if fb:
        return fb
    raise RuntimeError("No Lakebase credential returned and PGPASSWORD not set.")


def _connect():
    host = os.environ["PGHOST"]
    db = os.getenv("PGDATABASE", "databricks_postgres")
    user = os.environ["PGUSER"]
    sslmode = os.getenv("PGSSLMODE", "require")
    return psycopg.connect(host=host, dbname=db, user=user, password=_fresh_token(),
                           sslmode=sslmode, connect_timeout=15)


def get_conn():
    """Return a live connection, (re)connecting if needed."""
    global _CONN
    with _LOCK:
        if _CONN is None or _CONN.closed:
            _CONN = _connect()
        else:
            try:
                with _CONN.cursor() as c:
                    c.execute("SELECT 1")
            except Exception:
                try:
                    _CONN.close()
                except Exception:
                    pass
                _CONN = _connect()
        return _CONN


def run_query(sql: str, params=None):
    """Execute a read query with one reconnect-on-auth-failure retry."""
    for attempt in range(2):
        try:
            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute(sql, params or {})
                cols = [d.name for d in cur.description] if cur.description else []
                rows = cur.fetchall() if cur.description else []
                return [dict(zip(cols, r)) for r in rows]
        except psycopg.OperationalError:
            global _CONN
            with _LOCK:
                _CONN = None
            if attempt == 1:
                raise


def execute(sql: str, params=None):
    for attempt in range(2):
        try:
            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute(sql, params or {})
            conn.commit()
            return
        except psycopg.OperationalError:
            global _CONN
            with _LOCK:
                _CONN = None
            if attempt == 1:
                raise
