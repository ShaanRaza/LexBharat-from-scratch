# ruff: noqa: S603, S608, E501
"""Share links against a REAL PostgreSQL: try every route around the rule.

Runs on a throw-away database created from TEST_DATABASE_URL and dropped afterwards."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError

from api.pg_repo import PgRepo
from core.contracts import AnswerProvenance, PipelineRequest
from core.settings import Settings
from core.share import ShareRefused, create_share_link, hash_token

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
SOON = datetime.now(UTC) + timedelta(days=1)


@pytest.fixture(scope="module")
def db_url():
    base = make_url(os.environ["TEST_DATABASE_URL"])
    name = f"adv_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(ROOT)}
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "migrations/alembic.ini", "upgrade", "head"],
        cwd=ROOT, env=env, check=True, capture_output=True,
    )  # fmt: skip
    try:
        yield url
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def repo(db_url):
    eng = create_engine(db_url)
    yield PgRepo(eng, Settings(_env_file=None))
    with eng.begin() as c:
        c.execute(text("TRUNCATE users CASCADE"))
    eng.dispose()


async def user(repo, uid):
    return str((await repo.upsert_user(uid, None, None))["id"])


async def saved(repo, uid, upload=False, fact=False):
    """A stored answer written by the real Save path. Returns (conv, question, answer)."""
    conv = await repo.create_conversation(uid, "research", None)
    cid = str(conv["id"])
    await repo.add_user_message(uid, cid, "What is bail?")
    cit = SimpleNamespace(source_id="S1", record_id="rec-1", status="verified")
    result = SimpleNamespace(
        provenance=AnswerProvenance(upload, fact), outcome="answered", cache_hit=False,
        model="m", input_tokens=1, output_tokens=1,
        answer=SimpleNamespace(text="Bail is the rule [S1].", citations=(cit,)),
    )  # fmt: skip
    await repo.save(PipelineRequest(uid, "What is bail?", cid), result)
    msgs = (await repo.get_conversation(uid, cid))["messages"]
    return cid, str(msgs[0]["id"]), str(msgs[-1]["id"])


def sql(repo, statement, **p):
    with repo.engine.begin() as c:
        res = c.execute(text(statement), p)
        return [dict(r._mapping) for r in res] if res.returns_rows else []


def n_links(repo) -> int:
    return sql(repo, "SELECT count(*) AS n FROM share_links")[0]["n"]


INSERT = (
    "INSERT INTO share_links (user_id, message_id, token_hash, expires_at) "
    "VALUES (:u, :m, :h, :e)"
)


# ---- every way to INSERT a link for a message that must not be shared ---------------
@pytest.mark.parametrize("kind", ["upload", "fact", "both", "question", "other_user"])
async def test_raw_sql_insert_is_refused_for_every_kind_of_unshareable_message(
    repo, kind
):
    a, b = await user(repo, "ua"), await user(repo, "ub")
    _, q, clean = await saved(repo, a)
    _, _, up = await saved(repo, a, upload=True)
    _, _, fact = await saved(repo, a, fact=True)
    _, _, both = await saved(repo, a, upload=True, fact=True)
    target = {"upload": (a, up), "fact": (a, fact), "both": (a, both),
              "question": (a, q), "other_user": (b, clean)}[kind]  # fmt: skip
    with pytest.raises(DBAPIError) as e:
        sql(repo, INSERT, u=target[0], m=target[1], h="h-" + kind, e=SOON)
    assert "cannot be shared" in str(e.value)
    assert n_links(repo) == 0


async def test_on_conflict_do_nothing_or_update_does_not_skip_the_guard(repo):
    a = await user(repo, "ua")
    _, _, clean = await saved(repo, a)
    _, _, up = await saved(repo, a, upload=True)
    sql(
        repo, INSERT, u=a, m=clean, h="dup", e=SOON
    )  # a legitimate row to conflict with
    for clause in ("ON CONFLICT (token_hash) DO NOTHING",
                   "ON CONFLICT (token_hash) DO UPDATE SET revoked_at = NULL"):  # fmt: skip
        with pytest.raises(DBAPIError):
            sql(
                repo, INSERT + " " + clause, u=a, m=up, h="dup", e=SOON
            )  # conflicts AND shaped
        with pytest.raises(DBAPIError):
            sql(repo, INSERT + " " + clause, u=a, m=up, h="fresh", e=SOON)
    assert n_links(repo) == 1


async def test_a_multi_row_insert_with_one_bad_row_inserts_none(repo):
    a = await user(repo, "ua")
    _, _, clean = await saved(repo, a)
    _, _, up = await saved(repo, a, upload=True)
    with pytest.raises(DBAPIError):
        sql(
            repo,
            "INSERT INTO share_links (user_id, message_id, token_hash, expires_at) "
            "VALUES (:u, :c, 'h1', :e), (:u, :b, 'h2', :e)",
            u=a, c=clean, b=up, e=SOON,
        )  # fmt: skip
    assert n_links(repo) == 0


async def test_insert_select_cannot_launder_a_shaped_answer_either(repo):
    a = await user(repo, "ua")
    await saved(repo, a, upload=True)
    with pytest.raises(DBAPIError):
        sql(
            repo,
            "INSERT INTO share_links (user_id, message_id, token_hash, expires_at) "
            "SELECT c.user_id, m.id, 'h-' || m.id::text, now() + interval '1 day' "
            "FROM messages m JOIN conversations c ON c.id = m.conversation_id "
            "WHERE m.role = 'assistant'",
        )
    assert n_links(repo) == 0


async def test_pgrepo_create_share_link_directly_refuses_shaped_answers(repo):
    a = await user(repo, "ua")
    _, _, up = await saved(repo, a, upload=True)
    _, _, fact = await saved(repo, a, fact=True)
    for mid in (up, fact):
        with pytest.raises(DBAPIError):
            await repo.create_share_link(a, mid, "hh" + mid[:8], SOON)
    assert n_links(repo) == 0


async def test_core_refuses_before_the_database_is_even_asked(repo):
    a = await user(repo, "ua")
    _, _, up = await saved(repo, a, upload=True)
    with pytest.raises(ShareRefused):
        await create_share_link(repo, a, up, 30)
    assert n_links(repo) == 0


# ---- provenance flags cannot be NULL ----------------------------------------------------
async def test_messages_cannot_be_stored_with_null_or_missing_provenance(repo):
    a = await user(repo, "ua")
    conv = str((await repo.create_conversation(a, "research", None))["id"])
    for cols, vals in (
        ("conversation_id, role, content", ":c, 'assistant', 'x'"),  # flags omitted
        ("conversation_id, role, content, shaped_by_upload, shaped_by_matter_fact",
         ":c, 'assistant', 'x', NULL, false"),
        ("conversation_id, role, content, shaped_by_upload, shaped_by_matter_fact",
         ":c, 'assistant', 'x', false, NULL"),
    ):  # fmt: skip
        with pytest.raises(IntegrityError):
            sql(repo, f"INSERT INTO messages ({cols}) VALUES ({vals})", c=conv)


async def test_a_flag_cannot_be_blanked_to_null_after_the_fact(repo):
    a = await user(repo, "ua")
    _, _, up = await saved(repo, a, upload=True)
    for col in ("shaped_by_upload", "shaped_by_matter_fact"):
        with pytest.raises(IntegrityError):
            sql(repo, f"UPDATE messages SET {col} = NULL WHERE id = :m", m=up)


# ---- tampering AFTER a link exists: the public read must go dark -------------------------
async def _live_link(repo, a):
    _, _, mid = await saved(repo, a)
    link = await create_share_link(repo, a, mid, 30)
    assert await repo.get_shared_answer(hash_token(link.token)) is not None
    return link, mid


@pytest.mark.parametrize(
    "tamper",
    [
        "UPDATE messages SET shaped_by_upload = true WHERE id = :m",
        "UPDATE messages SET shaped_by_matter_fact = true WHERE id = :m",
        "UPDATE messages SET role = 'user' WHERE id = :m",
        "UPDATE messages SET conversation_id = (SELECT id FROM conversations "
        "WHERE user_id <> (SELECT user_id FROM conversations c2 JOIN messages m2 "
        "ON m2.conversation_id = c2.id WHERE m2.id = :m) LIMIT 1) WHERE id = :m",
    ],
)
async def test_the_public_read_dies_when_the_answer_is_later_made_unshareable(
    repo, tamper
):
    a, b = await user(repo, "ua"), await user(repo, "ub")
    await repo.create_conversation(
        b, "research", None
    )  # a conversation of another user
    link, mid = await _live_link(repo, a)
    sql(repo, tamper, m=mid)
    assert await repo.get_shared_answer(hash_token(link.token)) is None


async def test_retargeting_a_link_to_a_shaped_answer_leaves_the_public_page_dark(repo):
    a = await user(repo, "ua")
    link, _ = await _live_link(repo, a)
    _, _, up = await saved(repo, a, upload=True)
    sql(repo, "UPDATE share_links SET message_id = :m WHERE id = :i", m=up, i=link.id)
    assert await repo.get_shared_answer(hash_token(link.token)) is None


async def test_handing_a_link_to_another_user_leaves_the_public_page_dark(repo):
    a, b = await user(repo, "ua"), await user(repo, "ub")
    link, _ = await _live_link(repo, a)
    sql(repo, "UPDATE share_links SET user_id = :b WHERE id = :i", b=b, i=link.id)
    assert await repo.get_shared_answer(hash_token(link.token)) is None


@pytest.mark.xfail(
    strict=True,
    reason="BREAK (medium): the guard is BEFORE INSERT only (migrations/versions/"
    "0009_share_links.py), so UPDATE share_links SET message_id = <upload-shaped "
    "answer> succeeds: a link row can be pointed at a shaped answer after creation. "
    "The public read re-checks and stays dark, but the row exists",
)
async def test_the_database_refuses_to_retarget_a_link_to_a_shaped_answer(repo):
    a = await user(repo, "ua")
    link, _ = await _live_link(repo, a)
    _, _, up = await saved(repo, a, upload=True)
    with pytest.raises(DBAPIError):
        sql(
            repo,
            "UPDATE share_links SET message_id = :m WHERE id = :i",
            m=up,
            i=link.id,
        )


@pytest.mark.xfail(
    strict=True,
    reason="BREAK (medium): provenance flags are not write-once. Nothing in the "
    "database stops UPDATE messages SET shaped_by_upload = false on an upload-shaped "
    "answer, after which the trigger and core both allow a share link (A47 says the "
    "flags are written once at save; no trigger enforces it)",
)
async def test_a_shaped_flag_cannot_be_flipped_back_to_false_to_unlock_sharing(repo):
    a = await user(repo, "ua")
    _, _, up = await saved(repo, a, upload=True)
    with pytest.raises(DBAPIError):
        sql(repo, "UPDATE messages SET shaped_by_upload = false WHERE id = :m", m=up)


async def test_the_flag_flip_really_does_unlock_sharing_documenting_the_break(repo):
    """Characterisation of the break above, so the risk is visible in plain code."""
    a = await user(repo, "ua")
    _, _, up = await saved(repo, a, upload=True)
    sql(repo, "UPDATE messages SET shaped_by_upload = false WHERE id = :m", m=up)
    link = await create_share_link(
        repo, a, up, 30
    )  # accepted: provenance was rewritten
    assert await repo.get_shared_answer(hash_token(link.token)) is not None


# ---- the public lookup itself ------------------------------------------------------------
@pytest.mark.parametrize(
    "h",
    ["", " ", "%", "_", "' OR '1'='1", "'; DROP TABLE share_links; --", "\x00", "a" * 10000,
     "NULL", "0" * 64],
)  # fmt: skip
async def test_odd_hashes_find_nothing_and_do_not_error(repo, h):
    a = await user(repo, "ua")
    await _live_link(repo, a)
    try:
        got = await repo.get_shared_answer(h)
    except (ValueError, DataError):  # NUL refused by the driver: still no data
        got = None
    assert got is None
    assert n_links(repo) == 1  # the table survived the injection attempts


def test_the_route_hashes_first_so_the_database_only_ever_sees_hex():
    for token in ("\x00", "' OR 1=1 --", "%", "a" * 100000, "\u202e\u0000"):
        h = hash_token(token)
        assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


async def test_the_listing_never_returns_a_token_or_a_hash(repo):
    a = await user(repo, "ua")
    link, _ = await _live_link(repo, a)
    dump = str(await repo.list_share_links(a))
    assert link.token not in dump and hash_token(link.token) not in dump
    assert link.token not in str(sql(repo, "SELECT * FROM share_links"))
