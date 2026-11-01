"""Migrations: the 17 tables of docs/DATA-MODEL.md, reversible, with the conventions.

Two kinds of test:
  * OFFLINE (always run): generate the SQL without a database and inspect it.
  * ONLINE (run when TEST_DATABASE_URL points at a throwaway PostgreSQL, as in CI):
    really upgrade, check, downgrade, upgrade again.
"""

import io
import os
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
INI = ROOT / "migrations" / "alembic.ini"

TABLES = {
    "users", "subscriptions", "usage_daily", "organisations", "memberships", "consents",
    "conversations", "messages", "message_sources", "invented_citation_log", "feedback",
    "documents", "document_chunks", "cases", "act_sections", "court_coverage", "audit_log",
}  # fmt: skip


def alembic_config(url: str | None = None) -> Config:
    cfg = Config(str(INI))
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def offline_sql_for(revision_range: str, direction: str) -> str:
    """Run a migration in 'print the SQL' mode and return the SQL text."""
    buf = io.StringIO()
    cfg = alembic_config(
        "postgresql+psycopg://x:x@localhost/none"
    )  # never connected to
    cfg.output_buffer = buf
    getattr(command, direction)(cfg, revision_range, sql=True)
    return buf.getvalue()


@pytest.fixture(scope="module")
def offline_sql() -> str:
    return offline_sql_for("head", "upgrade")


def test_offline_sql_creates_exactly_the_17_tables(offline_sql):
    created = set(re.findall(r"CREATE TABLE (\w+) \(", offline_sql)) - {
        "alembic_version"
    }
    assert created == TABLES
    assert len(created) == 17


def test_every_table_has_uuid_id_and_both_timestamps_and_a_trigger(offline_sql):
    for name in TABLES:
        block = re.search(
            rf"CREATE TABLE {name} \((.*?)\n\)", offline_sql, re.DOTALL
        ).group(1)
        assert re.search(r"\bid UUID\b.*DEFAULT gen_random_uuid\(\)", block), name
        assert "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL" in block, (
            name
        )
        assert "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL" in block, (
            name
        )
        assert f"CREATE TRIGGER trg_{name}_updated_at" in offline_sql, name


def test_no_password_column_anywhere(offline_sql):
    assert "password" not in offline_sql.lower()


def test_no_judge_or_party_columns(offline_sql):
    # These fields failed the audit and must never be stored for display.
    for word in ("judges", "petitioner", "respondent"):
        assert word not in offline_sql.lower()


def test_audit_log_columns_hold_no_document_text(offline_sql):
    block = re.search(
        r"CREATE TABLE audit_log \((.*?)\n\)", offline_sql, re.DOTALL
    ).group(1)
    cols = set(re.findall(r"^\s+(\w+) ", block, re.MULTILINE)) - {
        "CONSTRAINT",
        "PRIMARY",
        "FOREIGN",
    }
    assert cols == {
        "id", "user_id", "action", "target_id", "ip", "request_id", "at",
        "created_at", "updated_at",
    }  # fmt: skip


def test_migrations_are_numbered_and_each_has_a_downgrade():
    files = sorted((ROOT / "migrations" / "versions").glob("[0-9]*.py"))
    assert [f.name[:4] for f in files] == [f"{i:04d}" for i in range(1, len(files) + 1)]
    for f in files:
        src = f.read_text()
        assert (
            "def downgrade()" in src
            and "pass\n" not in src.split("def downgrade()")[1][:40]
        )


def test_offline_downgrade_sql_drops_everything():
    dropped = set(
        re.findall(r"DROP TABLE (\w+)", offline_sql_for("0005:base", "downgrade"))
    )
    assert dropped >= TABLES


# ---------------------------------------------------------------------------------------
# ONLINE: needs a real PostgreSQL. Skipped (not failed) when none is configured.
# ---------------------------------------------------------------------------------------
DB_URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not DB_URL, reason="TEST_DATABASE_URL not set")


def reset_schema(engine) -> None:
    with engine.begin() as c:
        c.execute(sa.text("DROP SCHEMA public CASCADE"))
        c.execute(sa.text("CREATE SCHEMA public"))


@pytest.fixture
def engine():
    eng = sa.create_engine(DB_URL, poolclass=sa.pool.NullPool)
    reset_schema(eng)
    yield eng
    reset_schema(eng)
    eng.dispose()


def table_names(engine) -> set[str]:
    return set(sa.inspect(engine).get_table_names()) - {"alembic_version"}


@needs_db
def test_upgrade_downgrade_upgrade_on_real_postgres(engine):
    cfg = alembic_config(DB_URL)
    command.upgrade(cfg, "head")
    assert table_names(engine) == TABLES
    command.downgrade(cfg, "base")
    assert table_names(engine) == set()
    with engine.connect() as c:  # the trigger function is gone too
        assert (
            c.execute(
                sa.text("SELECT count(*) FROM pg_proc WHERE proname='set_updated_at'")
            ).scalar()
            == 0
        )
    command.upgrade(cfg, "head")
    assert table_names(engine) == TABLES


@needs_db
def test_every_table_really_has_the_conventions_in_postgres(engine):
    command.upgrade(alembic_config(DB_URL), "head")
    insp = sa.inspect(engine)
    for name in TABLES:
        cols = {c["name"]: c for c in insp.get_columns(name)}
        assert isinstance(cols["id"]["type"], sa.UUID), name
        assert (
            not cols["created_at"]["nullable"] and not cols["updated_at"]["nullable"]
        ), name
        assert not any("password" in c for c in cols), name


@needs_db
def test_updated_at_trigger_fires(engine):
    command.upgrade(alembic_config(DB_URL), "head")
    with engine.begin() as c:
        c.execute(
            sa.text("INSERT INTO users (firebase_uid, email) VALUES ('u', 'e@x')")
        )
        before = c.execute(sa.text("SELECT updated_at FROM users")).scalar()
        c.execute(sa.text("SELECT pg_sleep(0.05)"))
    with engine.begin() as c:
        c.execute(sa.text("UPDATE users SET name = 'n'"))
        after = c.execute(sa.text("SELECT updated_at FROM users")).scalar()
    assert after > before


@needs_db
def test_check_constraints_reject_bad_values(engine):
    command.upgrade(alembic_config(DB_URL), "head")
    bad = [
        "INSERT INTO users (firebase_uid, email, role) VALUES ('a', 'a@x', 'wizard')",
        "INSERT INTO users (firebase_uid, email, plan) VALUES ('b', 'b@x', 'platinum')",
        "INSERT INTO invented_citation_log (message_id, reason) VALUES (gen_random_uuid(), 'because')",
        "INSERT INTO cases (record_id, court, outcome_label) VALUES ('r', 'c', 'won')",
        "INSERT INTO audit_log (action) VALUES ('snoop')",
    ]
    for stmt in bad:
        with pytest.raises(sa.exc.DBAPIError), engine.begin() as c:
            c.execute(sa.text(stmt))


@needs_db
def test_chambers_need_at_least_three_seats_and_fk_rules(engine):
    command.upgrade(alembic_config(DB_URL), "head")
    with engine.begin() as c:
        owner = c.execute(
            sa.text(
                "INSERT INTO users (firebase_uid, email) VALUES ('o', 'o@x') RETURNING id"
            )
        ).scalar()
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as c:
        c.execute(
            sa.text(
                "INSERT INTO organisations (name, owner_user_id, seats) VALUES ('Chambers', :o, 2)"
            ),
            {"o": owner},
        )
    with engine.begin() as c:
        c.execute(
            sa.text(
                "INSERT INTO organisations (name, owner_user_id, seats) VALUES ('Chambers', :o, 3)"
            ),
            {"o": owner},
        )
    # An organisation owner cannot simply be deleted (RESTRICT).
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as c:
        c.execute(sa.text("DELETE FROM users WHERE id = :o"), {"o": owner})


@needs_db
def test_deleting_a_user_cascades_but_keeps_payment_and_audit_rows(engine):
    command.upgrade(alembic_config(DB_URL), "head")
    with engine.begin() as c:
        uid = c.execute(
            sa.text(
                "INSERT INTO users (firebase_uid, email) VALUES ('u', 'u@x') RETURNING id"
            )
        ).scalar()
        conv = c.execute(
            sa.text("INSERT INTO conversations (user_id) VALUES (:u) RETURNING id"),
            {"u": uid},
        ).scalar()
        msg = c.execute(
            sa.text(
                "INSERT INTO messages (conversation_id, role, content) VALUES (:c, 'user', 'q') RETURNING id"
            ),
            {"c": conv},
        ).scalar()
        c.execute(
            sa.text(
                "INSERT INTO invented_citation_log (message_id, query, reason) VALUES (:m, 'q', 'record_missing')"
            ),
            {"m": msg},
        )
        c.execute(
            sa.text("INSERT INTO documents (user_id, filename) VALUES (:u, 'f.pdf')"),
            {"u": uid},
        )
        c.execute(
            sa.text(
                "INSERT INTO consents (user_id, notice_version, purpose, given_at) VALUES (:u, 'v1', 'p', now())"
            ),
            {"u": uid},
        )
        c.execute(
            sa.text(
                "INSERT INTO subscriptions (user_id, plan, razorpay_subscription_id) VALUES (:u, 'pro', 'sub_9')"
            ),
            {"u": uid},
        )
        c.execute(
            sa.text("INSERT INTO audit_log (user_id, action) VALUES (:u, 'login')"),
            {"u": uid},
        )
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": uid})
    with engine.connect() as c:
        for t in (
            "conversations",
            "messages",
            "invented_citation_log",
            "documents",
            "consents",
        ):
            assert c.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar() == 0, t
        sub = c.execute(
            sa.text(
                "SELECT user_id FROM subscriptions WHERE razorpay_subscription_id='sub_9'"
            )
        ).one()
        assert sub[0] is None  # kept, detached from the person
        assert (
            c.execute(
                sa.text("SELECT count(*) FROM audit_log WHERE user_id IS NULL")
            ).scalar()
            == 1
        )
