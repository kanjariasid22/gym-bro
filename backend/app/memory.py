"""Agent memory: Cognis when available, Groq-backed local fallback otherwise.

Cognis local defaults need Gemini embeddings. With only GROQ_API_KEY we use a
disk-backed SQLite memory that matches the same scoping model
(owner_id / agent_id / session_id) so Guide/Trainer stay coherent.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import get_settings
from app.llm import LLMError, chat_json

_lock = Lock()


@dataclass
class MemoryScope:
    owner_id: str
    agent_id: str
    session_id: str


def planning_session_id(user_id: int) -> str:
    return f"planning-{user_id}"


def workout_session_id(session_id: int) -> str:
    return f"workout-{session_id}"


class LocalMemoryStore:
    """Simple persistent memory: messages + extracted facts, keyword search."""

    def __init__(self, data_dir: str) -> None:
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "local_memory.sqlite"
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                  id TEXT PRIMARY KEY,
                  owner_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS facts (
                  id TEXT PRIMARY KEY,
                  owner_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_msg_scope
                  ON messages(owner_id, agent_id, session_id);
                CREATE INDEX IF NOT EXISTS idx_fact_scope
                  ON facts(owner_id, agent_id);
                """
            )

    def add(
        self,
        messages: list[dict[str, str]],
        *,
        owner_id: str,
        agent_id: str,
        session_id: str,
        extract: bool = True,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with _lock, self._conn() as conn:
            for msg in messages:
                conn.execute(
                    "INSERT INTO messages(id, owner_id, agent_id, session_id, role, content, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        owner_id,
                        agent_id,
                        session_id,
                        msg.get("role", "user"),
                        msg.get("content", ""),
                        now,
                    ),
                )
            conn.commit()

        extracted: list[str] = []
        if extract:
            extracted = self._extract_facts(messages)
            with _lock, self._conn() as conn:
                for fact in extracted:
                    conn.execute(
                        "INSERT INTO facts(id, owner_id, agent_id, content, created_at) VALUES (?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), owner_id, agent_id, fact, now),
                    )
                conn.commit()

        return {"success": True, "message": f"Stored {len(messages)} messages", "facts": extracted}

    def _extract_facts(self, messages: list[dict[str, str]]) -> list[str]:
        blob = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        try:
            data = chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "Extract durable training-related facts (goals, preferences, "
                            "constraints, injuries, schedule). Return JSON "
                            '{"facts": ["..."]}. If none, return {"facts": []}.'
                        ),
                    },
                    {"role": "user", "content": blob[:4000]},
                ]
            )
            facts = data.get("facts") or []
            return [str(f).strip() for f in facts if str(f).strip()]
        except (LLMError, Exception):
            # Persist raw turn as a soft fact so handoff still has something
            return [f"Recent note: {messages[-1].get('content', '')[:240]}"] if messages else []

    def search(
        self,
        query: str,
        *,
        owner_id: str,
        agent_id: str,
        limit: int = 8,
    ) -> dict[str, Any]:
        tokens = [t.lower() for t in query.split() if len(t) > 2]
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT content FROM facts WHERE owner_id=? AND agent_id=? ORDER BY created_at DESC LIMIT 200",
                (owner_id, agent_id),
            ).fetchall()
        scored: list[tuple[float, str]] = []
        for row in rows:
            content = row["content"]
            lower = content.lower()
            score = sum(1.0 for t in tokens if t in lower) if tokens else 0.5
            if score > 0 or not tokens:
                scored.append((score, content))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [{"content": c, "score": s} for s, c in scored[:limit]]
        return {"success": True, "results": results, "count": len(results), "query": query}

    def get_context(
        self,
        messages: list[dict[str, str]],
        *,
        owner_id: str,
        agent_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        with self._conn() as conn:
            short = conn.execute(
                "SELECT role, content FROM messages WHERE owner_id=? AND agent_id=? AND session_id=?"
                " ORDER BY created_at DESC LIMIT 12",
                (owner_id, agent_id, session_id),
            ).fetchall()
            facts = conn.execute(
                "SELECT content FROM facts WHERE owner_id=? AND agent_id=? ORDER BY created_at DESC LIMIT 20",
                (owner_id, agent_id),
            ).fetchall()

        short_term = [{"role": r["role"], "content": r["content"]} for r in reversed(short)]
        long_term = [r["content"] for r in facts]
        # Prefer facts matching the latest user message
        latest = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if latest:
            hit = self.search(latest, owner_id=owner_id, agent_id=agent_id, limit=6)
            long_term = [r["content"] for r in hit["results"]] or long_term

        parts = []
        if long_term:
            parts.append("Long-term memory:\n- " + "\n- ".join(long_term))
        if short_term:
            parts.append(
                "Recent session messages:\n"
                + "\n".join(f"{m['role']}: {m['content']}" for m in short_term)
            )
        return {
            "short_term": short_term,
            "long_term": long_term,
            "short_term_count": len(short_term),
            "long_term_count": len(long_term),
            "context_string": "\n\n".join(parts),
        }


_local_store: LocalMemoryStore | None = None
_cognis_ok: bool | None = None


def _get_local() -> LocalMemoryStore:
    global _local_store
    if _local_store is None:
        _local_store = LocalMemoryStore(get_settings().memory_data_dir)
    return _local_store


def memory_backend() -> str:
    """Report which backend is active."""
    settings = get_settings()
    if settings.gemini_api_key.strip():
        return "cognis"
    return "local_groq"


def add_memory(
    messages: list[dict[str, str]],
    *,
    owner_id: str,
    agent_id: str,
    session_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.gemini_api_key.strip():
        try:
            return _cognis_add(messages, owner_id=owner_id, agent_id=agent_id, session_id=session_id)
        except Exception:
            pass
    return _get_local().add(
        messages, owner_id=owner_id, agent_id=agent_id, session_id=session_id
    )


def get_memory_context(
    messages: list[dict[str, str]],
    *,
    owner_id: str,
    agent_id: str,
    session_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.gemini_api_key.strip():
        try:
            return _cognis_context(
                messages, owner_id=owner_id, agent_id=agent_id, session_id=session_id
            )
        except Exception:
            pass
    return _get_local().get_context(
        messages, owner_id=owner_id, agent_id=agent_id, session_id=session_id
    )


def search_memory(
    query: str,
    *,
    owner_id: str,
    agent_id: str,
    limit: int = 8,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.gemini_api_key.strip():
        try:
            return _cognis_search(query, owner_id=owner_id, agent_id=agent_id, limit=limit)
        except Exception:
            pass
    return _get_local().search(query, owner_id=owner_id, agent_id=agent_id, limit=limit)


def _cognis_add(messages, *, owner_id, agent_id, session_id):
    from cognis import Cognis, CognisConfig

    settings = get_settings()
    model = f"groq/{settings.groq_fast_model}"
    config = CognisConfig(llm_model=model)
    m = Cognis(
        owner_id=owner_id,
        agent_id=agent_id,
        session_id=session_id,
        data_dir=settings.memory_data_dir,
        gemini_api_key=settings.gemini_api_key or None,
        config=config,
    )
    try:
        return m.add(messages)
    finally:
        m.close()


def _cognis_context(messages, *, owner_id, agent_id, session_id):
    from cognis import Cognis, CognisConfig

    settings = get_settings()
    model = f"groq/{settings.groq_fast_model}"
    config = CognisConfig(llm_model=model)
    m = Cognis(
        owner_id=owner_id,
        agent_id=agent_id,
        session_id=session_id,
        data_dir=settings.memory_data_dir,
        gemini_api_key=settings.gemini_api_key or None,
        config=config,
    )
    try:
        return m.get_context(messages)
    finally:
        m.close()


def _cognis_search(query, *, owner_id, agent_id, limit):
    from cognis import Cognis, CognisConfig

    settings = get_settings()
    model = f"groq/{settings.groq_fast_model}"
    config = CognisConfig(llm_model=model)
    m = Cognis(
        owner_id=owner_id,
        agent_id=agent_id,
        data_dir=settings.memory_data_dir,
        gemini_api_key=settings.gemini_api_key or None,
        config=config,
    )
    try:
        return m.search(query, limit=limit)
    finally:
        m.close()
