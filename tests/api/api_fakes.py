"""Test doubles for the API: an in-memory Store, a fake login check, a fake pipeline.

No network, no database, no real keys (CLAUDE.md section 12). `FakeStore` must behave like
`SqlStore`; tests/api/test_api_store_contract.py runs the same checks against both.
"""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from api.deps import InvalidToken, TokenClaims
from api.pipeline import FinalAnswer, SearchHit, TextDelta
from api.store import OwnsOrganisation, act_slug_candidates


class FakeVerifier:
    """Tokens look like 'token-alice'. Anything else is rejected."""

    def __init__(self):
        self.people = {
            "token-alice": TokenClaims("uid-alice", "alice@example.com", "Alice"),
            "token-bob": TokenClaims("uid-bob", "bob@example.com", "Bob"),
        }

    async def verify(self, token: str) -> TokenClaims:
        if token not in self.people:
            raise InvalidToken
        return self.people[token]


class FakeQueue:
    def __init__(self):
        self.jobs: list[tuple[str, dict]] = []
        self.fail = False

    async def enqueue(self, job: str, **kwargs: Any) -> None:
        if self.fail:
            raise RuntimeError("redis down")
        self.jobs.append((job, kwargs))


class FakeSigner:
    async def presign_upload(self, path: str, mime_type: str | None) -> str:
        return f"https://upload.example/{path}"


class FakePipeline:
    """Plays back a scripted list of events. Records whether it was called."""

    def __init__(self, events=None, hits=None, fail_at: int | None = None):
        self.events = events or []
        self.hits = hits or []
        self.fail_at = fail_at
        self.calls: list[dict] = []

    async def answer(self, **kwargs):
        self.calls.append(kwargs)
        for i, ev in enumerate(self.events):
            if self.fail_at == i:
                raise RuntimeError("model exploded")
            yield ev

    async def search(self, *, query, filters, limit) -> list[SearchHit]:
        self.calls.append({"search": query, "filters": filters, "limit": limit})
        return self.hits[:limit]


def words(text: str) -> list[TextDelta]:
    return [TextDelta(w + " ") for w in text.split()]


class FakeStore:
    """Dicts and lists standing in for PostgreSQL."""

    def __init__(self):
        self.users: dict[str, dict] = {}  # by firebase_uid
        self.conversations: dict[UUID, dict] = {}
        self.messages: dict[UUID, list[dict]] = {}
        self.sources: dict[UUID, list[dict]] = {}  # by message id
        self.invented: list[dict] = []
        self.usage: list[dict] = []
        self.consents: list[dict] = []
        self.documents: dict[UUID, dict] = {}
        self.feedback: dict[tuple[UUID, UUID], dict] = {}
        self.cases: dict[str, dict] = {}
        self.acts: list[dict] = []
        self.coverage: list[dict] = []
        self.audit: list[dict] = []
        self.subscriptions: dict[str, dict] = {}
        self.org_owners: set[UUID] = set()
        self.healthy = True
        self._tick = datetime(2026, 1, 1, tzinfo=UTC)

    def _now(self) -> datetime:
        self._tick += timedelta(seconds=1)  # strictly increasing, so ordering is stable
        return self._tick

    # ---- seeding helpers used by tests ------------------------------------------
    def set_plan(self, uid: str, plan: str) -> None:
        self.users[uid]["plan"] = plan

    def add_case(self, **kw) -> None:
        row = {
            "title": None, "court": "Supreme Court of India", "decision_date": None,
            "case_number": None, "citation": None, "disposition": None,
            "outcome_label": None, "is_final_outcome": None, "pdf_url": None,
            "full_text": None,
        }  # fmt: skip
        row.update(kw)
        self.cases[row["record_id"]] = row

    def add_act(self, **kw) -> None:
        row = {
            "act_year": None, "section_title": None, "text": None, "in_force": None,
            "act_status": None, "source_url": None,
        }  # fmt: skip
        row.update(kw)
        self.acts.append(row)

    # ---- Store interface ----------------------------------------------------------
    async def ping(self) -> None:
        if not self.healthy:
            raise RuntimeError("db down")

    async def upsert_user(self, firebase_uid, email, name):
        u = self.users.get(firebase_uid)
        if u is None:
            u = {
                "id": uuid4(), "firebase_uid": firebase_uid, "email": email,
                "name": name, "role": "other", "plan": "free", "status": "active",
            }  # fmt: skip
            self.users[firebase_uid] = u
        elif u["email"] != email:
            u["email"] = email
        return dict(u)

    async def answers_used(self, user_id, since):
        return sum(
            r["requests"]
            for r in self.usage
            if r["user_id"] == user_id and r["date"] >= since
        )

    async def create_conversation(self, user_id, module, title, document_id):
        if document_id is not None:
            doc = self.documents.get(document_id)
            if doc is None or doc["user_id"] != user_id:
                document_id = None
        cid, now = uuid4(), self._now()
        row = {
            "id": cid, "user_id": user_id, "module": module, "title": title,
            "rolling_summary": None, "message_count": 0, "created_at": now,
            "updated_at": now, "document_id": document_id,
        }  # fmt: skip
        self.conversations[cid] = row
        self.messages[cid] = []
        return dict(row)

    async def list_conversations(self, user_id, after, limit):
        rows = [c for c in self.conversations.values() if c["user_id"] == user_id]
        rows.sort(key=lambda c: (c["created_at"], c["id"]), reverse=True)
        if after is not None:
            rows = [c for c in rows if (c["created_at"], c["id"]) < after]
        return [dict(c) for c in rows[:limit]]

    async def get_conversation(self, user_id, conversation_id):
        c = self.conversations.get(conversation_id)
        return dict(c) if c and c["user_id"] == user_id else None

    async def list_messages(self, conversation_id):
        out = []
        for m in self.messages.get(conversation_id, []):
            m = dict(m)
            m["sources"] = [dict(s) for s in self.sources.get(m["id"], [])]
            out.append(m)
        return out

    async def save_exchange(
        self, user_id, conversation_id, question, answer: FinalAnswer, *, count_usage
    ):
        self.messages[conversation_id].append(
            {
                "id": uuid4(),
                "role": "user",
                "content": question,
                "created_at": self._now(),
            }
        )
        mid = uuid4()
        self.messages[conversation_id].append(
            {"id": mid, "role": "assistant", "content": answer.text,
             "created_at": self._now(), "from_cache": answer.from_cache,
             "model": answer.model}
        )  # fmt: skip
        self.sources[mid] = [
            {
                "source_id": s.source_id, "record_id": s.record_id,
                "verified": s.verified, "support": s.support,
                "title": self.cases.get(s.record_id, {}).get("title"),
                "citation": self.cases.get(s.record_id, {}).get("citation"),
                "url": self.cases.get(s.record_id, {}).get("pdf_url"),
            }
            for s in answer.sources
        ]  # fmt: skip
        for r in answer.removed:
            self.invented.append(
                {"message_id": mid, "reason": r.reason, "cited_text": r.cited_text,
                 "query": answer.rewritten_query}
            )  # fmt: skip
        conv = self.conversations[conversation_id]
        conv["message_count"] += 2
        conv["title"] = conv["title"] or question[:80]
        if answer.rolling_summary is not None:
            conv["rolling_summary"] = answer.rolling_summary
        if count_usage:
            today = datetime.now(UTC).date()
            row = next(
                (
                    r
                    for r in self.usage
                    if r["user_id"] == user_id and r["date"] == today
                ),
                None,
            )
            if row is None:
                row = {"user_id": user_id, "date": today, "requests": 0}
                self.usage.append(row)
            row["requests"] += 1
        return mid

    async def get_case(self, record_id):
        c = self.cases.get(record_id)
        return dict(c) if c else None

    async def get_act_section(self, act, section):
        names, year = act_slug_candidates(act)
        from api.store import act_slug

        found = [
            a
            for a in self.acts
            if (
                act_slug(a["act_name"]) in names
                or re.sub(r"-\d{4}$", "", act_slug(a["act_name"])) in names
            )
            and a["section_number"].lower() == section.lower()
            and (year is None or a["act_year"] in (year, None))
        ]
        found.sort(key=lambda a: a["act_year"] or 0, reverse=True)
        return dict(found[0]) if found else None

    async def data_as_of(self, court):
        rows = sorted(
            self.coverage, key=lambda r: (r["snapshot_version"], r["data_as_of"])
        )
        if court is not None:
            mine = [r for r in rows if r["court"] == court]
            if mine:
                return mine[-1]["data_as_of"]
        return rows[-1]["data_as_of"] if rows else None

    async def stats_live(self, court):
        return any(r["stats_live"] for r in self.coverage if r["court"] == court)

    async def case_stats(self, court, year):
        counts: dict[tuple[int, str], int] = {}
        for c in self.cases.values():
            if (
                c["court"] == court
                and c["outcome_label"]
                and c["is_final_outcome"] is True
                and c["decision_date"]
                and (year is None or c["decision_date"].year == year)
            ):
                key = (c["decision_date"].year, c["outcome_label"])
                counts[key] = counts.get(key, 0) + 1
        return [
            {"year": y, "outcome_label": o, "count": n}
            for (y, o), n in sorted(
                counts.items(), key=lambda kv: (-kv[0][0], kv[0][1])
            )
        ]

    async def list_consents(self, user_id):
        rows = [c for c in self.consents if c["user_id"] == user_id]
        rows.sort(key=lambda c: c["given_at"], reverse=True)
        return [{k: v for k, v in c.items() if k != "user_id"} for c in rows]

    async def give_consent(self, user_id, notice_version, purpose):
        row = {
            "id": uuid4(), "user_id": user_id, "notice_version": notice_version,
            "purpose": purpose, "given_at": self._now(), "withdrawn_at": None,
        }  # fmt: skip
        self.consents.append(row)
        return {k: v for k, v in row.items() if k != "user_id"}

    async def withdraw_consent(self, user_id, purpose):
        n = 0
        for c in self.consents:
            if (
                c["user_id"] == user_id
                and c["purpose"] == purpose
                and c["withdrawn_at"] is None
            ):
                c["withdrawn_at"] = self._now()
                n += 1
        return n

    async def account_cleanup_info(self, user_id):
        user = next(u for u in self.users.values() if u["id"] == user_id)
        docs = [d for d in self.documents.values() if d["user_id"] == user_id]
        return {
            "firebase_uid": user["firebase_uid"],
            "document_ids": [str(d["id"]) for d in docs],
            "storage_paths": [d["storage_path"] for d in docs if d["storage_path"]],
            "razorpay_subscription_ids": [
                s["razorpay_subscription_id"]
                for s in self.subscriptions.values()
                if s["user_id"] == user_id
            ],
        }

    async def owns_organisation(self, user_id):
        return user_id in self.org_owners

    async def delete_user(self, user_id):
        if user_id in self.org_owners:
            raise OwnsOrganisation
        self.users = {k: v for k, v in self.users.items() if v["id"] != user_id}
        for cid in [
            c for c, v in self.conversations.items() if v["user_id"] == user_id
        ]:
            for m in self.messages.pop(cid, []):
                self.sources.pop(m["id"], None)
                self.invented = [i for i in self.invented if i["message_id"] != m["id"]]
            del self.conversations[cid]
        self.documents = {
            k: v for k, v in self.documents.items() if v["user_id"] != user_id
        }
        self.consents = [c for c in self.consents if c["user_id"] != user_id]
        self.usage = [u for u in self.usage if u["user_id"] != user_id]
        for s in self.subscriptions.values():  # kept, but detached from the person
            if s["user_id"] == user_id:
                s["user_id"] = None

    async def export_user(self, user_id):
        user = next(u for u in self.users.values() if u["id"] == user_id)
        convs = []
        for c in self.conversations.values():
            if c["user_id"] == user_id:
                convs.append(
                    {
                        "id": c["id"], "module": c["module"], "title": c["title"],
                        "message_count": c["message_count"], "created_at": c["created_at"],
                        "messages": [
                            {k: m[k] for k in ("id", "role", "content", "created_at")}
                            for m in self.messages[c["id"]]
                        ],
                    }
                )  # fmt: skip
        return {
            "account": {k: user[k] for k in ("id", "email", "name", "role", "plan", "status")},
            "consents": await self.list_consents(user_id),
            "conversations": convs,
            "documents": [
                {k: d[k] for k in ("id", "filename", "status")}
                for d in self.documents.values()
                if d["user_id"] == user_id
            ],
        }  # fmt: skip

    async def add_audit(self, user_id, action, target_id, ip, request_id):
        self.audit.append(
            {"user_id": user_id, "action": action, "target_id": target_id,
             "ip": ip, "request_id": request_id}
        )  # fmt: skip

    async def add_feedback(self, user_id, message_id, rating, reason, comment):
        owned = any(
            m["id"] == message_id
            for cid, c in self.conversations.items()
            if c["user_id"] == user_id
            for m in self.messages[cid]
        )
        if not owned:
            return False
        self.feedback[(message_id, user_id)] = {
            "rating": rating, "reason": reason, "comment": comment,
        }  # fmt: skip
        return True

    async def create_document(
        self, doc_id, user_id, filename, mime_type, size_bytes, storage_path
    ):
        row = {
            "id": doc_id, "user_id": user_id, "filename": filename, "status": "uploaded",
            "fail_reason": None, "page_count": None, "expires_at": None,
            "storage_path": storage_path,
        }  # fmt: skip
        self.documents[doc_id] = row
        return dict(row)

    async def get_document(self, user_id, doc_id):
        d = self.documents.get(doc_id)
        return dict(d) if d and d["user_id"] == user_id else None

    async def delete_document(self, user_id, doc_id):
        d = self.documents.get(doc_id)
        if d and d["user_id"] == user_id:
            del self.documents[doc_id]
            return {"id": d["id"], "storage_path": d["storage_path"]}
        return None

    async def update_subscription_status(self, razorpay_id, status):
        s = self.subscriptions.get(razorpay_id)
        if s:
            s["status"] = status
            return 1
        return 0


def d(y: int, m: int = 1, day: int = 1) -> date:
    return date(y, m, day)
