# ruff: noqa: S603
"""Migrations: numbered, reversible, 19 tables (docs/DATA-MODEL.md).

The offline test needs no database. The live test runs only when TEST_DATABASE_URL
points at a throwaway PostgreSQL (it upgrades, downgrades and upgrades again).
"""

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "users", "subscriptions", "usage_daily", "organisations", "memberships",
    "consents", "conversations", "messages", "message_sources",
    "invented_citation_log", "feedback", "documents", "document_chunks",
    "cases", "act_sections", "court_coverage", "audit_log", "matters", "share_links",
}  # fmt: skip


def _alembic(*args: str, url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "migrations/alembic.ini", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )  # fmt: skip


def test_offline_sql_creates_all_19_tables():
    out = _alembic("upgrade", "head", "--sql", url="postgresql+psycopg://x@h/d").stdout
    created = set(re.findall(r"CREATE TABLE (\w+)", out))
    assert created - {"alembic_version"} == EXPECTED


def test_no_password_or_judge_columns_anywhere():
    out = _alembic("upgrade", "head", "--sql", url="postgresql+psycopg://x@h/d").stdout
    low = out.lower()
    for banned in ("password", "judges", "petitioner", "respondent"):
        assert banned not in low


@pytest.fixture
def scratch_db_url():
    """A brand-new empty database on the TEST_DATABASE_URL server, dropped afterwards.
    The downgrade-to-base test works here, so it can never disturb other tests that
    expect the main test database to be migrated (order never matters)."""
    base = make_url(os.environ["TEST_DATABASE_URL"])
    name = f"mig_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield base.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_upgrade_downgrade_upgrade_on_real_postgres(scratch_db_url):
    url = scratch_db_url
    _alembic("upgrade", "head", url=url)
    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == EXPECTED
    _alembic("downgrade", "base", url=url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    _alembic("upgrade", "head", url=url)
    with engine.connect() as c:
        assert (
            c.execute(text("select version_num from alembic_version")).scalar()
            == "0010"
        )
    engine.dispose()


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_matters_matter_id_and_provenance_flags(scratch_db_url):
    """0006: matter_id is nullable on every user-work table that exists, matter
    kind is checked, and a message cannot be saved without the provenance flags."""
    from sqlalchemy.exc import IntegrityError

    _alembic("upgrade", "head", url=scratch_db_url)
    engine = create_engine(scratch_db_url)
    insp = inspect(engine)
    for table in ("conversations", "messages", "documents"):
        col = {c["name"]: c for c in insp.get_columns(table)}["matter_id"]
        assert col["nullable"] is True, table
    msg_cols = {c["name"]: c for c in insp.get_columns("messages")}
    for flag in ("shaped_by_upload", "shaped_by_matter_fact"):
        assert msg_cols[flag]["nullable"] is False
        assert msg_cols[flag]["default"] is None  # no default: a save must say it
    with engine.begin() as c:
        uid = c.execute(
            text(
                "insert into users (firebase_uid, email) "
                "values ('f','e@x.in') returning id"
            )
        ).scalar()
        conv = c.execute(
            text("insert into conversations (user_id) values (:u) returning id"),
            {"u": uid},
        ).scalar()
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(
            text(
                "insert into messages (conversation_id, role, content) "
                "values (:c,'user','x')"
            ),
            {"c": conv},
        )
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(
            text("insert into matters (user_id, title, kind) values (:u,'t','bogus')"),
            {"u": uid},
        )
    with engine.begin() as c:  # deleting a matter keeps the work, matter_id -> NULL
        mid = c.execute(
            text("insert into matters (user_id, title) values (:u,'t') returning id"),
            {"u": uid},
        ).scalar()
        c.execute(text("update conversations set matter_id=:m"), {"m": mid})
        c.execute(text("delete from matters where id=:m"), {"m": mid})
        assert c.execute(text("select matter_id from conversations")).scalar() is None
    engine.dispose()


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_ai_spend_view_exists_and_is_removed_on_downgrade(scratch_db_url):
    _alembic("upgrade", "head", url=scratch_db_url)
    engine = create_engine(scratch_db_url)
    assert "ai_spend_daily" in inspect(engine).get_view_names()
    with engine.connect() as c:  # readable, and empty on a fresh database
        assert c.execute(text("select count(*) from ai_spend_daily")).scalar() == 0
    _alembic("downgrade", "0006", url=scratch_db_url)
    assert (
        "ai_spend_daily" not in inspect(create_engine(scratch_db_url)).get_view_names()
    )
    engine.dispose()
