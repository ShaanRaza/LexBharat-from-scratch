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

from core.settings import get_settings
from core.spend import AiCall, summarise


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
    async def record_ai_call(self, user_id: str, call: AiCall) -> None: ...
    async def get_message_for_share(
        self, user_id: str, message_id: str
    ) -> dict | None: ...
    async def create_share_link(
        self, user_id: str, message_id: str, token_hash: str, expires_at: datetime
    ) -> dict: ...
    async def list_share_links(self, user_id: str) -> list[dict]: ...
    async def revoke_share_link(self, user_id: str, link_id: str) -> bool: ...
    async def get_shared_answer(self, token_hash: str) -> dict | None: ...
    async def create_matter(self, user_id: str, title: str, kind: str) -> dict: ...
    async def list_matters(self, user_id: str, status: str | None) -> list[dict]: ...
    async def update_matter(
        self, user_id: str, matter_id: str, title: str | None, status: str | None
    ) -> dict | None: ...
    async def set_conversation_matter(
        self, user_id: str, conv_id: str, matter_id: str | None
    ) -> bool: ...
    async def search_user_work(
        self, user_id: str, q: str, limit: int
    ) -> list[dict]: ...
    async def get_matter(self, user_id: str, matter_id: str) -> dict | None: ...
    async def matter_document_ids(self, user_id: str, matter_id: str) -> list[str]: ...
    async def delete_matter(
        self, user_id: str, matter_id: str, delete_conversations: bool
    ) -> int: ...
    async def create_document(
        self, user_id: str, filename: str, matter_id: str | None, text: str
    ) -> str: ...
    async def delete_document_rows(self, user_id: str, document_id: str) -> bool: ...
    async def document_rows_remaining(self, document_id: str) -> int: ...
    async def audit(self, user_id: str, action: str, target_id: str) -> None: ...
    async def deleted_documents(self, days: int) -> list[tuple[str, str]]: ...
    async def daily_ai_spend(self, days: int = 7) -> list[dict]: ...
    async def create_conversation(
        self,
        user_id: str,
        module: str,
        document_id: str | None,
        matter_id: str | None = None,
    ) -> dict: ...
    async def list_conversations(
        self,
        user_id: str,
        cursor: str | None,
        limit: int,
        matter_id: str | None = None,
        unfiled: bool = False,
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
        self.usage: dict[str, int] = {}  # ANSWERS per user (the meter)
        self.ai_calls: list[tuple[str, AiCall]] = []  # helper calls: spend, not answers
        self.invented: list[dict] = []
        self.matters: dict[str, dict] = {}
        self.documents: dict[str, dict] = {}  # id -> {user_id, matter_id, text}
        self.audit_rows: list[tuple[str, str, str]] = []
        self.shares: dict[str, dict] = {}  # id -> link row (token stored hashed only)

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

    async def record_ai_call(self, user_id, call):
        self.ai_calls.append((user_id, call))

    async def daily_ai_spend(self, days=7):
        today = _now().date()
        rows = [
            {"day": today, "feature": c.feature, "calls": 1,
             "tokens_in": c.tokens_in, "tokens_out": c.tokens_out}
            for _, c in self.ai_calls
        ]  # fmt: skip
        rows.append(
            {"day": today, "feature": "answer", "calls": sum(self.usage.values()),
             "tokens_in": 0, "tokens_out": 0}
        )  # fmt: skip
        return summarise(rows, get_settings())

    # --- share links (O14) ---------------------------------------------------------
    def _find_message(self, user_id, message_id):
        for cid, c in self.convs.items():
            if c["user_id"] != user_id:
                continue
            for i, m in enumerate(self.msgs.get(cid, [])):
                if str(m["id"]) == str(message_id):
                    return cid, i, m
        return None

    async def get_message_for_share(self, user_id, message_id):
        hit = self._find_message(user_id, message_id)
        if hit is None:
            return None
        _, _, m = hit
        return {
            "id": m["id"], "role": m["role"],
            "shaped_by_upload": bool(m.get("shaped_by_upload")),
            "shaped_by_matter_fact": bool(m.get("shaped_by_matter_fact")),
        }  # fmt: skip

    async def create_share_link(self, user_id, message_id, token_hash, expires_at):
        # Mirrors the database trigger: refuse what must not be shared, whoever calls.
        m = await self.get_message_for_share(user_id, message_id)
        if (
            m is None
            or m["role"] != "assistant"
            or m["shaped_by_upload"]
            or m["shaped_by_matter_fact"]
        ):
            raise ValueError("this answer cannot be shared")
        row = {
            "id": str(uuid.uuid4()), "user_id": user_id, "message_id": message_id,
            "token_hash": token_hash, "expires_at": expires_at, "revoked_at": None,
            "created_at": _now(),
        }  # fmt: skip
        self.shares[row["id"]] = row
        return dict(row)

    async def list_share_links(self, user_id):
        rows = [r for r in self.shares.values() if r["user_id"] == user_id]
        return [
            {k: v for k, v in r.items() if k not in ("token_hash", "user_id")}
            for r in sorted(rows, key=lambda r: r["created_at"], reverse=True)
        ]

    async def revoke_share_link(self, user_id, link_id):
        r = self.shares.get(link_id)
        if not r or r["user_id"] != user_id or r["revoked_at"] is not None:
            return False
        r["revoked_at"] = _now()
        return True

    async def get_shared_answer(self, token_hash):
        """The public read. Checked against the stored row on EVERY call: not revoked,
        not expired, and still an answer that may be shared. Returns no user
        identity."""
        link = next(
            (r for r in self.shares.values() if r["token_hash"] == token_hash), None
        )
        if (
            link is None
            or link["revoked_at"] is not None
            or link["expires_at"] <= _now()
        ):
            return None
        hit = self._find_message(link["user_id"], link["message_id"])
        if hit is None:
            return None
        cid, i, m = hit
        if (
            m["role"] != "assistant"
            or m.get("shaped_by_upload")
            or m.get("shaped_by_matter_fact")
        ):
            return None
        question = next(
            (x["content"] for x in reversed(self.msgs[cid][:i]) if x["role"] == "user"),
            "",
        )
        return {
            "question": question, "text": m["content"],
            "citations": list(m.get("citations", [])), "expires_at": link["expires_at"],
        }  # fmt: skip

    # --- matters, documents, audit (A52) -------------------------------------------
    async def create_matter(self, user_id, title, kind):
        now = _now()
        m = {
            "id": str(uuid.uuid4()), "user_id": user_id, "title": title, "kind": kind,
            "status": "active", "archived_at": None,
            "created_at": now, "updated_at": now,
        }  # fmt: skip
        self.matters[m["id"]] = m
        return dict(m)

    def _counts(self, user_id, matter_id):
        return {
            "conversation_count": sum(
                1
                for c in self.convs.values()
                if c["user_id"] == user_id and c.get("matter_id") == matter_id
            ),
            "document_count": sum(
                1
                for d in self.documents.values()
                if d["user_id"] == user_id and d["matter_id"] == matter_id
            ),
        }

    async def get_matter(self, user_id, matter_id):
        m = self.matters.get(matter_id)
        if not m or m["user_id"] != user_id:  # another user's matter looks absent
            return None
        return {**m, **self._counts(user_id, matter_id)}

    async def list_matters(self, user_id, status):
        rows = [
            {**m, **self._counts(user_id, m["id"])}
            for m in self.matters.values()
            if m["user_id"] == user_id and (status is None or m["status"] == status)
        ]
        return sorted(rows, key=lambda m: (m["updated_at"], m["id"]), reverse=True)

    async def update_matter(self, user_id, matter_id, title, status):
        m = self.matters.get(matter_id)
        if not m or m["user_id"] != user_id:
            return None
        if title is not None:
            m["title"] = title
        if status is not None and status != m["status"]:
            m["status"] = status
            m["archived_at"] = _now() if status == "archived" else None
        m["updated_at"] = _now()
        return await self.get_matter(user_id, matter_id)

    async def set_conversation_matter(self, user_id, conv_id, matter_id):
        c = self.convs.get(conv_id)
        if not c or c["user_id"] != user_id:
            return False
        if matter_id is not None and await self.get_matter(user_id, matter_id) is None:
            return False  # never file work under someone else's matter
        c["matter_id"] = matter_id
        c["updated_at"] = _now()
        return True

    async def search_user_work(self, user_id, q, limit):
        words = [w.lower() for w in q.split()]
        out = []
        for cid, c in self.convs.items():
            if c["user_id"] != user_id:
                continue
            title = c.get("title") or ""
            if words and all(w in title.lower() for w in words):
                out.append(
                    {"kind": "conversation", "user_id": user_id, "conversation_id": cid,
                     "message_id": None, "matter_id": c.get("matter_id"),
                     "title": c.get("title"), "snippet": title,
                     "created_at": c["updated_at"]}
                )  # fmt: skip
            for m in self.msgs.get(cid, []):
                if words and all(w in m["content"].lower() for w in words):
                    out.append(
                        {"kind": "message", "user_id": user_id, "conversation_id": cid,
                         "message_id": m["id"], "matter_id": c.get("matter_id"),
                         "title": c.get("title"), "snippet": m["content"][:160],
                         "created_at": m["created_at"]}
                    )  # fmt: skip
        out.sort(key=lambda r: r["created_at"], reverse=True)
        return out[:limit]

    async def matter_document_ids(self, user_id, matter_id):
        return [
            i
            for i, d in self.documents.items()
            if d["user_id"] == user_id and d["matter_id"] == matter_id
        ]

    async def delete_matter(self, user_id, matter_id, delete_conversations):
        if await self.get_matter(user_id, matter_id) is None:
            return 0
        n = 0
        for cid, c in list(self.convs.items()):
            if c["user_id"] == user_id and c.get("matter_id") == matter_id:
                if delete_conversations:
                    del self.convs[cid]
                    self.msgs.pop(cid, None)
                    n += 1
                else:
                    c["matter_id"] = None  # unfiled
        for d in self.documents.values():
            if d["user_id"] == user_id and d["matter_id"] == matter_id:
                d["matter_id"] = None  # only reachable in "unfile" mode
        del self.matters[matter_id]
        return n

    async def create_document(self, user_id, filename, matter_id, text):
        i = str(uuid.uuid4())
        self.documents[i] = {"user_id": user_id, "matter_id": matter_id, "text": text}
        return i

    async def delete_document_rows(self, user_id, document_id):
        d = self.documents.get(document_id)
        if not d or d["user_id"] != user_id:
            return False
        del self.documents[document_id]
        return True

    async def document_rows_remaining(self, document_id):
        return 1 if document_id in self.documents else 0

    async def audit(self, user_id, action, target_id):
        self.audit_rows.append((user_id, action, target_id))

    async def deleted_documents(self, days):
        seen = dict.fromkeys(
            (u, t.split(":", 1)[1])
            for u, a, t in self.audit_rows
            if a == "delete" and t.startswith("document:")
        )
        return list(seen)

    async def create_conversation(self, user_id, module, document_id, matter_id=None):
        c = {
            "id": str(uuid.uuid4()), "user_id": user_id, "module": module,
            "document_id": document_id, "matter_id": matter_id, "title": None,
            "message_count": 0, "rolling_summary": "",
            "created_at": _now(), "updated_at": _now(),
        }  # fmt: skip
        self.convs[c["id"]] = c
        self.msgs[c["id"]] = []
        return c

    async def list_conversations(
        self, user_id, cursor, limit, matter_id=None, unfiled=False
    ):
        rows = sorted(
            (
                c
                for c in self.convs.values()
                if c["user_id"] == user_id
                and (matter_id is None or c.get("matter_id") == matter_id)
                and (not unfiled or c.get("matter_id") is None)
            ),
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
