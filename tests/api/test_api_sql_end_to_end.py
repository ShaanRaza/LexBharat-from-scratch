"""The real routes on top of the real SqlStore and a real PostgreSQL (fakes only for the
outside services: login, pipeline, queue). Skipped without TEST_DATABASE_URL."""

import json

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from api_fakes import words
from conftest import Env
from sqlalchemy.ext.asyncio import create_async_engine
from test_api_store_contract import DB_URL, INI

from api.pipeline import FinalAnswer, SourceRow, VerifiedCitation
from api.store import SqlStore


@pytest.fixture
def sql_env():
    if not DB_URL or not (sa.engine.make_url(DB_URL).database or "").endswith("_test"):
        pytest.skip(
            "TEST_DATABASE_URL not set, or its database name does not end in _test"
        )
    sync = sa.create_engine(DB_URL, poolclass=sa.pool.NullPool)
    with sync.begin() as c:
        c.execute(sa.text("DROP SCHEMA public CASCADE"))
        c.execute(sa.text("CREATE SCHEMA public"))
    cfg = Config(str(INI))
    cfg.set_main_option("sqlalchemy.url", DB_URL)
    command.upgrade(cfg, "head")
    with sync.begin() as c:
        c.execute(
            sa.text(
                "INSERT INTO cases (record_id, title, court, citation, pdf_url, full_text) "
                "VALUES ('rec-1', 'A v. B', 'Supreme Court of India', '[1959] S.C.R. 986', "
                "'https://x/p.pdf', 'para one\n\npara two')"
            )
        )
    env = Env()
    env.app.state.store = SqlStore(
        create_async_engine(DB_URL, poolclass=sa.pool.NullPool)
    )
    yield env, sync
    with sync.begin() as c:
        c.execute(sa.text("DROP SCHEMA public CASCADE"))
        c.execute(sa.text("CREATE SCHEMA public"))
    sync.dispose()


def test_chat_history_usage_export_and_delete_on_real_postgres(sql_env):
    env, sync = sql_env
    env.set_settings(PLAN_LIMIT_FREE=2)
    h = env.auth()
    client = env.client

    conv = client.post("/api/v1/conversations", headers=h, json={}).json()
    env.pipeline.events = [
        *words("Bail is release."),
        FinalAnswer(
            text="Bail is release.",
            citations=[VerifiedCitation("S1", "rec-1", "A v. B", "[1959] S.C.R. 986", "https://x/p.pdf", "verified")],
            sources=[SourceRow("S1", "rec-1", verified=True, support="supports")],
            model="fake", tokens_in=3, tokens_out=4,
        ),
    ]  # fmt: skip
    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=h,
        json={"content": "What is bail?"},
    )
    assert r.status_code == 200
    names = [b.split("\n")[0] for b in r.text.strip().split("\n\n")]
    assert names == ["event: token"] * 3 + ["event: citations", "event: done"]
    done = json.loads(r.text.strip().split("data: ")[-1])
    assert done["answers_left"] == 1

    hist = client.get(f"/api/v1/conversations/{conv['id']}", headers=h).json()
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant"]  # right order
    assert hist["messages"][1]["sources"][0]["title"] == "A v. B"

    me = client.get("/api/v1/me", headers=h).json()
    assert (me["answers_used"], me["answers_left"]) == (1, 1)
    case = client.get("/api/v1/cases/rec-1", headers=h).json()
    assert [p["anchor"] for p in case["paragraphs"]] == ["p1", "p2"]

    assert client.get("/api/v1/me/export", headers=h).json()["export"]["conversations"]

    assert client.delete("/api/v1/me", headers=h).status_code == 200
    with sync.connect() as c:
        for table in (
            "users",
            "conversations",
            "messages",
            "message_sources",
            "usage_daily",
        ):
            assert c.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar() == 0, (
                table
            )
        actions = [
            r[0] for r in c.execute(sa.text("SELECT action FROM audit_log ORDER BY at"))
        ]
        assert actions == ["export", "delete"]
    assert env.queue.jobs[0][0] == "delete_account"
