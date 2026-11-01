"""Database access for the API: one small class, plain SQL, no business rules.

`Store` is the interface routes depend on. `SqlStore` is the real PostgreSQL version.
Tests use an in-memory copy (tests/api/fakes.py), and one shared test file checks that
both behave the same, so the fake cannot quietly drift from the real thing.

Schema changes happen ONLY in migrations/ (rule 4). This file never creates or alters a
table; it only reads and writes rows.
"""

import re
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from api.pipeline import FinalAnswer

Row = dict[str, Any]


class OwnsOrganisation(Exception):
    """The user owns an organisation, so the account cannot be deleted yet."""


def act_slug(name: str) -> str:
    """'The Indian Penal Code, 1860' -> 'the-indian-penal-code-1860'.

    Must match the generated `act_slug` column in migrations/versions/0004.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def act_slug_candidates(slug: str) -> tuple[list[str], int | None]:
    """The URL may say 'indian-penal-code-1860' while the dataset says 'The Indian Penal
    Code, 1860' (or without the year). Try the sensible variants; return the year too."""
    slug = act_slug(slug)
    candidates = {slug}
    year = None
    m = re.search(r"-(\d{4})$", slug)
    if m:
        year = int(m.group(1))
        candidates.add(slug[: -len(m.group(0))])
    for c in sorted(candidates):  # sorted() = a copy, since we add while looping
        candidates.add(c[4:] if c.startswith("the-") else f"the-{c}")
    return sorted(candidates), year


class Store(Protocol):
    async def ping(self) -> None: ...
    async def upsert_user(
        self, firebase_uid: str, email: str, name: str | None
    ) -> Row: ...
    async def answers_used(self, user_id: UUID, since: date) -> int: ...
    # conversations
    async def create_conversation(
        self, user_id: UUID, module: str, title: str | None, document_id: UUID | None
    ) -> Row: ...
    async def list_conversations(
        self, user_id: UUID, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[Row]: ...
    async def get_conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> Row | None: ...
    async def list_messages(self, conversation_id: UUID) -> list[Row]: ...
    async def save_exchange(
        self,
        user_id: UUID,
        conversation_id: UUID,
        question: str,
        answer: FinalAnswer,
        *,
        count_usage: bool,
    ) -> UUID: ...
    # records
    async def get_case(self, record_id: str) -> Row | None: ...
    async def get_act_section(self, act: str, section: str) -> Row | None: ...
    async def data_as_of(self, court: str | None) -> date | None: ...
    async def stats_live(self, court: str) -> bool: ...
    async def case_stats(self, court: str, year: int | None) -> list[Row]: ...
    # privacy
    async def list_consents(self, user_id: UUID) -> list[Row]: ...
    async def give_consent(
        self, user_id: UUID, notice_version: str, purpose: str
    ) -> Row: ...
    async def withdraw_consent(self, user_id: UUID, purpose: str) -> int: ...
    async def account_cleanup_info(self, user_id: UUID) -> Row: ...
    async def owns_organisation(self, user_id: UUID) -> bool: ...
    async def delete_user(self, user_id: UUID) -> None: ...
    async def export_user(self, user_id: UUID) -> Row: ...
    async def add_audit(
        self,
        user_id: UUID | None,
        action: str,
        target_id: str | None,
        ip: str | None,
        request_id: str | None,
    ) -> None: ...
    # feedback, documents, billing
    async def add_feedback(
        self,
        user_id: UUID,
        message_id: UUID,
        rating: int,
        reason: str | None,
        comment: str | None,
    ) -> bool: ...
    async def create_document(
        self,
        doc_id: UUID,
        user_id: UUID,
        filename: str,
        mime_type: str | None,
        size_bytes: int | None,
        storage_path: str,
    ) -> Row: ...
    async def get_document(self, user_id: UUID, doc_id: UUID) -> Row | None: ...
    async def delete_document(self, user_id: UUID, doc_id: UUID) -> Row | None: ...
    async def update_subscription_status(
        self, razorpay_id: str, status: str
    ) -> int: ...


def _rows(result) -> list[Row]:
    return [dict(r) for r in result.mappings().all()]


def _one(result) -> Row | None:
    r = result.mappings().first()
    return dict(r) if r else None


_USER_COLS = "id, firebase_uid, email, name, role, plan, status"


class SqlStore:
    """Real PostgreSQL implementation. Each method runs in its own transaction."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def ping(self) -> None:
        async with self.engine.connect() as c:
            await c.execute(text("SELECT 1"))

    # ---- users ----------------------------------------------------------------
    async def upsert_user(self, firebase_uid: str, email: str, name: str | None) -> Row:
        """First sign-in creates the row; later calls only touch it if the email changed."""
        async with self.engine.begin() as c:
            row = _one(
                await c.execute(
                    text(f"SELECT {_USER_COLS} FROM users WHERE firebase_uid=:u"),
                    {"u": firebase_uid},
                )
            )
            if row and row["email"] == email:
                return row
            if row:
                return _one(
                    await c.execute(
                        text(
                            f"UPDATE users SET email=:e WHERE id=:id RETURNING {_USER_COLS}"
                        ),
                        {"e": email, "id": row["id"]},
                    )
                )
            created = _one(
                await c.execute(
                    text(
                        "INSERT INTO users (firebase_uid, email, name) "
                        "VALUES (:u, :e, :n) ON CONFLICT (firebase_uid) DO NOTHING "
                        f"RETURNING {_USER_COLS}"
                    ),
                    {"u": firebase_uid, "e": email, "n": name},
                )
            )
            if created:
                return created
            # Two first requests raced; the other one won. Read its row.
            return _one(
                await c.execute(
                    text(f"SELECT {_USER_COLS} FROM users WHERE firebase_uid=:u"),
                    {"u": firebase_uid},
                )
            )

    async def answers_used(self, user_id: UUID, since: date) -> int:
        async with self.engine.connect() as c:
            r = await c.execute(
                text(
                    "SELECT COALESCE(SUM(requests), 0) FROM usage_daily "
                    "WHERE user_id=:u AND feature='research' AND date >= :d"
                ),
                {"u": user_id, "d": since},
            )
            return int(r.scalar_one())

    # ---- conversations --------------------------------------------------------
    async def create_conversation(self, user_id, module, title, document_id) -> Row:
        async with self.engine.begin() as c:
            if document_id is not None:
                # A chat may only attach to the user's OWN upload.
                owned = await c.execute(
                    text("SELECT 1 FROM documents WHERE id=:d AND user_id=:u"),
                    {"d": document_id, "u": user_id},
                )
                if owned.first() is None:
                    document_id = None
            return _one(
                await c.execute(
                    text(
                        "INSERT INTO conversations (user_id, module, title, document_id) "
                        "VALUES (:u, :m, :t, :d) RETURNING id, module, title, "
                        "message_count, created_at, updated_at, document_id"
                    ),
                    {"u": user_id, "m": module, "t": title, "d": document_id},
                )
            )

    async def list_conversations(self, user_id, after, limit) -> list[Row]:
        sql = (
            "SELECT id, module, title, message_count, created_at, updated_at "
            "FROM conversations WHERE user_id=:u"
        )
        params: dict[str, Any] = {"u": user_id, "n": limit}
        if after is not None:
            sql += " AND (created_at, id) < (:ca, :ci)"
            params.update(ca=after[0], ci=after[1])
        sql += " ORDER BY created_at DESC, id DESC LIMIT :n"
        async with self.engine.connect() as c:
            return _rows(await c.execute(text(sql), params))

    async def get_conversation(self, user_id, conversation_id) -> Row | None:
        # The user_id in the WHERE is what stops one user reading another's chat.
        async with self.engine.connect() as c:
            return _one(
                await c.execute(
                    text(
                        "SELECT id, module, title, rolling_summary, message_count, "
                        "created_at, updated_at, document_id FROM conversations "
                        "WHERE id=:id AND user_id=:u"
                    ),
                    {"id": conversation_id, "u": user_id},
                )
            )

    async def list_messages(self, conversation_id) -> list[Row]:
        """Messages oldest-first, each with a `sources` list (links come from the corpus copy)."""
        async with self.engine.connect() as c:
            msgs = _rows(
                await c.execute(
                    text(
                        "SELECT id, role, content, created_at FROM messages "
                        "WHERE conversation_id=:c ORDER BY created_at, id"
                    ),
                    {"c": conversation_id},
                )
            )
            by_id = {m["id"]: m for m in msgs}
            for m in msgs:
                m["sources"] = []
            if by_id:
                srcs = _rows(
                    await c.execute(
                        text(
                            "SELECT ms.message_id, ms.source_id, ms.record_id, ms.verified, "
                            "ms.support, "
                            "COALESCE(c.title, a.act_name || ' s. ' || a.section_number) "
                            "  AS title, "
                            "c.citation, COALESCE(c.pdf_url, a.source_url) AS url "
                            "FROM message_sources ms "
                            "LEFT JOIN cases c ON c.record_id = ms.record_id "
                            "LEFT JOIN act_sections a ON a.record_id = ms.record_id "
                            "WHERE ms.message_id = ANY(:ids) "
                            "ORDER BY ms.message_id, ms.source_id"
                        ),
                        {"ids": list(by_id)},
                    )
                )
                for s in srcs:
                    by_id[s.pop("message_id")]["sources"].append(s)
            return msgs

    async def save_exchange(
        self, user_id, conversation_id, question, answer: FinalAnswer, *, count_usage
    ) -> UUID:
        """Step 11 (Save): the question, the answer, its sources, any removed citations
        and the usage count, all in ONE transaction so they stand or fall together.

        clock_timestamp() (not now()) gives the question and the answer different times;
        now() is frozen for a whole transaction, which would let history sort the answer
        before its own question."""
        async with self.engine.begin() as c:
            await c.execute(
                text(
                    "INSERT INTO messages (conversation_id, role, content, created_at) "
                    "VALUES (:c, 'user', :t, clock_timestamp())"
                ),
                {"c": conversation_id, "t": question},
            )
            message_id = (
                await c.execute(
                    text(
                        "INSERT INTO messages (conversation_id, role, content, "
                        "rewritten_query, model, tokens_in, tokens_out, latency_ms, "
                        "from_cache, scope, route, safety, jev_used, created_at) "
                        "VALUES (:c, 'assistant', :t, :rq, :m, :ti, :to, :l, :fc, :sc, "
                        ":r, :sa, :j, clock_timestamp()) RETURNING id"
                    ),
                    {
                        "c": conversation_id,
                        "t": answer.text,
                        "rq": answer.rewritten_query,
                        "m": answer.model,
                        "ti": answer.tokens_in,
                        "to": answer.tokens_out,
                        "l": answer.latency_ms,
                        "fc": answer.from_cache,
                        "sc": answer.scope,
                        "r": answer.route,
                        "sa": answer.safety,
                        "j": answer.jev_used,
                    },
                )
            ).scalar_one()
            for s in answer.sources:
                await c.execute(
                    text(
                        "INSERT INTO message_sources (message_id, source_id, record_id, "
                        "chunk_id, rank, rerank_score, verified, relevance, support, "
                        "support_confidence) VALUES (:m, :sid, :rid, :ch, :rk, :rs, :v, "
                        ":rel, :sup, :conf)"
                    ),
                    {
                        "m": message_id,
                        "sid": s.source_id,
                        "rid": s.record_id,
                        "ch": s.chunk_id,
                        "rk": s.rank,
                        "rs": s.rerank_score,
                        "v": s.verified,
                        "rel": s.relevance,
                        "sup": s.support,
                        "conf": s.support_confidence,
                    },
                )
            for r in answer.removed:
                await c.execute(
                    text(
                        "INSERT INTO invented_citation_log (message_id, query, model, "
                        "cited_text, reason) VALUES (:m, :q, :mo, :ct, :r)"
                    ),
                    {
                        "m": message_id,
                        "q": answer.rewritten_query,
                        "mo": answer.model,
                        "ct": r.cited_text,
                        "r": r.reason,
                    },
                )
            await c.execute(
                text(
                    "UPDATE conversations SET message_count = message_count + 2, "
                    "title = COALESCE(title, left(:q, 80)), "
                    "rolling_summary = COALESCE(:rs, rolling_summary) WHERE id=:c"
                ),
                {"q": question, "rs": answer.rolling_summary, "c": conversation_id},
            )
            if count_usage:
                await c.execute(
                    text(
                        "INSERT INTO usage_daily (user_id, date, feature, requests, "
                        "tokens_in, tokens_out) VALUES (:u, CURRENT_DATE, 'research', 1, "
                        ":ti, :to) ON CONFLICT (user_id, date, feature) DO UPDATE SET "
                        "requests = usage_daily.requests + 1, "
                        "tokens_in = usage_daily.tokens_in + EXCLUDED.tokens_in, "
                        "tokens_out = usage_daily.tokens_out + EXCLUDED.tokens_out"
                    ),
                    {
                        "u": user_id,
                        "ti": answer.tokens_in or 0,
                        "to": answer.tokens_out or 0,
                    },
                )
            return message_id

    # ---- records --------------------------------------------------------------
    async def get_case(self, record_id: str) -> Row | None:
        async with self.engine.connect() as c:
            return _one(
                await c.execute(
                    text(
                        "SELECT record_id, title, court, decision_date, case_number, "
                        "citation, disposition, outcome_label, pdf_url, full_text "
                        "FROM cases WHERE record_id=:r"
                    ),
                    {"r": record_id},
                )
            )

    async def get_act_section(self, act: str, section: str) -> Row | None:
        candidates, year = act_slug_candidates(act)
        sql = (
            "SELECT record_id, act_name, act_year, section_number, section_title, text, "
            "in_force, act_status, source_url FROM act_sections "
            "WHERE (act_slug = ANY(:names) OR act_slug_base = ANY(:names)) "
            "AND lower(section_number) = lower(:s)"
        )
        params: dict[str, Any] = {"names": candidates, "s": section}
        if year is not None:
            sql += " AND (act_year = :y OR act_year IS NULL)"
            params["y"] = year
        sql += " ORDER BY act_year DESC NULLS LAST LIMIT 1"
        async with self.engine.connect() as c:
            return _one(await c.execute(text(sql), params))

    async def data_as_of(self, court: str | None) -> date | None:
        async with self.engine.connect() as c:
            if court is not None:
                r = await c.execute(
                    text(
                        "SELECT data_as_of FROM court_coverage WHERE court=:c "
                        "ORDER BY snapshot_version DESC LIMIT 1"
                    ),
                    {"c": court},
                )
                found = r.scalar_one_or_none()
                if found:
                    return found
            r = await c.execute(
                text(
                    "SELECT data_as_of FROM court_coverage "
                    "ORDER BY snapshot_version DESC, data_as_of DESC LIMIT 1"
                )
            )
            return r.scalar_one_or_none()

    async def stats_live(self, court: str) -> bool:
        async with self.engine.connect() as c:
            r = await c.execute(
                text("SELECT bool_or(stats_live) FROM court_coverage WHERE court=:c"),
                {"c": court},
            )
            return bool(r.scalar_one_or_none())

    async def case_stats(self, court: str, year: int | None) -> list[Row]:
        sql = (
            "SELECT extract(year FROM decision_date)::int AS year, outcome_label, "
            "count(*)::int AS count FROM cases WHERE court=:c "
            "AND outcome_label IS NOT NULL AND is_final_outcome IS TRUE "
            "AND decision_date IS NOT NULL"
        )
        params: dict[str, Any] = {"c": court}
        if year is not None:
            sql += " AND extract(year FROM decision_date) = :y"
            params["y"] = year
        sql += " GROUP BY 1, 2 ORDER BY 1 DESC, 2"
        async with self.engine.connect() as c:
            return _rows(await c.execute(text(sql), params))

    # ---- privacy --------------------------------------------------------------
    async def list_consents(self, user_id) -> list[Row]:
        async with self.engine.connect() as c:
            return _rows(
                await c.execute(
                    text(
                        "SELECT id, notice_version, purpose, given_at, withdrawn_at "
                        "FROM consents WHERE user_id=:u ORDER BY given_at DESC, id"
                    ),
                    {"u": user_id},
                )
            )

    async def give_consent(self, user_id, notice_version, purpose) -> Row:
        async with self.engine.begin() as c:
            return _one(
                await c.execute(
                    text(
                        "INSERT INTO consents (user_id, notice_version, purpose, given_at) "
                        "VALUES (:u, :v, :p, now()) RETURNING id, notice_version, "
                        "purpose, given_at, withdrawn_at"
                    ),
                    {"u": user_id, "v": notice_version, "p": purpose},
                )
            )

    async def withdraw_consent(self, user_id, purpose) -> int:
        async with self.engine.begin() as c:
            r = await c.execute(
                text(
                    "UPDATE consents SET withdrawn_at = now() "
                    "WHERE user_id=:u AND purpose=:p AND withdrawn_at IS NULL"
                ),
                {"u": user_id, "p": purpose},
            )
            return r.rowcount

    async def account_cleanup_info(self, user_id) -> Row:
        """What the background job needs to clean OUTSIDE PostgreSQL (S3, Qdrant,
        Firebase, Razorpay). IDs and paths only, never document text."""
        async with self.engine.connect() as c:
            uid = (
                await c.execute(
                    text("SELECT firebase_uid FROM users WHERE id=:u"), {"u": user_id}
                )
            ).scalar_one_or_none()
            docs = _rows(
                await c.execute(
                    text("SELECT id, storage_path FROM documents WHERE user_id=:u"),
                    {"u": user_id},
                )
            )
            subs = (
                (
                    await c.execute(
                        text(
                            "SELECT razorpay_subscription_id FROM subscriptions "
                            "WHERE user_id=:u AND razorpay_subscription_id IS NOT NULL"
                        ),
                        {"u": user_id},
                    )
                )
                .scalars()
                .all()
            )
        return {
            "firebase_uid": uid,
            "document_ids": [str(d["id"]) for d in docs],
            "storage_paths": [d["storage_path"] for d in docs if d["storage_path"]],
            "razorpay_subscription_ids": list(subs),
        }

    async def owns_organisation(self, user_id) -> bool:
        async with self.engine.connect() as c:
            r = await c.execute(
                text("SELECT 1 FROM organisations WHERE owner_user_id=:u LIMIT 1"),
                {"u": user_id},
            )
            return r.first() is not None

    async def delete_user(self, user_id) -> None:
        """Hard delete. Foreign keys cascade to chats, messages, sources, documents,
        chunks, consents, usage and feedback. Subscriptions and audit rows are kept
        (user_id set to NULL) because payment records must be kept by law."""
        try:
            async with self.engine.begin() as c:
                await c.execute(text("DELETE FROM users WHERE id=:u"), {"u": user_id})
        except IntegrityError as exc:
            raise OwnsOrganisation from exc

    async def export_user(self, user_id) -> Row:
        async with self.engine.connect() as c:
            user = _one(
                await c.execute(
                    text(
                        "SELECT id, email, name, role, plan, status, created_at "
                        "FROM users WHERE id=:u"
                    ),
                    {"u": user_id},
                )
            )
            convs = _rows(
                await c.execute(
                    text(
                        "SELECT id, module, title, message_count, created_at "
                        "FROM conversations WHERE user_id=:u ORDER BY created_at, id"
                    ),
                    {"u": user_id},
                )
            )
            msgs = _rows(
                await c.execute(
                    text(
                        "SELECT m.conversation_id, m.id, m.role, m.content, m.created_at "
                        "FROM messages m JOIN conversations c ON c.id = m.conversation_id "
                        "WHERE c.user_id=:u ORDER BY m.created_at, m.id"
                    ),
                    {"u": user_id},
                )
            )
            docs = _rows(
                await c.execute(
                    text(
                        "SELECT id, filename, mime_type, size_bytes, page_count, status, "
                        "created_at FROM documents WHERE user_id=:u ORDER BY created_at, id"
                    ),
                    {"u": user_id},
                )
            )
        for conv in convs:
            conv["messages"] = [
                {k: v for k, v in m.items() if k != "conversation_id"}
                for m in msgs
                if m["conversation_id"] == conv["id"]
            ]
        return {
            "account": user,
            "consents": await self.list_consents(user_id),
            "conversations": convs,
            "documents": docs,  # the list only: file contents are never in the export
        }

    async def add_audit(self, user_id, action, target_id, ip, request_id) -> None:
        # Never put document text in here (docs/DATA-MODEL.md).
        async with self.engine.begin() as c:
            await c.execute(
                text(
                    "INSERT INTO audit_log (user_id, action, target_id, ip, request_id) "
                    "VALUES (:u, :a, :t, :ip, :r)"
                ),
                {"u": user_id, "a": action, "t": target_id, "ip": ip, "r": request_id},
            )

    # ---- feedback, documents, billing ----------------------------------------
    async def add_feedback(self, user_id, message_id, rating, reason, comment) -> bool:
        """False if the message is not in one of this user's own conversations."""
        async with self.engine.begin() as c:
            owned = await c.execute(
                text(
                    "SELECT 1 FROM messages m JOIN conversations c "
                    "ON c.id = m.conversation_id WHERE m.id=:m AND c.user_id=:u"
                ),
                {"m": message_id, "u": user_id},
            )
            if owned.first() is None:
                return False
            await c.execute(
                text(
                    "INSERT INTO feedback (message_id, user_id, rating, reason, comment) "
                    "VALUES (:m, :u, :r, :re, :co) ON CONFLICT (message_id, user_id) "
                    "DO UPDATE SET rating=EXCLUDED.rating, reason=EXCLUDED.reason, "
                    "comment=EXCLUDED.comment"
                ),
                {
                    "m": message_id,
                    "u": user_id,
                    "r": rating,
                    "re": reason,
                    "co": comment,
                },
            )
            return True

    async def create_document(
        self, doc_id, user_id, filename, mime_type, size_bytes, storage_path
    ) -> Row:
        async with self.engine.begin() as c:
            return _one(
                await c.execute(
                    text(
                        "INSERT INTO documents (id, user_id, filename, mime_type, "
                        "size_bytes, storage_path) VALUES (:id, :u, :f, :m, :s, :p) "
                        "RETURNING id, filename, status, fail_reason, page_count, "
                        "expires_at, storage_path"
                    ),
                    {
                        "id": doc_id,
                        "u": user_id,
                        "f": filename,
                        "m": mime_type,
                        "s": size_bytes,
                        "p": storage_path,
                    },
                )
            )

    async def get_document(self, user_id, doc_id) -> Row | None:
        async with self.engine.connect() as c:
            return _one(
                await c.execute(
                    text(
                        "SELECT id, filename, status, fail_reason, page_count, "
                        "expires_at, storage_path FROM documents "
                        "WHERE id=:id AND user_id=:u AND deleted_at IS NULL"
                    ),
                    {"id": doc_id, "u": user_id},
                )
            )

    async def delete_document(self, user_id, doc_id) -> Row | None:
        """Removes the row and (by cascade) its extracted text chunks. Returns what the
        background job needs to remove the S3 file and the Qdrant vectors."""
        async with self.engine.begin() as c:
            return _one(
                await c.execute(
                    text(
                        "DELETE FROM documents WHERE id=:id AND user_id=:u "
                        "RETURNING id, storage_path"
                    ),
                    {"id": doc_id, "u": user_id},
                )
            )

    async def update_subscription_status(self, razorpay_id: str, status: str) -> int:
        async with self.engine.begin() as c:
            r = await c.execute(
                text(
                    "UPDATE subscriptions SET status=:s WHERE razorpay_subscription_id=:r"
                ),
                {"s": status, "r": razorpay_id},
            )
            return r.rowcount


__all__ = ["OwnsOrganisation", "SqlStore", "Store"]
