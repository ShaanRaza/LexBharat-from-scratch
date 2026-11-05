# ruff: noqa: E501
"""The in-memory repository must behave EXACTLY like PostgreSQL for sharing (A59).

Every API test and all of fake mode run on MemoryRepo; production runs on PostgreSQL. If
the fake is more lenient than the database, tests prove nothing. This runs the same share
scenarios against both backends and asserts the outcomes are identical, case by case.

A missing provenance flag cannot be STORED in PostgreSQL at all (NOT NULL, no default),
so for that one case the identical outcome is "no link can exist": the in-memory repo
refuses to create one, the database refuses to hold the answer."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from api.pg_repo import PgRepo, make_engine
from api.repo import MemoryRepo
from core.contracts import AnswerProvenance, PipelineRequest
from core.settings import Settings
from core.share import (
    MessageNotFound,
    ShareRefused,
    create_share_link,
    hash_token,
)
from tests.pg_roles import app_login

PG = pytest.param(
    "postgres",
    marks=pytest.mark.skipif(
        not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
    ),
)


class Memory:
    def __init__(self):
        self.repo = MemoryRepo()

    async def user(self, name):
        return str((await self.repo.upsert_user(name, None, None))["id"])

    async def answer(self, uid, upload=False, fact=False):
        conv = await self.repo.create_conversation(uid, "research", None)
        await self.repo.add_user_message(uid, conv["id"], "What is bail?")
        res = SimpleNamespace(
            provenance=AnswerProvenance(upload, fact), outcome="answered", cache_hit=False,
            model="m", input_tokens=0, output_tokens=0,
            answer=SimpleNamespace(text="Bail is the rule [S1].", citations=()),
        )  # fmt: skip
        await self.repo.save(
            SimpleNamespace(conversation_id=conv["id"], user_id=uid), res
        )
        msgs = self.repo.msgs[conv["id"]]
        return msgs[0]["id"], msgs[-1]["id"]  # (question id, answer id)

    async def answer_without_flags(self, uid):
        q, a = await self.answer(uid)
        for conv in self.repo.msgs.values():
            for m in conv:
                if m["id"] == a:
                    m.pop("shaped_by_upload", None)
                    m.pop("shaped_by_matter_fact", None)
        return a

    async def flag_later(self, mid):
        for conv in self.repo.msgs.values():
            for m in conv:
                if m["id"] == mid:
                    m["shaped_by_upload"] = True

    async def expire(self, link_id):
        self.repo.shares[link_id]["expires_at"] = datetime.now(UTC) - timedelta(
            seconds=1
        )

    async def close(self):
        pass


class Postgres:
    def __init__(self):
        # The code under test connects as the application role; cleanup is the owner's.
        self.owner_url = os.environ["TEST_DATABASE_URL"]
        self._login = app_login(self.owner_url)
        self.engine = make_engine(self._login.__enter__())
        self.repo = PgRepo(self.engine, Settings(_env_file=None))

    def sql(self, statement, **p):
        with self.engine.begin() as c:
            c.execute(text(statement), p)

    async def user(self, name):
        return str(
            (await self.repo.upsert_user(f"{name}-{uuid.uuid4().hex[:6]}", None, None))[
                "id"
            ]
        )

    async def answer(self, uid, upload=False, fact=False):
        conv = await self.repo.create_conversation(uid, "research", None)
        cid = str(conv["id"])
        await self.repo.add_user_message(uid, cid, "What is bail?")
        res = SimpleNamespace(
            provenance=AnswerProvenance(upload, fact), outcome="answered", cache_hit=False,
            model="m", input_tokens=0, output_tokens=0,
            answer=SimpleNamespace(text="Bail is the rule [S1].", citations=()),
        )  # fmt: skip
        await self.repo.save(PipelineRequest(uid, "q", cid), res)
        msgs = (await self.repo.get_conversation(uid, cid))["messages"]
        return msgs[0]["id"], msgs[-1]["id"]

    async def answer_without_flags(self, uid):
        """PostgreSQL cannot even hold such a message: the INSERT is refused."""
        conv = await self.repo.create_conversation(uid, "research", None)
        try:
            self.sql(
                "INSERT INTO messages (conversation_id, role, content) VALUES (:c, 'assistant', 'x')",
                c=str(conv["id"]),
            )
        except DBAPIError:
            return None  # cannot exist
        raise AssertionError("PostgreSQL stored a message with unknown provenance")

    async def flag_later(self, mid):
        self.sql("UPDATE messages SET shaped_by_upload = true WHERE id = :m", m=mid)

    async def expire(self, link_id):
        self.sql(
            "UPDATE share_links SET expires_at = now() - interval '1 second' WHERE id = :i",
            i=link_id,
        )

    async def close(self):
        self.engine.dispose()
        self._login.__exit__(None, None, None)
        owner = make_engine(self.owner_url)
        with owner.begin() as c:
            c.execute(text("TRUNCATE users, share_links CASCADE"))
        owner.dispose()


async def attempt(b, uid, mid):
    """What happens when `uid` asks for a link to message `mid`: a short outcome string."""
    try:
        link = await create_share_link(b.repo, uid, mid, 30)
    except MessageNotFound:
        return "notfound", None
    except ShareRefused as e:
        return f"refused:{e.reason}", None
    live = await b.repo.get_shared_answer(hash_token(link.token)) is not None
    return ("created" if live else "created-but-dark"), link


async def run_scenarios(b) -> dict[str, str]:
    out: dict[str, str] = {}
    alice, mallory = await b.user("alice"), await b.user("mallory")
    q, clean = await b.answer(alice)
    _, upload = await b.answer(alice, upload=True)
    _, fact = await b.answer(alice, fact=True)
    _, both = await b.answer(alice, upload=True, fact=True)

    out["clean answer"] = (await attempt(b, alice, clean))[0]
    out["upload-shaped"] = (await attempt(b, alice, upload))[0]
    out["matter-fact-shaped"] = (await attempt(b, alice, fact))[0]
    out["both flags"] = (await attempt(b, alice, both))[0]
    out["a question, not an answer"] = (await attempt(b, alice, q))[0]
    out["someone else's answer"] = (await attempt(b, mallory, clean))[0]
    out["unknown id"] = (await attempt(b, alice, str(uuid.uuid4())))[0]

    # the repository write path refuses on its own, whoever calls it
    for label, mid in (
        ("write path: upload", upload),
        ("write path: fact", fact),
        ("write path: question", q),
    ):
        try:
            await b.repo.create_share_link(
                alice, mid, "h" + label, datetime.now(UTC) + timedelta(days=1)
            )
            out[label] = "created"
        except (ValueError, DBAPIError):
            out[label] = "refused"

    # unknown provenance: no link can exist, in either backend
    unknown = await b.answer_without_flags(alice)
    if unknown is None:
        out["unknown provenance"] = "no link possible"
    else:
        res = (await attempt(b, alice, unknown))[0]
        out["unknown provenance"] = (
            "no link possible" if res.startswith("refused:") else res
        )

    # lifecycle of a good link
    _, link = await attempt(b, alice, clean)
    token_hash = hash_token(link.token)
    out["live before revoke"] = (
        "live" if await b.repo.get_shared_answer(token_hash) else "dark"
    )
    assert await b.repo.revoke_share_link(alice, link.id) is True
    out["after revoke"] = (
        "live" if await b.repo.get_shared_answer(token_hash) else "dark"
    )
    out["revoke twice"] = str(await b.repo.revoke_share_link(alice, link.id))
    _, link2 = await attempt(b, alice, clean)
    out["another user revokes"] = str(await b.repo.revoke_share_link(mallory, link2.id))
    await b.expire(link2.id)
    out["after expiry"] = (
        "live" if await b.repo.get_shared_answer(hash_token(link2.token)) else "dark"
    )
    _, q2 = await b.answer(alice)
    _, link3 = await attempt(b, alice, q2)
    await b.flag_later(q2)
    out["answer flagged after link"] = (
        "live" if await b.repo.get_shared_answer(hash_token(link3.token)) else "dark"
    )
    out["listing hides the token"] = str(
        all("token" not in x for x in await b.repo.list_share_links(alice))
    )
    return out


@pytest.mark.parametrize("backend", ["memory", PG])
async def test_the_share_rules_hold_in_each_backend(backend):
    b = Memory() if backend == "memory" else Postgres()
    try:
        out = await run_scenarios(b)
    finally:
        await b.close()
    assert out["clean answer"] == "created" and out["live before revoke"] == "live"
    for k in (
        "upload-shaped",
        "matter-fact-shaped",
        "both flags",
        "a question, not an answer",
    ):
        assert out[k].startswith("refused:"), (k, out[k])
    assert out["someone else's answer"] == out["unknown id"] == "notfound"
    assert out["unknown provenance"] == "no link possible"
    assert (
        out["after revoke"]
        == out["after expiry"]
        == out["answer flagged after link"]
        == "dark"
    )


async def test_memory_and_postgres_behave_identically_for_sharing():
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL not set")
    m, p = Memory(), Postgres()
    try:
        mem, pg = await run_scenarios(m), await run_scenarios(p)
    finally:
        await m.close()
        await p.close()
    assert mem.keys() == pg.keys()
    diffs = {k: (mem[k], pg[k]) for k in mem if mem[k] != pg[k]}
    assert diffs == {}, f"the fake differs from the database: {diffs}"
