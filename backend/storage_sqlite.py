from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StoredMessage:
    role: str
    content: str


class SQLiteStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._ensure_parent_dir()
        self._init_db()

    @property
    def db_path(self) -> str:
        return self._db_path

    def _ensure_parent_dir(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    system_prompt TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);")

    def get_or_create_session(self, session_id: str) -> str:
        if not session_id:
            raise ValueError("session_id_required")

        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, system_prompt) VALUES (?, ?)",
                (session_id, None),
            )
            conn.execute("UPDATE sessions SET updated_at=datetime('now') WHERE id=?", (session_id,))
        return session_id

    def set_system_prompt(self, session_id: str, system_prompt: str) -> None:
        self.get_or_create_session(session_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET system_prompt=?, updated_at=datetime('now') WHERE id=?",
                (system_prompt, session_id),
            )

    def get_system_prompt(self, session_id: str) -> Optional[str]:
        if not session_id:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT system_prompt FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                return None
            return row["system_prompt"]

    def append_message(self, session_id: str, role: str, content: str) -> None:
        self.get_or_create_session(session_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            conn.execute("UPDATE sessions SET updated_at=datetime('now') WHERE id=?", (session_id,))

    def get_recent_messages(self, session_id: str, limit: int) -> List[StoredMessage]:
        if not session_id:
            return []
        limit = max(0, int(limit))
        if limit == 0:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()

        rows = list(reversed(rows))
        return [StoredMessage(role=r["role"], content=r["content"]) for r in rows]

    def export_session(self, session_id: str, limit: int) -> Dict[str, object]:
        prompt = self.get_system_prompt(session_id)
        msgs = self.get_recent_messages(session_id, limit)
        return {
            "session_id": session_id,
            "system_prompt": prompt,
            "messages": [{"role": m.role, "content": m.content} for m in msgs],
        }
