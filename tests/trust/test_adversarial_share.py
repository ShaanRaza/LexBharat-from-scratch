# ruff: noqa: E501
"""Attacks on share links (PRD-v2 O14): get a link for an answer that an upload or a
remembered matter fact shaped, or whose provenance is missing/odd, by any path."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from api.repo import MemoryRepo
from core.contracts import AnswerProvenance
from core.share import (
    MessageNotFound,
    ShareRefused,
    check_shareable,
    create_share_link,
    hash_token,
)

CLEAN = {"role": "assistant", "shaped_by_upload": False, "shaped_by_matter_fact": False}


class Truthy:
    """Not a bool, but truthy and equal to everything."""

    def __bool__(self):
        return True

    def __eq__(self, other):
        return True

    __hash__ = object.__hash__


class Falsy:
    """Looks like False: falsy, equal to False, but is not the bool False."""

    def __bool__(self):
        return False

    def __eq__(self, other):
        return other is False or other == 0

    __hash__ = object.__hash__


class NumpyBool:
    def __init__(self, v):
        self.v = v

    def __bool__(self):
        return self.v

    def __eq__(self, other):
        return bool(other) == self.v

    __hash__ = object.__hash__


ODD_FLAGS = [
    None, 0, 1, "", "true", "false", "False", "0", [], [False], {}, 0.0, 1.0,
    Truthy(), Falsy(), NumpyBool(False), NumpyBool(True), b"\x00",
]  # fmt: skip


@pytest.mark.parametrize("flag", ODD_FLAGS)
def test_any_flag_value_that_is_not_exactly_false_refuses_the_link(flag):
    for field in ("shaped_by_upload", "shaped_by_matter_fact"):
        with pytest.raises(ShareRefused):
            check_shareable({**CLEAN, field: flag})


def test_missing_keys_and_extra_keys_do_not_help():
    for msg in ({}, {"role": "assistant"}, {"role": "assistant", "shaped_by_upload": False},
                {"role": "assistant", "shaped_by_matter_fact": False}):  # fmt: skip
        with pytest.raises(ShareRefused):
            check_shareable(msg)
    # extra keys that look like permission change nothing, and the clean case still passes
    check_shareable({**CLEAN, "shareable": True, "is_public": True})
    with pytest.raises(ShareRefused):
        check_shareable(
            {"role": "assistant", "shareable": True, "shaped_by_upload": None}
        )


@pytest.mark.parametrize("role", ["Assistant", "ASSISTANT", " assistant", "assistant ",
                                  "assistant​", "аssistant", "user", "system", "",
                                  None, 0])  # fmt: skip
def test_only_the_exact_role_assistant_is_shareable(role):
    with pytest.raises(ShareRefused):
        check_shareable({**CLEAN, "role": role})


async def test_a_repository_that_lies_about_ownership_still_cannot_make_a_refused_link():
    class Repo:
        created = []

        async def get_message_for_share(self, user_id, message_id):
            return {**CLEAN, "shaped_by_upload": True}

        async def create_share_link(self, *a):
            self.created.append(a)

    repo = Repo()
    with pytest.raises(ShareRefused):
        await create_share_link(repo, "u", "m", 30)
    assert repo.created == []


async def test_the_ttl_cannot_be_used_to_make_a_link_that_never_expires_or_is_expired():
    class Repo:
        async def get_message_for_share(self, u, m):
            return {**CLEAN, "id": m}

        async def create_share_link(self, u, m, h, exp):
            self.exp = exp
            return {"id": "l"}

    repo = Repo()
    now = datetime(2026, 11, 2, tzinfo=UTC)
    link = await create_share_link(repo, "u", "m", 0, now=now)
    assert (
        link.expires_at == now
    )  # a zero ttl is already expired: nothing lives forever
    assert hash_token(link.token) != link.token


# ---- the in-memory repository (the one used by every API test) ------------------------
def _put(repo, user_id, **msg):
    cid = "conv-" + user_id
    repo.convs[cid] = {"user_id": user_id, "matter_id": None, "title": "t"}
    repo.msgs.setdefault(cid, []).append(
        {"id": msg.pop("id"), "content": "text", "citations": [], **msg}
    )


FUTURE = datetime.now(UTC) + timedelta(days=1)

NO_FLAGS = pytest.mark.xfail(
    strict=True,
    reason="BREAK: MemoryRepo.get_message_for_share coerces a MISSING/None provenance "
    "flag to False with bool() (api/repo.py:179-180), so the fail-closed rule in "
    "core/share.py never sees it; the in-memory repo (every API test, fake mode) "
    "shares an answer whose provenance is unknown",
)


@pytest.mark.parametrize(
    "flags",
    [
        pytest.param({}, marks=NO_FLAGS),
        pytest.param(
            {"shaped_by_upload": None, "shaped_by_matter_fact": None}, marks=NO_FLAGS
        ),
        pytest.param({"shaped_by_upload": False}, marks=NO_FLAGS),
    ],
)
async def test_memory_repo_refuses_a_link_for_an_answer_with_missing_provenance(flags):
    repo = MemoryRepo()
    _put(repo, "alice", id="m1", role="assistant", **flags)
    with pytest.raises(ShareRefused):
        await create_share_link(repo, "alice", "m1", 30)
    assert repo.shares == {}


@pytest.mark.parametrize("flags", [{}, {"shaped_by_upload": None}])
@pytest.mark.xfail(
    strict=True,
    reason="BREAK: MemoryRepo.create_share_link 'mirrors the trigger' but reads the "
    "same bool()-coerced view, so it also accepts missing provenance (api/repo.py:183)",
)
async def test_memory_repo_write_path_refuses_missing_provenance_too(flags):
    repo = MemoryRepo()
    _put(repo, "alice", id="m1", role="assistant", **flags)
    with pytest.raises(ValueError):
        await repo.create_share_link("alice", "m1", "h" * 64, FUTURE)


@pytest.mark.parametrize(
    "msg",
    [
        {"role": "assistant", "shaped_by_upload": True, "shaped_by_matter_fact": False},
        {"role": "assistant", "shaped_by_upload": False, "shaped_by_matter_fact": True},
        {"role": "user", "shaped_by_upload": False, "shaped_by_matter_fact": False},
    ],
)
async def test_memory_repo_write_path_refuses_shaped_answers_and_questions(msg):
    repo = MemoryRepo()
    _put(repo, "alice", id="m1", **msg)
    with pytest.raises(ValueError):
        await repo.create_share_link("alice", "m1", "h" * 64, FUTURE)
    assert repo.shares == {}


async def test_memory_repo_will_not_link_another_users_answer_or_a_missing_one():
    repo = MemoryRepo()
    _put(repo, "alice", id="m1", **CLEAN)
    for uid, mid in (("mallory", "m1"), ("alice", "nope"), ("mallory", "nope")):
        with pytest.raises(ValueError):
            await repo.create_share_link(uid, mid, "h" * 64, FUTURE)
        with pytest.raises(MessageNotFound):
            await create_share_link(repo, uid, mid, 30)
    assert repo.shares == {}


async def test_memory_public_read_dies_after_any_tamper_that_makes_the_answer_shaped():
    for tamper in (
        {"shaped_by_upload": True},
        {"shaped_by_matter_fact": True},
        {"role": "user"},
    ):
        repo = MemoryRepo()
        _put(repo, "alice", id="m1", **CLEAN)
        link = await create_share_link(repo, "alice", "m1", 30)
        assert await repo.get_shared_answer(hash_token(link.token)) is not None
        repo.msgs["conv-alice"][0].update(tamper)
        assert await repo.get_shared_answer(hash_token(link.token)) is None


async def test_the_public_read_does_not_accept_a_guessable_or_malformed_hash():
    repo = MemoryRepo()
    _put(repo, "alice", id="m1", **CLEAN)
    link = await create_share_link(repo, "alice", "m1", 30)
    for h in ("", "0" * 64, link.token, "%", "' OR '1'='1", link.token.upper(),
              hash_token(link.token)[:-1], hash_token(link.token) + "0"):  # fmt: skip
        assert await repo.get_shared_answer(h) is None


async def test_a_saved_shaped_answer_cannot_be_shared_end_to_end_with_the_real_save_path():
    repo = MemoryRepo()
    conv = await repo.create_conversation("alice", "research", None)
    await repo.add_user_message("alice", conv["id"], "q")
    result = SimpleNamespace(
        outcome="answered", cache_hit=False, model="m", input_tokens=0, output_tokens=0,
        provenance=AnswerProvenance(True, False),
        answer=SimpleNamespace(text="A [S1].", citations=()),
    )  # fmt: skip
    await repo.save(
        SimpleNamespace(conversation_id=conv["id"], user_id="alice"), result
    )
    mid = repo.msgs[conv["id"]][-1]["id"]
    with pytest.raises(ShareRefused):
        await create_share_link(repo, "alice", mid, 30)
