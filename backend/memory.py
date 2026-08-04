"""
memory.py — Long-term persistent memory for J.A.R.V.I.S.

Architecture:
  - SQLite for durable storage (facts, preferences, tasks, reminders, chat history)
  - Optional sentence-transformers for semantic similarity search
  - In-memory cache for fast recent access
  - Thread-safe for use across async/sync contexts
"""

import os
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# ── Optional: semantic embeddings ────────────────────────────────────────────
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.db")

_lock = threading.Lock()

# ── Schema ────────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL DEFAULT 'general',
    key         TEXT,
    value       TEXT NOT NULL,
    embedding   BLOB,
    importance  INTEGER DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL UNIQUE,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'pending',
    priority    INTEGER DEFAULT 3,
    due_at      TEXT,
    created_at  TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    remind_at   TEXT NOT NULL,
    fired       INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'active',
    metadata    TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(remind_at, fired);
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_sessions(session_id);
"""


def _now() -> str:
    return datetime.utcnow().isoformat()


class MemoryEngine:
    """Thread-safe SQLite-backed long-term memory for J.A.R.V.I.S."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._embed_model = None
        self._init_db()
        if SEMANTIC_AVAILABLE:
            try:
                self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                pass

    def _conn(self) -> sqlite3.Connection:
        """Per-thread DB connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        with _lock:
            conn = sqlite3.connect(self.db_path)
            conn.executescript(SCHEMA)
            conn.commit()
            conn.close()

    def _embed(self, text: str) -> Optional[bytes]:
        if self._embed_model and text:
            try:
                import numpy as np
                vec = self._embed_model.encode([text])[0]
                return vec.astype("float32").tobytes()
            except Exception:
                pass
        return None

    def _cosine(self, a: bytes, b: bytes) -> float:
        try:
            import numpy as np
            va = np.frombuffer(a, dtype="float32")
            vb = np.frombuffer(b, dtype="float32")
            denom = (np.linalg.norm(va) * np.linalg.norm(vb))
            if denom == 0:
                return 0.0
            return float(np.dot(va, vb) / denom)
        except Exception:
            return 0.0

    # ── Facts ──────────────────────────────────────────────────────────────────

    def remember(self, value: str, category: str = "general", key: str = "", importance: int = 1) -> int:
        """Store a fact. Returns the new row ID."""
        emb = self._embed(value)
        now = _now()
        with _lock:
            cur = self._conn().execute(
                "INSERT INTO facts (category, key, value, embedding, importance, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (category, key or None, value, emb, importance, now, now)
            )
            self._conn().commit()
            return cur.lastrowid

    def recall(self, query: str, limit: int = 5, category: str = "") -> List[Dict]:
        """Semantic search over stored facts. Falls back to keyword search."""
        q_emb = self._embed(query)
        with _lock:
            if category:
                rows = self._conn().execute(
                    "SELECT * FROM facts WHERE category = ? ORDER BY importance DESC, updated_at DESC LIMIT 100",
                    (category,)
                ).fetchall()
            else:
                rows = self._conn().execute(
                    "SELECT * FROM facts ORDER BY importance DESC, updated_at DESC LIMIT 200"
                ).fetchall()

        if not rows:
            return []

        results = []
        for row in rows:
            r = dict(row)
            score = 0.0
            if q_emb and r.get("embedding"):
                score = self._cosine(q_emb, r["embedding"])
            else:
                # Keyword fallback
                if query.lower() in (r.get("value") or "").lower():
                    score = 0.5
            r["_score"] = score
            results.append(r)

        results.sort(key=lambda x: x["_score"], reverse=True)
        return [
            {
                "id": r["id"],
                "category": r["category"],
                "key": r.get("key"),
                "value": r["value"],
                "importance": r["importance"],
                "created_at": r["created_at"],
                "score": round(r["_score"], 3),
            }
            for r in results[:limit]
        ]

    def forget(self, fact_id: int) -> bool:
        with _lock:
            self._conn().execute("DELETE FROM facts WHERE id = ?", (fact_id,))
            self._conn().commit()
        return True

    def list_facts(self, category: str = "", limit: int = 50) -> List[Dict]:
        with _lock:
            if category:
                rows = self._conn().execute(
                    "SELECT id, category, key, value, importance, created_at FROM facts "
                    "WHERE category = ? ORDER BY importance DESC, updated_at DESC LIMIT ?",
                    (category, limit)
                ).fetchall()
            else:
                rows = self._conn().execute(
                    "SELECT id, category, key, value, importance, created_at FROM facts "
                    "ORDER BY importance DESC, updated_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    # ── Preferences ───────────────────────────────────────────────────────────

    def set_preference(self, key: str, value: Any):
        val_str = json.dumps(value) if not isinstance(value, str) else value
        with _lock:
            self._conn().execute(
                "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, val_str, _now())
            )
            self._conn().commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        with _lock:
            row = self._conn().execute(
                "SELECT value FROM preferences WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]

    def all_preferences(self) -> Dict[str, Any]:
        with _lock:
            rows = self._conn().execute("SELECT key, value FROM preferences").fetchall()
        result = {}
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value"])
            except Exception:
                result[r["key"]] = r["value"]
        return result

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def add_task(self, title: str, description: str = "", priority: int = 3, due_at: str = "") -> int:
        now = _now()
        with _lock:
            cur = self._conn().execute(
                "INSERT INTO tasks (title, description, priority, due_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (title, description, priority, due_at or None, now)
            )
            self._conn().commit()
            return cur.lastrowid

    def complete_task(self, task_id: int) -> bool:
        with _lock:
            self._conn().execute(
                "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
                (_now(), task_id)
            )
            self._conn().commit()
        return True

    def get_tasks(self, status: str = "pending") -> List[Dict]:
        with _lock:
            rows = self._conn().execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY priority ASC, due_at ASC",
                (status,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_task(self, task_id: int) -> bool:
        with _lock:
            self._conn().execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._conn().commit()
        return True

    # ── Reminders ─────────────────────────────────────────────────────────────

    def add_reminder(self, text: str, remind_at: str) -> int:
        """remind_at should be ISO datetime string."""
        with _lock:
            cur = self._conn().execute(
                "INSERT INTO reminders (text, remind_at, created_at) VALUES (?, ?, ?)",
                (text, remind_at, _now())
            )
            self._conn().commit()
            return cur.lastrowid

    def get_due_reminders(self) -> List[Dict]:
        now = _now()
        with _lock:
            rows = self._conn().execute(
                "SELECT * FROM reminders WHERE fired = 0 AND remind_at <= ? ORDER BY remind_at ASC",
                (now,)
            ).fetchall()
        return [dict(r) for r in rows]

    def fire_reminder(self, reminder_id: int):
        with _lock:
            self._conn().execute(
                "UPDATE reminders SET fired = 1 WHERE id = ?", (reminder_id,)
            )
            self._conn().commit()

    def list_reminders(self, include_fired: bool = False) -> List[Dict]:
        with _lock:
            if include_fired:
                rows = self._conn().execute(
                    "SELECT * FROM reminders ORDER BY remind_at ASC"
                ).fetchall()
            else:
                rows = self._conn().execute(
                    "SELECT * FROM reminders WHERE fired = 0 ORDER BY remind_at ASC"
                ).fetchall()
        return [dict(r) for r in rows]

    # ── Chat history ──────────────────────────────────────────────────────────

    def save_message(self, session_id: str, role: str, content: str):
        with _lock:
            self._conn().execute(
                "INSERT INTO chat_sessions (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, _now())
            )
            self._conn().commit()

    def get_history(self, session_id: str, limit: int = 30) -> List[Dict]:
        with _lock:
            rows = self._conn().execute(
                "SELECT role, content, timestamp FROM chat_sessions "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_all_sessions(self) -> List[str]:
        with _lock:
            rows = self._conn().execute(
                "SELECT DISTINCT session_id FROM chat_sessions ORDER BY rowid DESC LIMIT 50"
            ).fetchall()
        return [r["session_id"] for r in rows]

    # ── Projects ──────────────────────────────────────────────────────────────

    def add_project(self, name: str, description: str = "", metadata: dict = None) -> int:
        now = _now()
        with _lock:
            cur = self._conn().execute(
                "INSERT INTO projects (name, description, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (name, description, json.dumps(metadata or {}), now, now)
            )
            self._conn().commit()
            return cur.lastrowid

    def get_projects(self, status: str = "active") -> List[Dict]:
        with _lock:
            rows = self._conn().execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC",
                (status,)
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["metadata"] = json.loads(d.get("metadata") or "{}")
            except Exception:
                d["metadata"] = {}
            result.append(d)
        return result

    # ── Context builder for AI ─────────────────────────────────────────────────

    def build_context_summary(self) -> str:
        """Build a compact context string to inject into AI system prompt."""
        lines = []

        prefs = self.all_preferences()
        if prefs:
            lines.append("[User Preferences]")
            for k, v in list(prefs.items())[:10]:
                lines.append(f"  {k}: {v}")

        tasks = self.get_tasks("pending")[:5]
        if tasks:
            lines.append("[Pending Tasks]")
            for t in tasks:
                lines.append(f"  - {t['title']}")

        reminders = self.list_reminders()[:3]
        if reminders:
            lines.append("[Upcoming Reminders]")
            for r in reminders:
                lines.append(f"  - {r['text']} at {r['remind_at']}")

        facts = self.list_facts(limit=10)
        if facts:
            lines.append("[Remembered Facts]")
            for f in facts:
                lines.append(f"  [{f['category']}] {f['value']}")

        return "\n".join(lines)

    def stats(self) -> Dict:
        with _lock:
            facts_count = self._conn().execute("SELECT COUNT(*) as c FROM facts").fetchone()["c"]
            tasks_count = self._conn().execute("SELECT COUNT(*) as c FROM tasks WHERE status='pending'").fetchone()["c"]
            reminders_count = self._conn().execute("SELECT COUNT(*) as c FROM reminders WHERE fired=0").fetchone()["c"]
            sessions_count = self._conn().execute("SELECT COUNT(DISTINCT session_id) as c FROM chat_sessions").fetchone()["c"]
        return {
            "facts": facts_count,
            "pending_tasks": tasks_count,
            "active_reminders": reminders_count,
            "chat_sessions": sessions_count,
            "semantic_search": SEMANTIC_AVAILABLE and self._embed_model is not None,
        }


# Singleton
memory = MemoryEngine()
