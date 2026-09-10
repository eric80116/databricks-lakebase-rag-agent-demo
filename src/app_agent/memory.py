"""Lakebase-backed chat memory (mem.chat_history), keyed by session_id."""
from lakebase import run_query, execute

MAX_TURNS = 6  # last N messages included as history


def load_history(session_id: str):
    rows = run_query(
        """SELECT role, content FROM mem.chat_history
           WHERE session_id = %(s)s ORDER BY id DESC LIMIT %(n)s""",
        {"s": session_id, "n": MAX_TURNS},
    )
    # returned newest-first; reverse to chronological
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def save_message(session_id: str, role: str, content: str):
    execute(
        """INSERT INTO mem.chat_history (session_id, role, content)
           VALUES (%(s)s, %(r)s, %(c)s)""",
        {"s": session_id, "r": role, "c": content},
    )
