"""PostgreSQL implementation of Repo, and of core's UsageMeter, ConversationStore and
CitationLog Protocols (core/contracts.py). Plain SQL through SQLAlchemy; no business
rules here, only reading and writing rows.

Pipeline step 11 (Save) lives in PgRepo.save(); the usage meter counts one answer in
count_one(); invented_citation_log rows are written by write().
"""

# ruff: noqa: E501  (long SQL strings)
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import Engine, create_engine, text
from starlette.concurrency import run_in_threadpool

from api.repo import _last_message, slugify_act, split_paragraphs

_REASON = {
    "not_retrieved": "not retrieved",
    "record_missing": "record missing",
    "quote_not_found": "quote not found",
    "claim_not_supported": "claim not supported",
}
_PLAN_LIMIT = {
    "free": "PLAN_LIMIT_FREE", "student": "PLAN_LIMIT_STUDENT",
    "pro": "PLAN_LIMIT_PRO", "chambers": "PLAN_LIMIT_CHAMBERS",
}  # fmt: skip


def make_engine(url: str) -> Engine:
    # Sync engine; calls run in a thread pool so they never block the event loop.
    # (Chosen over the async engine, which needs the extra `greenlet` dependency.)
    return create_engine(url, pool_pre_ping=True)


class PgRepo:
    def __init__(self, engine: Engine, settings: Any):
        self.engine, self.settings = engine, settings

    def _rows_sync(self, sql: str, p: dict) -> list[dict]:
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(text(sql), p)]

    def _exec_sync(self, sql: str, p: dict) -> list[dict]:
        with self.engine.begin() as c:
            res = c.execute(text(sql), p)
            return [dict(r._mapping) for r in res] if res.returns_rows else []

    async def _rows(self, sql: str, **p) -> list[dict]:
        return await run_in_threadpool(self._rows_sync, sql, p)

    async def _exec(self, sql: str, **p) -> list[dict]:
        return await run_in_threadpool(self._exec_sync, sql, p)

    @staticmethod
    def _s(row: dict) -> dict:
        return {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in row.items()}

    async def upsert_user(self, uid, email, name):
        rows = await self._exec(
            """INSERT INTO users (firebase_uid, email, name) VALUES (:u, :e, :n)
               ON CONFLICT (firebase_uid) DO UPDATE SET updated_at = now(),
                 email = COALESCE(EXCLUDED.email, users.email)
               RETURNING id, firebase_uid, email, name, role, plan, status""",
            u=uid, e=email, n=name,
        )  # fmt: skip
        row = self._s(rows[0])
        row.pop("status")
        return row

    async def answers_this_month(self, user_id):
        rows = await self._rows(
            """SELECT COALESCE(SUM(requests), 0) AS n FROM usage_daily
               WHERE user_id = :u AND date >= date_trunc('month', current_date)""",
            u=user_id,
        )
        return int(rows[0]["n"])

    async def create_conversation(self, user_id, module, document_id):
        rows = await self._exec(
            """INSERT INTO conversations (user_id, module, document_id)
               VALUES (:u, :m, :d) RETURNING *""",
            u=user_id, m=module, d=document_id,
        )  # fmt: skip
        return self._s(rows[0])

    async def list_conversations(self, user_id, cursor, limit):
        off = int(cursor) if cursor else 0
        rows = await self._rows(
            """SELECT * FROM conversations WHERE user_id = :u
               ORDER BY created_at DESC, id DESC LIMIT :l OFFSET :o""",
            u=user_id, l=limit + 1, o=off,
        )  # fmt: skip
        nxt = str(off + limit) if len(rows) > limit else None
        return [self._s(r) for r in rows[:limit]], nxt

    async def get_conversation(self, user_id, conv_id):
        conv = await self._rows(
            "SELECT * FROM conversations WHERE id = :c AND user_id = :u",
            c=conv_id,
            u=user_id,
        )  # user_id filter: another user's chat looks absent
        if not conv:
            return None
        msgs = await self._rows(
            "SELECT id, role, content, from_cache, created_at FROM messages "
            "WHERE conversation_id = :c ORDER BY created_at, id",
            c=conv_id,
        )
        srcs = await self._rows(
            """SELECT ms.message_id, ms.source_id, ms.record_id, ms.verified, ms.support,
                      COALESCE(c.title, a.act_name) AS title,
                      c.citation AS citation_string,
                      COALESCE(c.pdf_url, a.source_url) AS url,
                      (a.record_id IS NOT NULL) AS is_act, a.act_name, a.act_year,
                      a.section_number
               FROM message_sources ms
               JOIN messages m ON m.id = ms.message_id
               LEFT JOIN cases c ON c.record_id = ms.record_id
               LEFT JOIN act_sections a ON a.record_id = ms.record_id
               WHERE m.conversation_id = :c AND ms.verified ORDER BY ms.source_id""",
            c=conv_id,
        )
        by_msg: dict[str, list[dict]] = {}
        for s in srcs:
            by_msg.setdefault(str(s["message_id"]), []).append(
                {
                    "source_id": s["source_id"], "record_id": s["record_id"],
                    "kind": "act" if s["is_act"] else "judgment",
                    "title": s["title"] if s["is_act"] else None, "citation_string": s["citation_string"],
                    "url": s["url"],
                    "act_slug": slugify_act(s["act_name"], s["act_year"]) if s["is_act"] else None,
                    "section": s["section_number"] if s["is_act"] else None,
                    "status": {"partly": "partly", None: "unchecked"}.get(s["support"], "verified"),
                }
            )  # fmt: skip
        out = self._s(conv[0])
        out["messages"] = [
            {**self._s(m), "citations": by_msg.get(str(m["id"]), [])} for m in msgs
        ]
        return out

    async def add_user_message(self, user_id, conv_id, content):
        # The ownership check is inside the SQL: a foreign conversation inserts nothing.
        rows = await self._exec(
            """INSERT INTO messages (conversation_id, role, content)
               SELECT id, 'user', :t FROM conversations
               WHERE id = :c AND user_id = :u RETURNING id""",
            c=conv_id, t=content, u=user_id,
        )  # fmt: skip
        if not rows:
            return None
        await self._exec(
            """UPDATE conversations SET message_count = message_count + 1,
               title = COALESCE(title, left(:t, 80)), updated_at = now()
               WHERE id = :c AND user_id = :u""",
            c=conv_id, t=content, u=user_id,
        )  # fmt: skip
        return str(rows[0]["id"])

    async def history(self, user_id, conv_id, exclude_id):
        rows = await self._rows(
            """SELECT m.role, m.content FROM messages m
               JOIN conversations cv ON cv.id = m.conversation_id
               WHERE cv.id = :c AND cv.user_id = :u AND m.id <> :x
               ORDER BY m.created_at, m.id""",
            c=conv_id, u=user_id, x=exclude_id,
        )  # fmt: skip
        conv = await self._rows(
            "SELECT rolling_summary FROM conversations WHERE id = :c AND user_id = :u",
            c=conv_id, u=user_id,
        )  # fmt: skip
        turns = [(r["role"], r["content"]) for r in rows]
        return turns, (conv[0]["rolling_summary"] or "") if conv else ""

    async def get_case(self, record_id):
        rows = await self._rows(
            """SELECT record_id, title, court, decision_date, case_number,
                      citation AS citation_string, pdf_url AS url, full_text
               FROM cases WHERE record_id = :r""",
            r=record_id,
        )
        if not rows:
            return None
        row = rows[0]
        row["paragraphs"] = split_paragraphs(row.pop("full_text"))
        return row

    async def get_section(self, act_slug, number):
        rows = await self._rows(
            """SELECT record_id, act_name, act_year, section_number AS section,
                      section_title, text, in_force, act_status, source_url
               FROM act_sections WHERE section_number = :n""",
            n=number,
        )
        for r in rows:
            if slugify_act(r["act_name"], r["act_year"]) == act_slug:
                # in-force shown ONLY where act_status is filled (CLAUDE.md section 6)
                r["act_slug"] = act_slug
                r["act_status_checked"] = bool(r["act_status"])
                r["in_force"] = r["in_force"] if r["act_status_checked"] else None
                return r
        return None

    async def data_as_of(self):
        rows = await self._rows(
            "SELECT data_as_of, snapshot_version FROM court_coverage "
            "ORDER BY data_as_of DESC LIMIT 1"
        )
        if not rows:
            return None
        d: date = rows[0]["data_as_of"]
        return d.isoformat(), rows[0]["snapshot_version"]

    async def stats(self):
        live = await self._rows(
            "SELECT bool_or(stats_live) AS live FROM court_coverage"
        )
        if not (live and live[0]["live"]):
            return [], False
        rows = await self._rows(
            """SELECT court, extract(year FROM decision_date)::int AS year,
                      outcome_label, count(*) AS count
               FROM cases WHERE is_final_outcome AND outcome_label IS NOT NULL
               GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"""
        )
        return rows, True

    async def add_feedback(self, user_id, data):
        await self._exec(
            """INSERT INTO feedback (message_id, user_id, rating, reason, comment)
               VALUES (:m, :u, :r, :re, :c)""",
            m=str(data["message_id"]), u=user_id, r=data["rating"],
            re=data.get("reason"), c=data.get("comment"),
        )  # fmt: skip

    async def list_consents(self, user_id):
        return [
            self._s(r)
            for r in await self._rows(
                "SELECT id, notice_version, purpose, given_at, withdrawn_at "
                "FROM consents WHERE user_id = :u ORDER BY given_at",
                u=user_id,
            )
        ]

    async def add_consent(self, user_id, notice_version, purpose):
        rows = await self._exec(
            """INSERT INTO consents (user_id, notice_version, purpose) VALUES (:u, :v, :p)
               RETURNING id, notice_version, purpose, given_at, withdrawn_at""",
            u=user_id, v=notice_version, p=purpose,
        )  # fmt: skip
        return self._s(rows[0])

    async def withdraw_consent(self, user_id, consent_id):
        rows = await self._exec(
            """UPDATE consents SET withdrawn_at = now(), updated_at = now()
               WHERE id = :c AND user_id = :u AND withdrawn_at IS NULL RETURNING id""",
            c=consent_id, u=user_id,
        )  # fmt: skip
        return bool(rows)

    # --- core's UsageMeter ---------------------------------------------------
    async def allowed(self, user_id: str, plan: str) -> bool:
        limit = getattr(self.settings, _PLAN_LIMIT.get(plan, "PLAN_LIMIT_FREE"), None)
        if limit is None:  # limits are undecided (owner's call): do not block
            return True
        return await self.answers_this_month(user_id) < limit

    async def count_one(self, user_id: str) -> None:
        await self._exec(
            """INSERT INTO usage_daily (user_id, date, feature, requests)
               VALUES (:u, current_date, 'research', 1)
               ON CONFLICT (user_id, date, feature)
               DO UPDATE SET requests = usage_daily.requests + 1, updated_at = now()""",
            u=user_id,
        )

    # --- core's ConversationStore (pipeline step 11, Save) -----------------------
    async def save(self, request: Any, result: Any) -> None:
        if not request.conversation_id or result.outcome != "answered":
            return
        a = result.answer

        def _write() -> str | None:
            with self.engine.begin() as c:
                row = c.execute(
                    text(
                        """INSERT INTO messages (conversation_id, role, content, model,
                               tokens_in, tokens_out, from_cache)
                           SELECT id, 'assistant', :t, :m, :ti, :to, :fc
                           FROM conversations WHERE id = :c AND user_id = :u
                           RETURNING id"""
                    ),
                    dict(c=request.conversation_id, u=request.user_id, t=a.text, m=result.model or None,
                         ti=result.input_tokens, to=result.output_tokens, fc=result.cache_hit),
                )  # fmt: skip
                mid = row.scalar_one_or_none()
                if mid is None:  # conversation is not this user's: write nothing
                    return None
                for rank, cit in enumerate(a.citations, 1):
                    c.execute(
                        text(
                            """INSERT INTO message_sources (message_id, source_id, record_id,
                                   rank, verified, support)
                               VALUES (:m, :s, :r, :k, true, :sup)
                               ON CONFLICT DO NOTHING"""
                        ),
                        dict(m=mid, s=cit.source_id, r=cit.record_id, k=rank,
                             sup={"verified": "supports", "partly": "partly"}.get(cit.status)),
                    )  # fmt: skip
                c.execute(
                    text(
                        "UPDATE conversations SET message_count = message_count + 1, "
                        "updated_at = now() WHERE id = :c"
                    ),
                    dict(c=request.conversation_id),
                )
            return str(mid)

        mid = await run_in_threadpool(_write)
        holder = _last_message.get(None)
        if holder is not None and mid is not None:
            holder["id"] = mid

    # --- core's CitationLog ----------------------------------------------------
    async def write(self, question: str, model: str, removed: Sequence[Any]) -> None:
        for r in removed:
            await self._exec(
                """INSERT INTO invented_citation_log (query, model, cited_text, reason)
                   VALUES (:q, :m, :t, :r)""",
                q=question, m=model, t=r.sentence or r.source_id,
                r=_REASON[r.reason],
            )  # fmt: skip
