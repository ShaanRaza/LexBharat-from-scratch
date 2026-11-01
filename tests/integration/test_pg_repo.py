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


@pytest.fixture
def priced_repo():
    from core.settings import Settings

    eng = make_engine(os.environ["TEST_DATABASE_URL"])
    s = Settings(
        _env_file=None,
        PLAN_LIMIT_FREE=1,
        AI_PRICE_IN_PER_MTOK=1.0,
        AI_PRICE_OUT_PER_MTOK=2.0,
    )
    yield PgRepo(eng, s)
    with eng.begin() as c:
        c.execute(text("TRUNCATE users, invented_citation_log CASCADE"))
    eng.dispose()


async def test_helper_calls_never_spend_the_answer_limit_but_are_in_the_daily_spend(
    priced_repo,
):
    from core.spend import AiCall

    repo = priced_repo
    u = await repo.upsert_user("uid-h", None, None)
    uid = u["id"]
    # A free user with a limit of 1 answer makes many helper calls: still allowed.
    for _ in range(5):
        await repo.record_ai_call(uid, AiCall("improve", 30, 20, "m"))
        await repo.record_ai_call(uid, AiCall("followups", 120, 40, "m"))
    assert await repo.answers_this_month(uid) == 0  # helpers are not answers
    assert await repo.allowed(uid, "free") is True

    # One real answer is saved (its tokens are in messages) and counted once.
    conv = await repo.create_conversation(uid, "research", None)
    cit = SimpleNamespace(source_id="S1", record_id="r1", status="verified")
    result = SimpleNamespace(
        provenance=AnswerProvenance(), outcome="answered", cache_hit=False, model="m",
        input_tokens=1000, output_tokens=500,
        answer=SimpleNamespace(text="A [S1]", citations=(cit,)),
    )  # fmt: skip
    await repo.save(PipelineRequest(uid, "Q?", conv["id"]), result)
    await repo.count_one(uid)
    assert await repo.answers_this_month(uid) == 1
    assert await repo.allowed(uid, "free") is False  # now the limit bites

    [day] = await repo.daily_ai_spend()
    assert day["answers"] == 1 and day["helper_calls"] == 10
    assert day["helper_tokens"] == 5 * (50 + 160)
    assert day["tokens_in"] == 1000 + 5 * 150 and day["tokens_out"] == 500 + 5 * 60
    cost = day["tokens_in"] * 1.0 / 1e6 + day["tokens_out"] * 2.0 / 1e6
    assert day["estimated_cost"] == pytest.approx(cost)
    assert day["cost_per_answer"] == pytest.approx(cost)  # one answer, helpers included


async def _pg_matter_with_work(repo, svc):
    u = await repo.upsert_user("uid-m", None, None)
    uid = str(u["id"])
    m = await repo.create_matter(uid, "State v Doe", "matter")
    mid = str(m["id"])
    docs = []
    for body in ("first client file text", "second client file text"):
        d = await repo.create_document(uid, "f.pdf", mid, body)
        svc.files.put(uid, d, b"%PDF")
        svc.vectors.add_upload(f"{d}-0", body, uid, d)
        docs.append(d)
    conv = await repo.create_conversation(uid, "research", None)
    await repo._exec(
        "UPDATE conversations SET matter_id = :m WHERE id = :c RETURNING id",
        m=mid, c=conv["id"],
    )  # fmt: skip
    return uid, mid, docs, str(conv["id"])


def _services(repo):
    from adapters.qdrant import FakeVectorStore
    from adapters.s3 import FakeFileStore
    from core.doc_delete import DocServices
    from core.settings import Settings

    return DocServices(FakeFileStore(), FakeVectorStore(Settings(_env_file=None)), repo)


async def test_hard_delete_path_on_real_postgres_including_the_leftover_check(
    priced_repo,
):
    from core.doc_delete import delete_matter, find_leftover, leftover_check

    repo = priced_repo
    svc = _services(repo)
    uid, mid, docs, conv = await _pg_matter_with_work(repo, svc)
    for d in docs:
        assert await find_leftover(uid, d, svc) == ["file", "vectors", "database"]

    r = await delete_matter(uid, mid, "everything", svc, repo)
    assert (r.documents_deleted, r.conversations_deleted) == (2, 1)

    for d in docs:  # file, vectors and every database row are really gone
        assert await find_leftover(uid, d, svc) == []
        assert not await svc.files.exists(uid, d)
        assert await svc.vectors.count_upload_vectors(uid, d) == 0
    left = await repo._rows(
        "SELECT (SELECT count(*) FROM documents) AS d, "
        "(SELECT count(*) FROM document_chunks) AS c, "
        "(SELECT count(*) FROM conversations) AS v, (SELECT count(*) FROM matters) AS m"
    )
    assert left == [{"d": 0, "c": 0, "v": 0, "m": 0}]
    # logged (ids only, never text) and the nightly check agrees
    logged = await repo.deleted_documents(2)
    assert sorted(d for _, d in logged) == sorted(docs)
    audit = await repo._rows("SELECT action, target_id FROM audit_log")
    assert {r["action"] for r in audit} == {"delete"}
    assert "client file text" not in str(audit)
    assert await leftover_check(svc) == []


async def test_leftover_check_finds_and_removes_a_file_left_in_s3(priced_repo):
    from core.doc_delete import find_leftover, hard_delete_document, leftover_check

    repo = priced_repo
    svc = _services(repo)
    uid, mid, docs, _ = await _pg_matter_with_work(repo, svc)
    await hard_delete_document(uid, docs[0], svc)
    svc.files.put(uid, docs[0], b"%PDF came back")  # a stray copy reappears
    assert await find_leftover(uid, docs[0], svc) == ["file"]
    assert await leftover_check(svc) == []  # the nightly job removes it
    assert not await svc.files.exists(uid, docs[0])


async def test_delete_matter_only_on_real_postgres_unfiles_and_deletes_nothing(
    priced_repo,
):
    from core.doc_delete import delete_matter

    repo = priced_repo
    svc = _services(repo)
    uid, mid, docs, conv = await _pg_matter_with_work(repo, svc)
    r = await delete_matter(uid, mid, "unfile", svc, repo)
    assert (r.documents_deleted, r.conversations_deleted) == (0, 0)
    rows = await repo._rows("SELECT matter_id FROM documents")
    assert len(rows) == 2 and all(x["matter_id"] is None for x in rows)  # unfiled
    assert (await repo._rows("SELECT matter_id FROM conversations"))[0][
        "matter_id"
    ] is None
    for d in docs:  # nothing deleted, nothing orphaned: still the user's, still there
        assert await svc.files.exists(uid, d)


async def _user(repo, uid):
    return str((await repo.upsert_user(uid, None, None))["id"])


async def test_matters_on_real_postgres_crud_counts_and_isolation(priced_repo):
    repo = priced_repo
    a, b = await _user(repo, "uid-ma"), await _user(repo, "uid-mb")
    m = await repo.create_matter(a, "State v Doe", "matter")
    mid = str(m["id"])
    c1 = await repo.create_conversation(a, "research", None, mid)
    assert str(c1["matter_id"]) == mid
    await repo.create_document(a, "f.pdf", mid, "text")
    got = await repo.get_matter(a, mid)
    assert (got["conversation_count"], got["document_count"]) == (1, 1)
    assert await repo.get_matter(b, mid) is None  # another user's matter looks absent

    # a foreign matter id can never be used to file work
    stolen = await repo.create_conversation(b, "research", None, mid)
    assert stolen["matter_id"] is None  # inserted unfiled, not under Alice's matter
    mine_b = await repo.create_conversation(b, "research", None)
    assert await repo.set_conversation_matter(b, str(mine_b["id"]), mid) is False
    assert (
        await repo.set_conversation_matter(b, str(c1["id"]), None) is False
    )  # not hers

    # rename, archive, restore
    u = await repo.update_matter(a, mid, "Renamed", "archived")
    assert u["title"] == "Renamed" and u["status"] == "archived" and u["archived_at"]
    assert [x["id"] for x in await repo.list_matters(a, "active")] == []
    assert len(await repo.list_matters(a, "archived")) == 1
    u = await repo.update_matter(a, mid, None, "active")
    assert u["status"] == "active" and u["archived_at"] is None
    assert await repo.update_matter(b, mid, "x", None) is None

    # move between matters and unfile; list filters
    m2 = await repo.create_matter(a, "Other", "project")
    assert await repo.set_conversation_matter(a, str(c1["id"]), str(m2["id"]))
    inside, _ = await repo.list_conversations(a, None, 10, matter_id=str(m2["id"]))
    assert [str(x["id"]) for x in inside] == [str(c1["id"])]
    assert await repo.set_conversation_matter(a, str(c1["id"]), None)
    unfiled, _ = await repo.list_conversations(a, None, 10, unfiled=True)
    assert [str(x["id"]) for x in unfiled] == [str(c1["id"])]


async def test_history_search_on_real_postgres_is_full_text_and_never_crosses_users(
    priced_repo,
):
    from core.user_search import search_my_work

    repo = priced_repo
    a, b = await _user(repo, "uid-sa"), await _user(repo, "uid-sb")
    ca = await repo.create_conversation(a, "research", None)
    cb = await repo.create_conversation(b, "research", None)
    for uid, conv, q in (
        (a, ca, "bails for cheque dishonour"),
        (b, cb, "bail for cheque dishonour"),
    ):
        qid = await repo.add_user_message(uid, str(conv["id"]), q)
        assert qid
    await repo.add_user_message(b, str(cb["id"]), "zebracrossing is only in Bob's chat")

    hits_a = await search_my_work(repo, a, "bail cheque")  # "bails" stems to "bail"
    assert hits_a and {str(h["conversation_id"]) for h in hits_a} == {str(ca["id"])}
    hits_b = await search_my_work(repo, b, "bail cheque")
    assert {str(h["conversation_id"]) for h in hits_b} == {str(cb["id"])}
    assert (
        await search_my_work(repo, a, "zebracrossing") == []
    )  # Bob's word, not Alice's
    assert await search_my_work(repo, b, "zebracrossing")
    # operators in the query are plain words, not SQL or tsquery syntax
    leak = await search_my_work(repo, a, "'; DROP TABLE messages; --")
    assert isinstance(leak, list)
    assert (await repo._rows("SELECT count(*) AS n FROM messages"))[0]["n"] == 3


# ---- share links on a real PostgreSQL (O14) ------------------------------------------
async def _saved_answer(repo, uid, upload=False, fact=False):
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
    return cid, msgs[0]["id"], msgs[-1]["id"]


async def test_share_links_on_real_postgres_token_hashed_revocable_expiring(
    priced_repo,
):
    from datetime import UTC, datetime, timedelta

    from core.share import create_share_link, hash_token

    repo = priced_repo
    uid = await _user(repo, "uid-share")
    _, _, mid = await _saved_answer(repo, uid)
    link = await create_share_link(repo, uid, str(mid), 30)

    dump = str(await repo._rows("SELECT * FROM share_links"))
    assert link.token not in dump  # the token itself is never stored
    assert hash_token(link.token) in dump  # only its hash

    got = await repo.get_shared_answer(hash_token(link.token))
    assert got["question"] == "What is bail?" and got["text"].startswith(
        "Bail is the rule"
    )
    assert [c["status"] for c in got["citations"]] == ["verified"]
    assert "user_id" not in got and "email" not in str(got)  # no owner identity

    assert [x["id"] for x in await repo.list_share_links(uid)] == [link.id]
    assert "token" not in str(await repo.list_share_links(uid))

    # revoke: the very next read is gone (the row is read every time)
    assert await repo.revoke_share_link(uid, link.id) is True
    assert await repo.get_shared_answer(hash_token(link.token)) is None
    assert await repo.revoke_share_link(uid, link.id) is False

    # expiry: a past expires_at is gone too
    link2 = await create_share_link(repo, uid, str(mid), 30)
    assert await repo.get_shared_answer(hash_token(link2.token)) is not None
    await repo._exec(
        "UPDATE share_links SET expires_at = :e WHERE id = :i RETURNING id",
        e=datetime.now(UTC) - timedelta(seconds=1), i=link2.id,
    )  # fmt: skip
    assert await repo.get_shared_answer(hash_token(link2.token)) is None


async def test_the_database_itself_refuses_a_link_for_a_shaped_answer(priced_repo):
    """If application code forgot the rule, the trigger refuses (migration 0009)."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.exc import DBAPIError

    repo = priced_repo
    a, b = await _user(repo, "uid-ta"), await _user(repo, "uid-tb")
    _, q_id, clean = await _saved_answer(repo, a)
    _, _, upload = await _saved_answer(repo, a, upload=True)
    _, _, fact = await _saved_answer(repo, a, fact=True)
    soon = datetime.now(UTC) + timedelta(days=1)

    async def raw_insert(user_id, message_id, h):
        await repo._exec(
            """INSERT INTO share_links (user_id, message_id, token_hash, expires_at)
               VALUES (:u, :m, :h, :e) RETURNING id""",
            u=user_id, m=message_id, h=h, e=soon,
        )  # fmt: skip

    for bad, label in (
        (upload, "upload"),
        (fact, "fact"),
        (q_id, "a question"),
        (clean, "someone else"),
    ):
        user = b if label == "someone else" else a
        with pytest.raises(DBAPIError) as e:
            await raw_insert(user, bad, f"hash-{label}")
        assert "cannot be shared" in str(e.value)
    assert (await repo._rows("SELECT count(*) AS n FROM share_links"))[0]["n"] == 0
    await raw_insert(a, clean, "hash-ok")  # the clean answer is fine
    assert (await repo._rows("SELECT count(*) AS n FROM share_links"))[0]["n"] == 1


async def test_a_link_does_not_work_if_the_answer_is_later_found_to_be_shaped(
    priced_repo,
):
    from core.share import create_share_link, hash_token

    repo = priced_repo
    uid = await _user(repo, "uid-late")
    _, _, mid = await _saved_answer(repo, uid)
    link = await create_share_link(repo, uid, str(mid), 30)
    await repo._exec(
        "UPDATE messages SET shaped_by_upload = true WHERE id = :m RETURNING id", m=mid
    )  # fmt: skip
    assert await repo.get_shared_answer(hash_token(link.token)) is None


async def test_deleting_the_account_or_the_answer_removes_its_links(priced_repo):
    from core.share import create_share_link

    repo = priced_repo
    uid = await _user(repo, "uid-gone")
    cid, _, mid = await _saved_answer(repo, uid)
    await create_share_link(repo, uid, str(mid), 30)
    await repo._exec("DELETE FROM conversations WHERE id = :c RETURNING id", c=cid)
    assert (await repo._rows("SELECT count(*) AS n FROM share_links"))[0]["n"] == 0
