"""One set of checks, run against BOTH the in-memory FakeStore and the real SqlStore.

This is what keeps the fake honest: if SqlStore and FakeStore ever disagree, a test here
fails. The SqlStore half needs a throwaway PostgreSQL (TEST_DATABASE_URL, as in CI) and
is skipped when none is configured.
"""

import os
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from api_fakes import FakeStore
from sqlalchemy.ext.asyncio import create_async_engine

from api.pipeline import FinalAnswer, RemovedCitation, SourceRow
from api.store import OwnsOrganisation, SqlStore

DB_URL = os.environ.get("TEST_DATABASE_URL")
INI = Path(__file__).resolve().parents[2] / "migrations" / "alembic.ini"
TODAY = datetime.now(UTC).date()
LONG_AGO = date(2000, 1, 1)


class Backend:
    """A store plus the helpers a test needs to put data in place."""

    def __init__(self, store, kind, engine=None):
        self.store, self.kind, self.engine = store, kind, engine

    async def seed_case(self, **kw):
        row = {
            "title": "A v. B", "court": "Supreme Court of India", "decision_date": None,
            "citation": "cit", "outcome_label": None, "is_final_outcome": None,
            "pdf_url": "https://x/p.pdf", "full_text": "t",
        } | kw  # fmt: skip
        if self.kind == "fake":
            self.store.add_case(**row)
            return
        async with self.engine.begin() as c:
            cols = ", ".join(row)
            vals = ", ".join(f":{k}" for k in row)
            await c.execute(sa.text(f"INSERT INTO cases ({cols}) VALUES ({vals})"), row)

    async def seed_act(self, **kw):
        row = {"act_year": None, "act_status": None, "in_force": None, "text": "t"} | kw
        if self.kind == "fake":
            self.store.add_act(**row)
            return
        async with self.engine.begin() as c:
            cols = ", ".join(row)
            vals = ", ".join(f":{k}" for k in row)
            await c.execute(
                sa.text(f"INSERT INTO act_sections ({cols}) VALUES ({vals})"), row
            )

    async def seed_coverage(self, court, as_of, stats_live=False, version="v2026.08"):
        if self.kind == "fake":
            self.store.coverage.append(
                {
                    "court": court,
                    "snapshot_version": version,
                    "data_as_of": as_of,
                    "stats_live": stats_live,
                }
            )
            return
        async with self.engine.begin() as c:
            await c.execute(
                sa.text(
                    "INSERT INTO court_coverage (court, snapshot_version, data_as_of, stats_live) "
                    "VALUES (:c, :v, :d, :s)"
                ),
                {"c": court, "v": version, "d": as_of, "s": stats_live},
            )

    async def make_owner(self, user_id):
        if self.kind == "fake":
            self.store.org_owners.add(user_id)
            return
        async with self.engine.begin() as c:
            await c.execute(
                sa.text(
                    "INSERT INTO organisations (name, owner_user_id, seats) VALUES ('Ch', :u, 3)"
                ),
                {"u": user_id},
            )

    async def count(self, table, where="true", **params):
        assert self.kind == "sql"
        async with self.engine.connect() as c:
            return (
                await c.execute(
                    sa.text(f"SELECT count(*) FROM {table} WHERE {where}"), params
                )
            ).scalar()


@pytest.fixture(scope="module")
def migrated_db():
    # These tests DROP the whole schema, so they only run on a database named *_test.
    if not DB_URL or not (sa.engine.make_url(DB_URL).database or "").endswith("_test"):
        pytest.skip(
            "TEST_DATABASE_URL not set, or its database name does not end in _test"
        )
    eng = sa.create_engine(DB_URL, poolclass=sa.pool.NullPool)
    with eng.begin() as c:
        c.execute(sa.text("DROP SCHEMA public CASCADE"))
        c.execute(sa.text("CREATE SCHEMA public"))
    cfg = Config(str(INI))
    cfg.set_main_option("sqlalchemy.url", DB_URL)
    command.upgrade(cfg, "head")
    yield DB_URL
    with eng.begin() as c:
        c.execute(sa.text("DROP SCHEMA public CASCADE"))
        c.execute(sa.text("CREATE SCHEMA public"))
    eng.dispose()


@pytest.fixture(params=["fake", "sql"])
async def be(request):
    if request.param == "fake":
        yield Backend(FakeStore(), "fake")
        return
    request.getfixturevalue("migrated_db")
    engine = create_async_engine(DB_URL, poolclass=sa.pool.NullPool)
    async with engine.begin() as c:  # start every test from empty tables
        await c.execute(
            sa.text(
                "TRUNCATE users, organisations, subscriptions, cases, act_sections, "
                "court_coverage, audit_log CASCADE"
            )
        )
    yield Backend(SqlStore(engine), "sql", engine)
    await engine.dispose()


async def user(be, uid="u1", email="a@x"):
    return (await be.store.upsert_user(uid, email, "Name"))["id"]


def answer(**kw) -> FinalAnswer:
    base = {
        "text": "ans", "model": "m", "tokens_in": 5, "tokens_out": 7,
        "rewritten_query": "q", "sources": [SourceRow("S1", "rec-1", verified=True, support="supports")],
    }  # fmt: skip
    return FinalAnswer(**(base | kw))


# ---- users --------------------------------------------------------------------------
async def test_upsert_user_is_idempotent_and_follows_email_changes(be):
    first = await be.store.upsert_user("uid", "a@x", "A")
    again = await be.store.upsert_user("uid", "a@x", "A")
    assert first["id"] == again["id"]
    assert (first["role"], first["plan"], first["status"]) == (
        "other",
        "free",
        "active",
    )
    changed = await be.store.upsert_user("uid", "new@x", "A")
    assert changed["id"] == first["id"] and changed["email"] == "new@x"


# ---- conversations ---------------------------------------------------------------------
async def test_conversations_are_private_and_paginate_newest_first(be):
    a, b = await user(be, "a"), await user(be, "b", "b@x")
    made = [
        (await be.store.create_conversation(a, "research", f"t{i}", None))["id"]
        for i in range(5)
    ]
    await be.store.create_conversation(b, "research", "bobs", None)
    page1 = await be.store.list_conversations(a, None, 3)
    assert [c["id"] for c in page1] == made[::-1][:3]
    last = page1[-1]
    page2 = await be.store.list_conversations(a, (last["created_at"], last["id"]), 3)
    assert [c["id"] for c in page2] == made[::-1][3:]
    assert await be.store.get_conversation(b, made[0]) is None
    assert (await be.store.get_conversation(a, made[0]))["title"] == "t0"


async def test_conversation_cannot_attach_someone_elses_document(be):
    a, b = await user(be, "a"), await user(be, "b", "b@x")
    doc = uuid4()
    await be.store.create_document(doc, b, "f.pdf", None, None, f"uploads/{b}/{doc}")
    conv = await be.store.create_conversation(a, "document", None, doc)
    assert conv["document_id"] is None


async def test_save_exchange_stores_everything_and_counts_usage(be):
    u = await user(be)
    await be.seed_case(
        record_id="rec-1", title="Title 1", citation="C1", pdf_url="https://x/1.pdf"
    )
    conv = (await be.store.create_conversation(u, "research", None, None))["id"]
    ans = answer(
        removed=[RemovedCitation("Fake v. Fake", "not_retrieved")],
        rolling_summary="sum",
    )
    mid = await be.store.save_exchange(u, conv, "What is bail?", ans, count_usage=True)

    msgs = await be.store.list_messages(conv)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["id"] == mid
    src = msgs[1]["sources"][0]
    assert (src["source_id"], src["record_id"], src["verified"]) == (
        "S1",
        "rec-1",
        True,
    )
    assert (src["title"], src["citation"], src["url"]) == (
        "Title 1",
        "C1",
        "https://x/1.pdf",
    )

    c = await be.store.get_conversation(u, conv)
    assert c["message_count"] == 2
    assert c["title"] == "What is bail?"
    assert c["rolling_summary"] == "sum"
    assert await be.store.answers_used(u, TODAY.replace(day=1)) == 1
    if be.kind == "sql":
        assert await be.count("invented_citation_log", "reason='not_retrieved'") == 1


async def test_save_exchange_without_usage_leaves_the_meter_alone(be):
    u = await user(be)
    conv = (await be.store.create_conversation(u, "research", None, None))["id"]
    await be.store.save_exchange(
        u, conv, "q", answer(from_cache=True, sources=[]), count_usage=False
    )
    assert await be.store.answers_used(u, LONG_AGO) == 0


async def test_usage_accumulates_per_day_and_ignores_older_months(be):
    u = await user(be)
    conv = (await be.store.create_conversation(u, "research", None, None))["id"]
    for _ in range(3):
        await be.store.save_exchange(u, conv, "q", answer(sources=[]), count_usage=True)
    assert await be.store.answers_used(u, TODAY.replace(day=1)) == 3
    assert (
        await be.store.answers_used(
            u, TODAY.replace(day=1).replace(year=TODAY.year + 1)
        )
        == 0
    )


# ---- records ------------------------------------------------------------------------------
async def test_case_lookup_and_missing(be):
    await be.seed_case(
        record_id="r1", decision_date=date(2020, 5, 1), outcome_label="allowed"
    )
    got = await be.store.get_case("r1")
    assert got["record_id"] == "r1" and got["decision_date"] == date(2020, 5, 1)
    assert await be.store.get_case("nope") is None
    for banned in ("judges", "petitioner", "respondent"):
        assert banned not in got


async def test_act_section_lookup_by_slug_variants(be):
    await be.seed_act(
        record_id="a1",
        act_name="The Indian Penal Code, 1860",
        act_year=1860,
        section_number="498A",
    )
    await be.seed_act(
        record_id="a2",
        act_name="The Indian Penal Code, 1860",
        act_year=1860,
        section_number="302",
    )
    for slug in (
        "the-indian-penal-code-1860",
        "indian-penal-code-1860",
        "indian-penal-code",
        "the-indian-penal-code",
    ):
        got = await be.store.get_act_section(slug, "498a")
        assert got and got["record_id"] == "a1", slug
    assert await be.store.get_act_section("indian-penal-code", "999") is None
    assert await be.store.get_act_section("other-act", "302") is None
    assert (await be.store.get_act_section("indian-penal-code", "302"))[
        "act_status"
    ] is None


async def test_data_as_of_prefers_the_court_then_latest_then_none(be):
    assert await be.store.data_as_of("Supreme Court of India") is None
    await be.seed_coverage("acts_india", date(2026, 7, 1))
    assert await be.store.data_as_of("Supreme Court of India") == date(2026, 7, 1)
    await be.seed_coverage("Supreme Court of India", date(2026, 8, 15))
    assert await be.store.data_as_of("Supreme Court of India") == date(2026, 8, 15)


async def test_stats_count_only_final_labelled_cases_and_respect_stats_live(be):
    await be.seed_coverage("Supreme Court of India", date(2026, 8, 15), stats_live=True)
    await be.seed_coverage("Bombay High Court", date(2026, 8, 15), stats_live=False)
    rows = [("allowed", True, 2020), ("allowed", True, 2020), ("dismissed", True, 2021),
            ("allowed", False, 2020), (None, True, 2020)]  # fmt: skip
    for i, (label, final, yr) in enumerate(rows):
        await be.seed_case(
            record_id=f"s{i}",
            outcome_label=label,
            is_final_outcome=final,
            decision_date=date(yr, 2, 2),
        )
    assert await be.store.stats_live("Supreme Court of India") is True
    assert await be.store.stats_live("Bombay High Court") is False
    assert await be.store.stats_live("Nowhere") is False
    assert await be.store.case_stats("Supreme Court of India", None) == [
        {"year": 2021, "outcome_label": "dismissed", "count": 1},
        {"year": 2020, "outcome_label": "allowed", "count": 2},
    ]
    assert len(await be.store.case_stats("Supreme Court of India", 2021)) == 1


# ---- privacy -----------------------------------------------------------------------------------
async def test_consents_give_list_withdraw(be):
    u = await user(be)
    await be.store.give_consent(u, "v1", "research")
    await be.store.give_consent(u, "v1", "marketing")
    assert await be.store.withdraw_consent(u, "marketing") == 1
    assert await be.store.withdraw_consent(u, "marketing") == 0
    by_purpose = {c["purpose"]: c for c in await be.store.list_consents(u)}
    assert by_purpose["marketing"]["withdrawn_at"] is not None
    assert by_purpose["research"]["withdrawn_at"] is None


async def test_feedback_only_on_own_messages_and_one_per_message(be):
    a, b = await user(be, "a"), await user(be, "b", "b@x")
    conv = (await be.store.create_conversation(a, "research", None, None))["id"]
    mid = await be.store.save_exchange(
        a, conv, "q", answer(sources=[]), count_usage=False
    )
    assert await be.store.add_feedback(b, mid, 1, None, None) is False
    assert await be.store.add_feedback(a, mid, -1, "wrong", "c") is True
    assert await be.store.add_feedback(a, mid, 1, None, None) is True
    if be.kind == "sql":
        assert await be.count("feedback") == 1


async def test_documents_are_private_and_deletable(be):
    a, b = await user(be, "a"), await user(be, "b", "b@x")
    doc = uuid4()
    created = await be.store.create_document(
        doc, a, "f.pdf", "application/pdf", 10, f"uploads/{a}/{doc}"
    )
    assert created["status"] == "uploaded"
    assert await be.store.get_document(b, doc) is None
    assert (await be.store.get_document(a, doc))["storage_path"].endswith(str(doc))
    assert await be.store.delete_document(b, doc) is None
    gone = await be.store.delete_document(a, doc)
    assert gone["storage_path"].endswith(str(doc))
    assert await be.store.get_document(a, doc) is None


async def test_account_cleanup_info_lists_ids_and_paths_only(be):
    u = await user(be, "uid-x")
    doc = uuid4()
    await be.store.create_document(
        doc, u, "secret-name.pdf", None, None, f"uploads/{u}/{doc}"
    )
    info = await be.store.account_cleanup_info(u)
    assert info["firebase_uid"] == "uid-x"
    assert info["document_ids"] == [str(doc)]
    assert info["storage_paths"] == [f"uploads/{u}/{doc}"]
    assert "secret-name.pdf" not in str(info)


async def test_delete_user_removes_personal_data_everywhere(be):
    u = await user(be)
    other = await user(be, "other", "o@x")
    conv = (await be.store.create_conversation(u, "research", None, None))["id"]
    await be.store.save_exchange(
        u,
        conv,
        "q",
        answer(removed=[RemovedCitation("x", "record_missing")]),
        count_usage=True,
    )
    await be.store.give_consent(u, "v1", "research")
    doc = uuid4()
    await be.store.create_document(doc, u, "f.pdf", None, None, "p")
    await be.store.delete_user(u)
    assert await be.store.get_conversation(u, conv) is None
    assert await be.store.list_consents(u) == []
    assert await be.store.get_document(u, doc) is None
    assert await be.store.answers_used(u, LONG_AGO) == 0
    assert (await be.store.upsert_user("other", "o@x", None))[
        "id"
    ] == other  # others untouched
    if be.kind == "sql":
        assert await be.count("messages") == 0
        assert await be.count("invented_citation_log") == 0


async def test_delete_user_is_blocked_while_owning_an_organisation(be):
    u = await user(be)
    await be.make_owner(u)
    assert await be.store.owns_organisation(u) is True
    with pytest.raises(OwnsOrganisation):
        await be.store.delete_user(u)
    assert (
        await be.store.get_conversation(u, uuid4()) is None
    )  # user still exists, no crash


async def test_export_has_account_chats_and_document_list_without_contents(be):
    u = await user(be)
    conv = (await be.store.create_conversation(u, "research", "T", None))["id"]
    await be.store.save_exchange(
        u, conv, "my question", answer(sources=[]), count_usage=False
    )
    doc = uuid4()
    await be.store.create_document(doc, u, "f.pdf", None, None, "p")
    data = await be.store.export_user(u)
    assert data["account"]["email"] == "a@x"
    assert [m["content"] for m in data["conversations"][0]["messages"]] == [
        "my question",
        "ans",
    ]
    assert [d["filename"] for d in data["documents"]] == ["f.pdf"]
    assert "storage_path" not in data["documents"][0]


async def test_audit_rows_and_subscription_updates(be):
    u = await user(be)
    await be.store.add_audit(u, "export", str(u), "1.2.3.4", "req-1")
    assert await be.store.update_subscription_status("sub_none", "active") == 0
    if be.kind == "sql":
        assert (
            await be.count("audit_log", "action='export' AND request_id='req-1'") == 1
        )
        async with be.engine.begin() as c:
            await c.execute(
                sa.text(
                    "INSERT INTO subscriptions (user_id, plan, razorpay_subscription_id) VALUES (:u, 'pro', 'sub_1')"
                ),
                {"u": u},
            )
        assert await be.store.update_subscription_status("sub_1", "active") == 1
        assert await be.count("subscriptions", "status='active'") == 1


async def test_ping(be):
    await be.store.ping()
