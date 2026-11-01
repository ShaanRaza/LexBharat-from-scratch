"""Migrations: numbered, reversible, 17 tables (docs/DATA-MODEL.md).

The offline test needs no database. The live test runs only when TEST_DATABASE_URL
points at a throwaway PostgreSQL (it upgrades, downgrades and upgrades again).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "users", "subscriptions", "usage_daily", "organisations", "memberships",
    "consents", "conversations", "messages", "message_sources",
    "invented_citation_log", "feedback", "documents", "document_chunks",
    "cases", "act_sections", "court_coverage", "audit_log",
}  # fmt: skip


def _alembic(*args: str, url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "migrations/alembic.ini", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )  # fmt: skip


def test_offline_sql_creates_all_17_tables():
    out = _alembic("upgrade", "head", "--sql", url="postgresql+psycopg://x@h/d").stdout
    created = set(re.findall(r"CREATE TABLE (\w+)", out))
    assert created - {"alembic_version"} == EXPECTED


def test_no_password_or_judge_columns_anywhere():
    out = _alembic("upgrade", "head", "--sql", url="postgresql+psycopg://x@h/d").stdout
    low = out.lower()
    for banned in ("password", "judges", "petitioner", "respondent"):
        assert banned not in low


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_upgrade_downgrade_upgrade_on_real_postgres():
    url = os.environ["TEST_DATABASE_URL"]
    _alembic("downgrade", "base", url=url)
    _alembic("upgrade", "head", url=url)
    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == EXPECTED
    _alembic("downgrade", "base", url=url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    _alembic("upgrade", "head", url=url)
    with engine.connect() as c:
        assert (
            c.execute(text("select version_num from alembic_version")).scalar()
            == "0005"
        )
    engine.dispose()
