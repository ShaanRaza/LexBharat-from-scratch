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
from core.spend import summarise

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
               WHERE user_id = :u AND feature = 'research'
                 AND date >= date_trunc('month', current_date)""",
            u=user_id,
        )
        return int(rows[0]["n"])

    async def create_conversation(self, user_id, module, document_id, matter_id=None):
        # The matter must be this user's: a foreign matter id inserts NULL (unfiled).
        rows = await self._exec(
            """INSERT INTO conversations (user_id, module, document_id, matter_id)
               VALUES (:u, :m, :d,
                       (SELECT id FROM matters WHERE id = :mt AND user_id = :u))
               RETURNING *""",
            u=user_id, m=module, d=document_id, mt=matter_id,
        )  # fmt: skip
        return self._s(rows[0])

    async def list_conversations(
        self, user_id, cursor, limit, matter_id=None, unfiled=False
    ):
        off = int(cursor) if cursor else 0
        rows = await self._rows(
            """SELECT * FROM conversations WHERE user_id = :u
                 AND (CAST(:mt AS uuid) IS NULL OR matter_id = CAST(:mt AS uuid))
                 AND (NOT :uf OR matter_id IS NULL)
               ORDER BY created_at DESC, id DESC LIMIT :l OFFSET :o""",
            u=user_id, mt=matter_id, uf=unfiled, l=limit + 1, o=off,
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
            "SELECT id, role, content, from_cache, created_at, shaped_by_upload, "
            "shaped_by_matter_fact FROM messages "
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
            """INSERT INTO messages (conversation_id, role, content, matter_id,
                   shaped_by_upload, shaped_by_matter_fact)
               SELECT id, 'user', :t, matter_id, false, false FROM conversations
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

    # --- share links (O14) ---------------------------------------------------------
    async def get_message_for_share(self, user_id, message_id):
        rows = await self._rows(
            """SELECT m.id, m.role, m.shaped_by_upload, m.shaped_by_matter_fact
                 FROM messages m JOIN conversations c ON c.id = m.conversation_id
                WHERE m.id = :m AND c.user_id = :u""",
            m=message_id, u=user_id,
        )  # fmt: skip
        return self._s(rows[0]) if rows else None

    async def create_share_link(self, user_id, message_id, token_hash, expires_at):
        # The database trigger share_links_guard refuses an answer that is not the
        # user's own, not an answer, or shaped by an upload or a matter fact.
        rows = await self._exec(
            """INSERT INTO share_links (user_id, message_id, token_hash, expires_at)
               VALUES (:u, :m, :h, :e) RETURNING id, message_id, expires_at, created_at""",
            u=user_id, m=message_id, h=token_hash, e=expires_at,
        )  # fmt: skip
        return self._s(rows[0])

    async def list_share_links(self, user_id):
        rows = await self._rows(
            """SELECT id, message_id, expires_at, revoked_at, created_at
                 FROM share_links WHERE user_id = :u ORDER BY created_at DESC""",
            u=user_id,
        )  # the token hash is never returned
        return [self._s(r) for r in rows]

    async def revoke_share_link(self, user_id, link_id):
        rows = await self._exec(
            """UPDATE share_links SET revoked_at = now(), updated_at = now()
                WHERE id = :l AND user_id = :u AND revoked_at IS NULL RETURNING id""",
            l=link_id, u=user_id,
        )  # fmt: skip
        return bool(rows)

    async def get_shared_answer(self, token_hash):
        """The public read: the live row is checked on EVERY call (not revoked, not
        expired, still an unshaped assistant answer). The owner's id is used only inside
        and is never returned."""
        rows = await self._rows(
            """SELECT s.user_id, s.expires_at, m.id AS message_id, m.conversation_id
                 FROM share_links s
                 JOIN messages m ON m.id = s.message_id
                 JOIN conversations c ON c.id = m.conversation_id AND c.user_id = s.user_id
                WHERE s.token_hash = :h AND s.revoked_at IS NULL AND s.expires_at > now()
                  AND m.role = 'assistant'
                  AND NOT m.shaped_by_upload AND NOT m.shaped_by_matter_fact""",
            h=token_hash,
        )  # fmt: skip
        if not rows:
            return None
        r = rows[0]
        conv = await self.get_conversation(str(r["user_id"]), str(r["conversation_id"]))
        if conv is None:
            return None
        msgs = conv["messages"]
        idx = next(
            (i for i, m in enumerate(msgs) if str(m["id"]) == str(r["message_id"])),
            None,
        )
        if idx is None:
            return None
        question = next(
            (m["content"] for m in reversed(msgs[:idx]) if m["role"] == "user"), ""
        )
        return {
            "question": question, "text": msgs[idx]["content"],
            "citations": msgs[idx]["citations"], "expires_at": r["expires_at"],
        }  # fmt: skip

    # --- matters, documents, audit (A52) -------------------------------------------
    async def create_matter(self, user_id, title, kind):
        rows = await self._exec(
            """INSERT INTO matters (user_id, title, kind) VALUES (:u, :t, :k)
               RETURNING *""",
            u=user_id, t=title, k=kind,
        )  # fmt: skip
        return self._s(rows[0])

    _MATTER_SQL = """SELECT m.*,
        (SELECT count(*) FROM conversations c
          WHERE c.matter_id = m.id AND c.user_id = m.user_id) AS conversation_count,
        (SELECT count(*) FROM documents d
          WHERE d.matter_id = m.id AND d.user_id = m.user_id) AS document_count
        FROM matters m"""

    async def get_matter(self, user_id, matter_id):
        rows = await self._rows(
            self._MATTER_SQL + " WHERE m.id = :m AND m.user_id = :u",
            m=matter_id, u=user_id,
        )  # user_id filter: another user's matter looks absent  # fmt: skip
        return self._s(rows[0]) if rows else None

    async def list_matters(self, user_id, status):
        rows = await self._rows(
            self._MATTER_SQL + """ WHERE m.user_id = :u
                 AND (CAST(:s AS text) IS NULL OR m.status = CAST(:s AS text))
               ORDER BY m.updated_at DESC, m.id DESC""",
            u=user_id, s=status,
        )  # fmt: skip
        return [self._s(r) for r in rows]

    async def update_matter(self, user_id, matter_id, title, status):
        rows = await self._exec(
            """UPDATE matters SET
                 title = COALESCE(CAST(:t AS text), title),
                 status = COALESCE(CAST(:s AS text), status),
                 archived_at = CASE
                   WHEN CAST(:s AS text) = 'archived' AND status <> 'archived' THEN now()
                   WHEN CAST(:s AS text) = 'active' THEN NULL
                   ELSE archived_at END,
                 updated_at = now()
               WHERE id = :m AND user_id = :u RETURNING id""",
            t=title, s=status, m=matter_id, u=user_id,
        )  # fmt: skip
        return await self.get_matter(user_id, matter_id) if rows else None

    async def set_conversation_matter(self, user_id, conv_id, matter_id):
        # Both the conversation AND the matter must be this user's.
        rows = await self._exec(
            """UPDATE conversations SET matter_id = CAST(:mt AS uuid), updated_at = now()
               WHERE id = :c AND user_id = :u
                 AND (CAST(:mt AS uuid) IS NULL OR EXISTS
                      (SELECT 1 FROM matters WHERE id = CAST(:mt AS uuid) AND user_id = :u))
               RETURNING id""",
            mt=matter_id, c=conv_id, u=user_id,
        )  # fmt: skip
        return bool(rows)

    async def search_user_work(self, user_id, q, limit):
        """PostgreSQL full text over this user's conversation titles and messages. The
        user_id filter is in BOTH halves; core/user_search.py checks the rows again."""
        rows = await self._rows(
            """SELECT * FROM (
                 SELECT 'conversation' AS kind, c.user_id, c.id AS conversation_id,
                        NULL::uuid AS message_id, c.matter_id, c.title,
                        ts_headline('english', COALESCE(c.title, ''), qy,
                                    'StartSel=, StopSel=, MaxFragments=1, MaxWords=25')
                          AS snippet,
                        c.updated_at AS created_at,
                        ts_rank(to_tsvector('english', COALESCE(c.title, '')), qy) AS rank
                   FROM conversations c, websearch_to_tsquery('english', :q) qy
                  WHERE c.user_id = :u
                    AND to_tsvector('english', COALESCE(c.title, '')) @@ qy
                 UNION ALL
                 SELECT 'message', c.user_id, m.conversation_id, m.id, c.matter_id,
                        c.title,
                        ts_headline('english', m.content, qy,
                                    'StartSel=, StopSel=, MaxFragments=1, MaxWords=25'),
                        m.created_at, ts_rank(to_tsvector('english', m.content), qy)
                   FROM messages m
                   JOIN conversations c ON c.id = m.conversation_id,
                        websearch_to_tsquery('english', :q) qy
                  WHERE c.user_id = :u
                    AND to_tsvector('english', m.content) @@ qy
               ) t ORDER BY rank DESC, created_at DESC LIMIT :l""",
            q=q, u=user_id, l=limit,
        )  # fmt: skip
        out = []
        for r in rows:
            r = self._s(r)
            r.pop("rank", None)
            out.append(r)
        return out

    async def matter_document_ids(self, user_id, matter_id):
        rows = await self._rows(
            "SELECT id FROM documents WHERE matter_id = :m AND user_id = :u",
            m=matter_id, u=user_id,
        )  # fmt: skip
        return [str(r["id"]) for r in rows]

    async def delete_matter(self, user_id, matter_id, delete_conversations):
        """Deletes the matter row. Its conversations and documents become unfiled
        (ON DELETE SET NULL) unless `delete_conversations`, which removes the
        conversations (and their messages) first. Documents are NEVER deleted here:
        core/doc_delete.py does that, with S3 and Qdrant, before this is called."""
        n = 0
        if delete_conversations:
            rows = await self._exec(
                "DELETE FROM conversations WHERE matter_id = :m AND user_id = :u RETURNING id",
                m=matter_id, u=user_id,
            )  # fmt: skip
            n = len(rows)
        await self._exec(
            "DELETE FROM matters WHERE id = :m AND user_id = :u RETURNING id",
            m=matter_id, u=user_id,
        )  # fmt: skip
        return n

    async def create_document(self, user_id, filename, matter_id, text):
        rows = await self._exec(
            """INSERT INTO documents (user_id, filename, mime_type, size_bytes, status,
                   matter_id) VALUES (:u, :f, 'application/pdf', :s, 'ready', :m)
               RETURNING id""",
            u=user_id, f=filename, s=len(text), m=matter_id,
        )  # fmt: skip
        doc_id = str(rows[0]["id"])
        await self._exec(
            """INSERT INTO document_chunks (document_id, page_no, char_start, char_end,
                   text) VALUES (:d, 1, 0, :e, :t)""",
            d=doc_id, e=len(text), t=text,
        )  # fmt: skip
        return doc_id

    async def delete_document_rows(self, user_id, document_id):
        rows = await self._exec(
            "DELETE FROM documents WHERE id = :d AND user_id = :u RETURNING id",
            d=document_id, u=user_id,
        )  # fmt: skip
        return bool(rows)  # document_chunks go with it (ON DELETE CASCADE)

    async def document_rows_remaining(self, document_id):
        rows = await self._rows(
            """SELECT (SELECT count(*) FROM documents WHERE id = :d)
                    + (SELECT count(*) FROM document_chunks WHERE document_id = :d) AS n""",
            d=document_id,
        )  # fmt: skip
        return int(rows[0]["n"])

    async def audit(self, user_id, action, target_id):
        await self._exec(
            "INSERT INTO audit_log (user_id, action, target_id) VALUES (:u, :a, :t)",
            u=user_id, a=action, t=target_id,
        )  # fmt: skip

    async def deleted_documents(self, days):
        rows = await self._rows(
            """SELECT DISTINCT user_id, substr(target_id, 10) AS document_id
               FROM audit_log
               WHERE action = 'delete' AND target_id LIKE 'document:%'
                 AND user_id IS NOT NULL AND at > now() - make_interval(days => :n)""",
            n=days,
        )  # fmt: skip
        return [(str(r["user_id"]), r["document_id"]) for r in rows]

    # --- helper calls: counted as spend, never as answers (A52) -----------------------
    async def record_ai_call(self, user_id, call) -> None:
        await self._exec(
            """INSERT INTO usage_daily (user_id, date, feature, requests, tokens_in,
                   tokens_out)
               VALUES (:u, current_date, :f, 1, :ti, :to)
               ON CONFLICT (user_id, date, feature) DO UPDATE SET
                   requests = usage_daily.requests + 1,
                   tokens_in = usage_daily.tokens_in + :ti,
                   tokens_out = usage_daily.tokens_out + :to,
                   updated_at = now()""",
            u=user_id, f=call.feature, ti=call.tokens_in, to=call.tokens_out,
        )  # fmt: skip

    async def daily_ai_spend(self, days: int = 7) -> list[dict]:
        rows = await self._rows(
            """SELECT day, feature, calls, tokens_in, tokens_out FROM ai_spend_daily
               WHERE day > current_date - :n""",
            n=days,
        )
        return summarise(rows, self.settings)

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
                               tokens_in, tokens_out, from_cache, matter_id,
                               shaped_by_upload, shaped_by_matter_fact)
                           SELECT id, 'assistant', :t, :m, :ti, :to, :fc, matter_id,
                                  :su, :sm
                           FROM conversations WHERE id = :c AND user_id = :u
                           RETURNING id"""
                    ),
                    dict(c=request.conversation_id, u=request.user_id, t=a.text, m=result.model or None,
                         ti=result.input_tokens, to=result.output_tokens, fc=result.cache_hit,
                         su=result.provenance.shaped_by_upload,
                         sm=result.provenance.shaped_by_matter_fact),
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
