# ruff: noqa: E501, S603
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
            == "0011"
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


# ---- the application role (A63) ---------------------------------------------------------
APP_ROLE = "app_rw"
APP_PASSWORD = "test-only-" + uuid.uuid4().hex  # throwaway cluster, never a real secret


@pytest.fixture
def app_engine(scratch_db_url):
    """A connection that is the application role (not the owner) on a migrated scratch
    database. The role is cluster-wide, so its login is switched off again afterwards."""
    from migrations.set_app_password import set_password

    _alembic("upgrade", "head", url=scratch_db_url)
    set_password(scratch_db_url, APP_ROLE, APP_PASSWORD)
    url = make_url(scratch_db_url).set(username=APP_ROLE, password=APP_PASSWORD)
    engine = create_engine(url)
    owner = create_engine(scratch_db_url)
    try:
        yield engine, owner
    finally:
        engine.dispose()
        with owner.begin() as c:
            c.execute(text(f"ALTER ROLE {APP_ROLE} NOLOGIN PASSWORD NULL"))
        owner.dispose()


def _must_fail(engine, statement: str, *needles: str):
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as e, engine.begin() as c:
        c.execute(text(statement))
    msg = str(e.value).lower()
    assert any(n in msg for n in needles), msg


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_the_application_role_is_not_an_owner_and_has_no_powers_over_the_schema(
    app_engine,
):
    app, owner = app_engine
    with app.connect() as c:
        who = c.execute(
            text(
                "select current_user, r.rolsuper, r.rolcreaterole, r.rolcreatedb "
                "from pg_roles r where r.rolname = current_user"
            )
        ).one()
    assert tuple(who) == (APP_ROLE, False, False, False)
    with owner.connect() as c:  # no table, view or function in public is owned by it
        owned = c.execute(
            text(
                "select count(*) from pg_class cl join pg_namespace n on n.oid = cl.relnamespace "
                "where n.nspname = 'public' and pg_get_userbyid(cl.relowner) = :r"
            ),
            {"r": APP_ROLE},
        ).scalar()
    assert owned == 0
    # the things an owner could do to switch the guarantees off:
    for stmt in (
        "alter table messages disable trigger messages_provenance_write_once",
        "alter table share_links disable trigger share_links_guard",
        "alter table messages disable trigger all",
        "drop trigger messages_provenance_write_once on messages",
        "drop trigger share_links_guard on share_links",
        "drop function messages_provenance_write_once() cascade",
        "alter table messages alter column shaped_by_upload drop not null",
        "alter table messages alter column shaped_by_upload set default false",
        "drop table share_links",
        "create table sneaky (id int)",
        "create trigger t before insert on messages for each row execute function share_links_guard()",
        "truncate messages",
        "alter role app_rw superuser",
        "create role other login",
        "set session authorization kanoon",
        "alter table messages owner to app_rw",
        "select * from alembic_version",
        "delete from alembic_version",
    ):
        _must_fail(app, stmt, "must be owner", "permission denied", "must be superuser",
                   "must have", "not permitted", "cannot set", "does not exist")  # fmt: skip


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_the_application_role_cannot_grant_itself_or_anyone_more(app_engine):
    """GRANT by a non-owner does not error in PostgreSQL (it warns and does nothing), so
    check the EFFECT: PUBLIC gains nothing and the app role gains no schema privilege."""
    app, owner = app_engine
    with app.begin() as c:
        c.execute(text("grant all on messages to public"))
        c.execute(text("grant all on schema public to app_rw"))
    with owner.connect() as c:
        public = c.execute(
            text(
                "select count(*) from information_schema.role_table_grants "
                "where table_name = 'messages' and grantee = 'PUBLIC'"
            )
        ).scalar()
        schema_create = c.execute(
            text("select has_schema_privilege('app_rw', 'public', 'CREATE')")
        ).scalar()
        trigger_priv = c.execute(
            text(
                "select has_table_privilege('app_rw', 'messages', 'TRIGGER'), "
                "has_table_privilege('app_rw', 'messages', 'TRUNCATE'), "
                "has_table_privilege('app_rw', 'messages', 'REFERENCES')"
            )
        ).one()
    assert public == 0 and schema_create is False
    assert tuple(trigger_priv) == (False, False, False)


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_the_application_role_can_do_ordinary_data_work_and_the_triggers_still_hold(
    app_engine,
):
    from sqlalchemy.exc import DBAPIError

    app, owner = app_engine
    with app.begin() as c:  # SELECT, INSERT, UPDATE, DELETE through tables and the view
        uid = c.execute(
            text(
                "insert into users (firebase_uid, email) values ('f','e@x.in') returning id"
            )
        ).scalar()
        cv = c.execute(
            text("insert into conversations (user_id) values (:u) returning id"),
            {"u": uid},
        ).scalar()
        mid = c.execute(
            text(
                "insert into messages (conversation_id, role, content, shaped_by_upload, shaped_by_matter_fact) "
                "values (:c, 'assistant', 'x', true, false) returning id"
            ),
            {"c": cv},
        ).scalar()
        c.execute(text("update messages set content = 'y' where id = :m"), {"m": mid})
        assert c.execute(text("select count(*) from ai_spend_daily")).scalar() >= 0
    # the guarantees hold against this role: the trigger refuses clearing the flag
    with pytest.raises(DBAPIError) as e, app.begin() as c:
        c.execute(
            text("update messages set shaped_by_upload = false where id = :m"),
            {"m": mid},
        )
    assert "cannot be cleared" in str(e.value)
    with pytest.raises(DBAPIError) as e, app.begin() as c:  # and a share link for it
        c.execute(
            text(
                "insert into share_links (user_id, message_id, token_hash, expires_at) "
                "values (:u, :m, 'h', now() + interval '1 day')"
            ),
            {"u": uid, "m": mid},
        )
    assert "cannot be shared" in str(e.value)
    with app.begin() as c:
        c.execute(text("delete from messages where id = :m"), {"m": mid})


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_a_table_a_later_migration_creates_is_usable_by_the_app_role_at_once(
    app_engine,
):
    app, owner = app_engine
    with owner.begin() as c:  # the owner creates a table, as a future migration would
        c.execute(text("create table later_table (id int primary key, v text)"))
    with app.begin() as c:
        c.execute(text("insert into later_table values (1, 'a')"))
        c.execute(text("update later_table set v = 'b' where id = 1"))
        assert c.execute(text("select v from later_table")).scalar() == "b"
    _must_fail(app, "drop table later_table", "must be owner", "permission denied")


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_the_password_is_required_and_the_role_has_no_login_until_it_is_set(
    scratch_db_url,
):
    from sqlalchemy.exc import DBAPIError

    from migrations.set_app_password import set_password

    _alembic("upgrade", "head", url=scratch_db_url)
    with pytest.raises(SystemExit):
        set_password(scratch_db_url, APP_ROLE, "")  # no passwordless login
    owner = create_engine(scratch_db_url)
    with owner.connect() as c:
        can_login = c.execute(
            text("select rolcanlogin from pg_roles where rolname = :r"), {"r": APP_ROLE}
        ).scalar()
    owner.dispose()
    assert can_login is False  # created NOLOGIN; the deploy enables it with a password
    nopass = create_engine(
        make_url(scratch_db_url).set(username=APP_ROLE, password=uuid.uuid4().hex)
    )
    with pytest.raises(DBAPIError), nopass.connect():
        pass
    nopass.dispose()


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)
def test_downgrade_takes_the_privileges_away_in_this_database(scratch_db_url):
    from sqlalchemy.exc import DBAPIError

    from migrations.set_app_password import set_password

    _alembic("upgrade", "head", url=scratch_db_url)
    set_password(scratch_db_url, APP_ROLE, APP_PASSWORD)
    _alembic("downgrade", "0010", url=scratch_db_url)
    app = create_engine(
        make_url(scratch_db_url).set(username=APP_ROLE, password=APP_PASSWORD)
    )
    with pytest.raises(DBAPIError), app.connect() as c:
        c.execute(text("select 1 from users limit 1"))
    app.dispose()
    owner = create_engine(scratch_db_url)
    with owner.begin() as c:
        c.execute(text(f"ALTER ROLE {APP_ROLE} NOLOGIN PASSWORD NULL"))
    owner.dispose()
    _alembic("upgrade", "head", url=scratch_db_url)  # and back up again
