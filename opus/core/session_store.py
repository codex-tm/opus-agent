"""OPUS Agent - Armazem de sessoes em SQLite (arquivo binario, ~/.opus/sessions.db).

Nao e JSON editavel: schema + integridade via sqlite3 (stdlib). Cada sessao
tem id curto unico, nome (primeira mensagem do usuario) e historico completo.
"""

import secrets
import sqlite3
import time
from pathlib import Path

DB_PATH = Path.home() / ".opus" / "sessions.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_messages_session ON messages(session_id);
"""


class SessionStore:
    def __init__(self, path: "Path | None" = None):
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(_SCHEMA)

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create(self) -> str:
        with self._conn() as conn:
            for _ in range(20):
                sid = secrets.token_hex(3)  # 6 chars
                if not conn.execute(
                    "SELECT 1 FROM sessions WHERE id=?", (sid,)
                ).fetchone():
                    conn.execute(
                        "INSERT INTO sessions (id, name, created_at) VALUES (?, '', ?)",
                        (sid, time.time()),
                    )
                    return sid
        raise RuntimeError("falha ao gerar id de sessao")

    def ensure_name(self, session_id: str, first_message: str) -> None:
        name = " ".join(first_message.split())[:48]
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET name=? WHERE id=? AND name=''",
                (name, session_id),
            )

    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, time.time()),
            )

    def get_messages(self, session_id: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def list_sessions(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT s.id, s.name, s.created_at, COUNT(m.id) AS n_msgs
                   FROM sessions s
                   LEFT JOIN messages m ON m.session_id = s.id
                   GROUP BY s.id
                   HAVING n_msgs > 0
                   ORDER BY s.created_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, session_id: str) -> "dict | None":
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, name, created_at FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
        return dict(row) if row else None
