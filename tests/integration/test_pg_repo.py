"""PgRepo against a real PostgreSQL (set TEST_DATABASE_URL; migrations applied)."""

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from api.pg_repo import PgRepo, make_engine
from core.contracts import AnswerProvenance, PipelineRequest, RemovedCitation

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


@pytest.fixture
def repo():
    eng = make_engine(os.environ["TEST_DATABASE_URL"])
    yield PgRepo(eng, SimpleNamespace(PLAN_LIMIT_FREE=1))
    with eng.begin() as c:
        c.execute(text("TRUNCATE users, invented_citation_log CASCADE"))
    eng.dispose()


async def test_conversation_save_isolation_usage_and_log(repo):
    a = await repo.upsert_user("uid-a", "a@x.invalid", None)
    b = await repo.upsert_user("uid-b", None, None)
    assert (await repo.upsert_user("uid-a", None, None))["id"] == a["id"]

    conv = await repo.create_conversation(a["id"], "research", None)
    qid = await repo.add_user_message(a["id"], conv["id"], "Q?")
    assert await repo.add_user_message(b["id"], conv["id"], "evil") is None
    assert await repo.history(b["id"], conv["id"], qid) == ([], "")
    assert await repo.get_conversation(b["id"], conv["id"]) is None  # isolation

    cit = SimpleNamespace(source_id="S1", record_id="r1", status="verified")
    result = SimpleNamespace(
        provenance=AnswerProvenance(),
        outcome="answered", cache_hit=False, model="m", input_tokens=1,
        output_tokens=2, answer=SimpleNamespace(text="A [S1]", citations=(cit,)),
    )  # fmt: skip
    await repo.save(PipelineRequest(a["id"], "Q?", conv["id"]), result)
    got = await repo.get_conversation(a["id"], conv["id"])
    assert [m["role"] for m in got["messages"]] == ["user", "assistant"]
    assert got["message_count"] == 2
    assert got["messages"][1]["shaped_by_upload"] is False
    assert got["messages"][1]["shaped_by_matter_fact"] is False
    # The provenance flag is written with the answer (O14), not worked out later.
    shaped = SimpleNamespace(
        **{**vars(result), "provenance": AnswerProvenance(True, True)}
    )
    await repo.save(PipelineRequest(a["id"], "Q2?", conv["id"]), shaped)
    last = (await repo.get_conversation(a["id"], conv["id"]))["messages"][-1]
    assert last["shaped_by_upload"] and last["shaped_by_matter_fact"]
    # Bob's save into Alice's conversation writes nothing.
    await repo.save(PipelineRequest(b["id"], "x", conv["id"]), result)
    assert len((await repo.get_conversation(a["id"], conv["id"]))["messages"]) == 3

    assert await repo.allowed(a["id"], "free") is True
    await repo.count_one(a["id"])
    assert await repo.answers_this_month(a["id"]) == 1
    assert await repo.allowed(a["id"], "free") is False  # limit 1 reached

    await repo.write(
        "Q?", "m", [RemovedCitation("S2", None, "quote_not_found", "sent")]
    )
    rows = await repo._rows("SELECT reason FROM invented_citation_log")
    assert rows == [{"reason": "quote not found"}]
