"""
OPUS Agent v2 - Sessions Store with enriched schema.

Schema v2:
- sessions: id, name, provider, model, created_at, updated_at, total_tokens, metadata(JSON)
- messages: id, session_id(FK), role, content, tokens, created_at
- messages_fts: Virtual table for full-text search
"""

import sqlite3
import secrets
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from .config_v2 import get_db_path

DB_FILE = get_db_path()

SCHEMA_V2 = """
-- Sessions table with enriched metadata
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    provider TEXT,
    model TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    total_tokens INTEGER DEFAULT 0,
    metadata JSON
);

-- Messages table with token tracking
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

-- Index for fast session message lookup
CREATE INDEX IF NOT EXISTS ix_messages_session ON messages(session_id);

-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    session_id, role, content,
    content='messages', content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, session_id, role, content)
    VALUES (new.id, new.session_id, new.role, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, session_id, role, content)
    VALUES ('delete', old.id, old.session_id, old.role, old.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, session_id, role, content)
    VALUES ('delete', old.id, old.session_id, old.role, old.content);
    INSERT INTO messages_fts(rowid, session_id, role, content)
    VALUES (new.id, new.session_id, new.role, new.content);
END;

-- Migration: add missing columns if they don't exist
-- SQLite doesn't support IF NOT EXISTS for columns, so we use a workaround
"""


class SessionStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DB_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_V2)
        self._migrate_schema()

    def _migrate_schema(self):
        """Adiciona colunas faltantes no schema existente."""
        with self._conn() as conn:
            # Verifica quais colunas existem
            cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            
            migrations = [
                ("provider", "TEXT"),
                ("model", "TEXT"),
                ("updated_at", "REAL NOT NULL DEFAULT 0"),
                ("total_tokens", "INTEGER DEFAULT 0"),
                ("metadata", "JSON"),
            ]
            
            for col_name, col_type in migrations:
                if col_name not in cols:
                    try:
                        conn.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}")
                    except sqlite3.OperationalError:
                        pass  # Coluna já existe
            
            # Atualiza updated_at onde for 0
            conn.execute("UPDATE sessions SET updated_at=created_at WHERE updated_at=0")
            
            # Verifica messages table
            msg_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
            if "tokens" not in msg_cols:
                try:
                    conn.execute("ALTER TABLE messages ADD COLUMN tokens INTEGER DEFAULT 0")
                except sqlite3.OperationalError:
                    pass

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create(self, provider: str = "", model: str = "") -> str:
        """Cria nova sessão com provider/model opcionais."""
        with self._conn() as conn:
            for _ in range(20):
                sid = secrets.token_hex(4)  # 8 chars = 4.3B combinations
                if not conn.execute(
                    "SELECT 1 FROM sessions WHERE id=?", (sid,)
                ).fetchone():
                    now = time.time()
                    conn.execute(
                        """INSERT INTO sessions (id, name, provider, model, created_at, updated_at) 
                           VALUES (?, '', ?, ?, ?, ?)""",
                        (sid, provider, model, now, now),
                    )
                    return sid
        raise RuntimeError("falha ao gerar id de sessao")

    def ensure_name(self, session_id: str, first_message: str) -> None:
        name = " ".join(first_message.split())[:64]
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET name=?, updated_at=? WHERE id=? AND name=''",
                (name, time.time(), session_id),
            )

    def add_message(self, session_id: str, role: str, content: str, tokens: int = 0) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO messages (session_id, role, content, tokens, created_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, role, content, tokens, time.time()),
            )
            # Update session updated_at and token count
            conn.execute(
                "UPDATE sessions SET updated_at=?, total_tokens=total_tokens+? WHERE id=?",
                (time.time(), tokens, session_id),
            )

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            sql = "SELECT role, content, tokens, created_at FROM messages WHERE session_id=? ORDER BY id"
            if limit:
                sql += f" LIMIT {limit}"
            rows = conn.execute(sql, (session_id,)).fetchall()
        return [{"role": r["role"], "content": r["content"], "tokens": r["tokens"], "created_at": r["created_at"]} for r in rows]

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT s.id, s.name, s.provider, s.model, s.created_at, s.updated_at, 
                          s.total_tokens, COUNT(m.id) AS n_msgs
                   FROM sessions s
                   LEFT JOIN messages m ON m.session_id = s.id
                   GROUP BY s.id
                   HAVING n_msgs > 0
                   ORDER BY s.updated_at DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, name, provider, model, created_at, updated_at, total_tokens, metadata FROM sessions WHERE id=?",
                (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete(self, session_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            return cur.rowcount > 0

    def search_messages(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Busca full-text nas mensagens."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT m.session_id, m.role, m.content, m.created_at, s.name as session_name
                   FROM messages_fts f
                   JOIN messages m ON m.id = f.rowid
                   JOIN sessions s ON s.id = m.session_id
                   WHERE messages_fts MATCH ?
                   ORDER BY m.created_at DESC
                   LIMIT ?""",
                (query, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_session_metadata(self, session_id: str, metadata: Dict[str, Any]) -> None:
        """Atualiza metadata JSON da sessão."""
        with self._conn() as conn:
            existing = conn.execute("SELECT metadata FROM sessions WHERE id=?", (session_id,)).fetchone()
            current = json.loads(existing["metadata"]) if existing and existing["metadata"] else {}
            current.update(metadata)
            conn.execute(
                "UPDATE sessions SET metadata=?, updated_at=? WHERE id=?",
                (json.dumps(current), time.time(), session_id)
            )

    def get_session_with_messages(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retorna sessão completa com todas as mensagens."""
        session = self.get(session_id)
        if not session:
            return None
        session["messages"] = self.get_messages(session_id)
        return session

    def export_session(self, session_id: str, output_path: Path) -> bool:
        """Exporta sessão para JSON (backup)."""
        data = self.get_session_with_messages(session_id)
        if not data:
            return False
        try:
            output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False


def migrate_v1_to_v2(v1_db_path: Path, v2_store: SessionStore) -> bool:
    """Migra sessões do schema v1 para v2."""
    if not v1_db_path.exists():
        return False
    
    try:
        with sqlite3.connect(v1_db_path) as src:
            src.row_factory = sqlite3.Row
            # Migra sessions
            sessions = src.execute("SELECT id, name, created_at FROM sessions").fetchall()
            with v2_store._conn() as dst:
                for s in sessions:
                    dst.execute(
                        """INSERT OR IGNORE INTO sessions (id, name, created_at, updated_at) 
                           VALUES (?, ?, ?, ?)""",
                        (s["id"], s["name"], s["created_at"], s["created_at"])
                    )
                
                # Migra messages
                messages = src.execute(
                    "SELECT session_id, role, content, created_at FROM messages ORDER BY id"
                ).fetchall()
                for m in messages:
                    dst.execute(
                        """INSERT INTO messages (session_id, role, content, created_at) 
                           VALUES (?, ?, ?, ?)""",
                        (m["session_id"], m["role"], m["content"], m["created_at"])
                    )
        return True
    except Exception as e:
        print(f"Erro na migracao de sessoes: {e}")
        return False


if __name__ == "__main__":
    store = SessionStore()
    sid = store.create("anthropic", "claude-3-5-sonnet-20241022")
    print(f"Created session: {sid}")
    store.ensure_name(sid, "primeira mensagem do usuario")
    store.add_message(sid, "user", "ola mundo", tokens=10)
    store.add_message(sid, "assistant", "ola! como posso ajudar?", tokens=15)
    
    sessions = store.list_sessions()
    print(f"Sessions: {sessions}")
    
    msgs = store.get_messages(sid)
    print(f"Messages: {msgs}")