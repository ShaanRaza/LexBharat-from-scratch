# ruff: noqa: E501
"""PgRepo works end to end when it connects as the NON-OWNING application role (A63).

If a repository method needed schema powers (a TRUNCATE, an ALTER, a sequence, a table the
default privileges missed), the app would break in production while every other test,
which connects as the owner, stayed green. This runs the real flows as the app role."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from api.pg_repo import PgRepo, make_engine
from core.contracts import AnswerProvenance, PipelineRequest
from core.doc_delete import DocServices, delete_matter, hard_delete_document
from core.settings import Settings
from core.share import create_share_link, hash_token
from core.spend import AiCall
from core.user_search import search_my_work
from tests.pg_roles import app_login

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


@pytest.fixture
def repo():
    owner_url = os.environ["TEST_DATABASE_URL"]
    with app_login(owner_url) as app_url:
        app = make_engine(app_url)
        yield PgRepo(app, Settings(_env_file=None))
        app.dispose()
    owner = make_engine(owner_url)
    with owner.begin() as c:
        c.execute(text("TRUNCATE users CASCADE"))  # the OWNER cleans up
    owner.dispose()


async def test_the_real_flows_work_as_the_application_role(repo):
    from adapters.qdrant import FakeVectorStore
    from adapters.s3 import FakeFileStore

    uid = str((await repo.upsert_user("uid-role", "a@x.in", None))["id"])
    # matters, conversations, answers (step 11), the meter
    m = await repo.create_matter(uid, "State v Doe", "matter")
    mid = str(m["id"])
    conv = await repo.create_conversation(uid, "research", None, mid)
    cid = str(conv["id"])
    await repo.add_user_message(uid, cid, "What is bail?")
    res = SimpleNamespace(
        provenance=AnswerProvenance(), outcome="answered", cache_hit=False, model="m",
        input_tokens=5, output_tokens=7,
        answer=SimpleNamespace(
            text="Bail is the rule [S1].",
            citations=(SimpleNamespace(source_id="S1", record_id="r1", status="verified"),),
        ),
    )  # fmt: skip
    await repo.save(PipelineRequest(uid, "What is bail?", cid), res)
    await repo.count_one(uid)
    assert await repo.answers_this_month(uid) == 1
    detail = await repo.get_conversation(uid, cid)
    answer_id = detail["messages"][-1]["id"]

    # sharing (the trigger runs for this role), history search, helper spend, AI spend view
    link = await create_share_link(repo, uid, answer_id, 30)
    assert await repo.get_shared_answer(hash_token(link.token)) is not None
    assert await repo.revoke_share_link(uid, link.id) is True
    assert await search_my_work(repo, uid, "bail")
    await repo.record_ai_call(uid, AiCall("improve", 3, 4, "m"))
    assert (await repo.daily_ai_spend())[0]["helper_calls"] == 1
    await repo.add_feedback(uid, {"message_id": answer_id, "rating": "up"})
    await repo.add_consent(uid, "v1", "service")
    await repo.audit(uid, "export", "x")
    assert await repo.allowed(uid, "free") in (True, False)

    # uploads and the hard-delete path, ending in a matter delete that asks "everything"
    svc = DocServices(FakeFileStore(), FakeVectorStore(Settings(_env_file=None)), repo)
    d1 = await repo.create_document(uid, "a.pdf", mid, "client text")
    svc.files.put(uid, d1, b"%PDF")
    svc.vectors.add_upload(f"{d1}-0", "client text", uid, d1)
    await hard_delete_document(uid, d1, svc)
    assert await repo.document_rows_remaining(d1) == 0
    d2 = await repo.create_document(uid, "b.pdf", mid, "more text")
    svc.files.put(uid, d2, b"%PDF")
    svc.vectors.add_upload(f"{d2}-0", "more text", uid, d2)
    r = await delete_matter(uid, mid, "everything", svc, repo)
    assert (r.documents_deleted, r.conversations_deleted) == (1, 1)
    assert await repo.get_matter(uid, mid) is None
