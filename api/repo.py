"""Storage interface for the API, plus an in-memory version for tests and fake mode.

Plain words: routes never write SQL. They call these methods. `pg_repo.py` is the
real PostgreSQL version; `MemoryRepo` here is the same thing in a Python dict.
Rows are plain dicts with string IDs.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Protocol


def slugify_act(act_name: str, year: int | None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", act_name.lower()).strip("-")
    return f"{base}-{year}" if year else base


def split_paragraphs(full_text: str) -> list[dict[str, str]]:
    parts = [p.strip() for p in re.split(r"\n\s*\n", full_text or "") if p.strip()]
    return [{"anchor": f"p{i}", "text": p} for i, p in enumerate(parts, 1)]


# The bridge puts a dict here before running the pipeline; the store writes the saved
# assistant message id into it so the `done` event can name it.
_last_message: ContextVar[dict | None] = ContextVar("last_message", default=None)


class Repo(Protocol):
    async def upsert_user(
        self, uid: str, email: str | None, name: str | None
    ) -> dict: ...
    async def answers_this_month(self, user_id: str) -> int: ...
    async def create_conversation(
        self, user_id: str, module: str, document_id: str | None
    ) -> dict: ...
    async def list_conversations(
        self, user_id: str, cursor: str | None, limit: int
    ) -> tuple[list[dict], str | None]: ...
    async def get_conversation(self, user_id: str, conv_id: str) -> dict | None: ...
    async def add_user_message(
        self, user_id: str, conv_id: str, content: str
    ) -> str | None: ...
    async def history(
        self, user_id: str, conv_id: str, exclude_id: str
    ) -> tuple[list[tuple[str, str]], str]: ...
    async def get_case(self, record_id: str) -> dict | None: ...
    async def get_section(self, act_slug: str, number: str) -> dict | None: ...
    async def data_as_of(self) -> tuple[str, str] | None: ...
    async def stats(self) -> tuple[list[dict], bool]: ...
    async def add_feedback(self, user_id: str, data: dict) -> None: ...
    async def list_consents(self, user_id: str) -> list[dict]: ...
    async def add_consent(
        self, user_id: str, notice_version: str, purpose: str
    ) -> dict: ...
    async def withdraw_consent(self, user_id: str, consent_id: str) -> bool: ...


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryRepo:
    """Dict-backed Repo. Also plays UsageMeter, CitationLog and ConversationStore."""

    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.convs: dict[str, dict] = {}
        self.msgs: dict[str, list[dict]] = {}
        self.cases: dict[str, dict] = {}
        self.sections: list[dict] = []
        self.coverage: tuple[str, str] | None = ("2026-08-31", "v2026.08")
        self.feedback: list[dict] = []
        self.consents: dict[str, list[dict]] = {}
        self.usage: dict[str, int] = {}
        self.invented: list[dict] = []

    async def upsert_user(self, uid, email, name):
        for u in self.users.values():
            if u["firebase_uid"] == uid:
                return u
        u = {
            "id": str(uuid.uuid4()), "firebase_uid": uid, "email": email,
            "name": name, "role": None, "plan": "free",
        }  # fmt: skip
        self.users[u["id"]] = u
        return u

    async def answers_this_month(self, user_id):
        return self.usage.get(user_id, 0)

    async def create_conversation(self, user_id, module, document_id):
        c = {
            "id": str(uuid.uuid4()), "user_id": user_id, "module": module,
            "document_id": document_id, "title": None, "message_count": 0,
            "rolling_summary": "", "created_at": _now(), "updated_at": _now(),
        }  # fmt: skip
        self.convs[c["id"]] = c
        self.msgs[c["id"]] = []
        return c

    async def list_conversations(self, user_id, cursor, limit):
        rows = sorted(
            (c for c in self.convs.values() if c["user_id"] == user_id),
            key=lambda c: (c["created_at"], c["id"]),
            reverse=True,
        )
        start = int(cursor) if cursor else 0
        page = rows[start : start + limit]
        nxt = str(start + limit) if start + limit < len(rows) else None
        return page, nxt

    async def get_conversation(self, user_id, conv_id):
        c = self.convs.get(conv_id)
        if not c or c["user_id"] != user_id:  # other users' chats look absent
            return None
        return {**c, "messages": list(self.msgs[conv_id])}

    async def add_user_message(self, user_id, conv_id, content):
        c = self.convs.get(conv_id)
        if not c or c["user_id"] != user_id:
            return None
        m = {
            "id": str(uuid.uuid4()), "role": "user", "content": content,
            "from_cache": False, "citations": [], "created_at": _now(),
            "shaped_by_upload": False, "shaped_by_matter_fact": False,
        }  # fmt: skip
        self.msgs[conv_id].append(m)
        self.convs[conv_id]["message_count"] += 1
        if not self.convs[conv_id]["title"]:
            self.convs[conv_id]["title"] = content[:80]
        return m["id"]

    async def history(self, user_id, conv_id, exclude_id):
        c = self.convs.get(conv_id)
        if not c or c["user_id"] != user_id:
            return [], ""
        turns = [
            (m["role"], m["content"])
            for m in self.msgs[conv_id]
            if m["id"] != exclude_id
        ]
        return turns, self.convs[conv_id]["rolling_summary"] or ""

    async def get_case(self, record_id):
        return self.cases.get(record_id)

    async def get_section(self, act_slug, number):
        for s in self.sections:
            if s["act_slug"] == act_slug and s["section"] == number:
                return s
        return None

    async def data_as_of(self):
        return self.coverage

    async def stats(self):
        return [], False

    async def add_feedback(self, user_id, data):
        self.feedback.append({"user_id": user_id, **data})

    async def list_consents(self, user_id):
        return self.consents.get(user_id, [])

    async def add_consent(self, user_id, notice_version, purpose):
        c = {
            "id": str(uuid.uuid4()), "notice_version": notice_version,
            "purpose": purpose, "given_at": _now(), "withdrawn_at": None,
        }  # fmt: skip
        self.consents.setdefault(user_id, []).append(c)
        return c

    async def withdraw_consent(self, user_id, consent_id):
        for c in self.consents.get(user_id, []):
            if c["id"] == consent_id:
                c["withdrawn_at"] = _now()
                return True
        return False

    # --- core's Protocols (UsageMeter / ConversationStore / CitationLog) ---
    async def allowed(self, user_id: str, plan: str) -> bool:
        return True

    async def count_one(self, user_id: str) -> None:
        self.usage[user_id] = self.usage.get(user_id, 0) + 1

    async def save(self, request: Any, result: Any) -> None:
        conv_id = request.conversation_id
        c = self.convs.get(conv_id)
        if not c or c["user_id"] != request.user_id or result.outcome != "answered":
            return
        m = {
            "id": str(uuid.uuid4()), "role": "assistant", "content": result.answer.text,
            "from_cache": result.cache_hit, "citations": [], "created_at": _now(),
            "shaped_by_upload": result.provenance.shaped_by_upload,
            "shaped_by_matter_fact": result.provenance.shaped_by_matter_fact,
        }  # fmt: skip
        self.msgs[conv_id].append(m)
        self.convs[conv_id]["message_count"] += 1
        _holder = _last_message.get(None)
        if _holder is not None:
            _holder["id"] = m["id"]

    async def write(self, question: str, model: str, removed: Any) -> None:
        for r in removed:
            self.invented.append({"question": question, "model": model, "r": r})
