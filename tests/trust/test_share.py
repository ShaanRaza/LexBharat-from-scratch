"""Share by link (PRD-v2 O14): the refusal is the trust-critical part.

An answer shaped by an upload or a remembered matter fact must NEVER get a link. These
tests call the rule directly (no web, no database) and try to get around it."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.share import (
    MessageNotFound,
    ShareRefused,
    check_shareable,
    create_share_link,
    hash_token,
    new_token,
)

CLEAN = {
    "id": "m1",
    "role": "assistant",
    "shaped_by_upload": False,
    "shaped_by_matter_fact": False,
}


class SpyRepo:
    """Remembers every call; says what the stored message is."""

    def __init__(self, message):
        self.message, self.created, self.lookups = message, [], []

    async def get_message_for_share(self, user_id, message_id):
        self.lookups.append((user_id, message_id))
        return self.message

    async def create_share_link(self, user_id, message_id, token_hash, expires_at):
        self.created.append((user_id, message_id, token_hash, expires_at))
        return {"id": "link-1"}


# ---- the refusal, called directly ------------------------------------------------
def test_a_clean_answer_may_be_shared():
    check_shareable(CLEAN)


@pytest.mark.parametrize(
    "flags, reason",
    [
        ({"shaped_by_upload": True}, "shaped_by_upload"),
        ({"shaped_by_matter_fact": True}, "shaped_by_matter_fact"),
        ({"shaped_by_upload": True, "shaped_by_matter_fact": True}, "shaped_by_upload"),
    ],
)
def test_creating_a_link_is_refused_when_an_upload_or_a_matter_fact_shaped_the_answer(
    flags, reason
):
    with pytest.raises(ShareRefused) as e:
        check_shareable({**CLEAN, **flags})
    assert e.value.reason == reason


def test_a_question_is_not_an_answer():
    with pytest.raises(ShareRefused) as e:
        check_shareable({**CLEAN, "role": "user"})
    assert e.value.reason == "not_an_answer"


@pytest.mark.parametrize(
    "flags", [{"shaped_by_upload": True}, {"shaped_by_matter_fact": True}]
)
async def test_a_refused_answer_never_reaches_the_repository_write(flags):
    repo = SpyRepo({**CLEAN, **flags})
    with pytest.raises(ShareRefused):
        await create_share_link(repo, "u1", "m1", 30)
    assert repo.created == []  # nothing was written, so no token exists to leak


@pytest.mark.parametrize(
    "msg",
    [
        {"id": "m1", "role": "assistant"},  # no flags at all
        {
            "id": "m1",
            "role": "assistant",
            "shaped_by_upload": None,
            "shaped_by_matter_fact": False,
        },
        {"id": "m1", "role": "assistant", "shaped_by_upload": False},  # one missing
        {
            "id": "m1",
            "role": "assistant",
            "shaped_by_upload": 0,
            "shaped_by_matter_fact": 0,
        },
        {
            "id": "m1",
            "role": "assistant",
            "shaped_by_upload": "false",
            "shaped_by_matter_fact": False,
        },
    ],
)
async def test_unknown_provenance_is_never_read_as_safe_to_share(msg):
    """Fail closed: a flag must be exactly False. Absent, None or a look-alike value
    refuses, and nothing is written."""
    repo = SpyRepo(msg)
    with pytest.raises(ShareRefused) as e:
        await create_share_link(repo, "u1", "m1", 30)
    assert e.value.reason == "unknown_provenance"
    assert repo.created == []


async def test_someone_elses_or_missing_message_is_not_found_and_nothing_is_written():
    repo = SpyRepo(None)
    with pytest.raises(MessageNotFound):
        await create_share_link(repo, "mallory", "m1", 30)
    assert repo.created == []


# ---- the token ---------------------------------------------------------------------
def test_tokens_are_long_random_and_unique():
    tokens = {new_token() for _ in range(2000)}
    assert len(tokens) == 2000
    assert all(len(t) >= 43 for t in tokens)  # 32 random bytes, url-safe


async def test_only_a_hash_is_handed_to_storage_and_the_token_is_not_the_hash():
    repo = SpyRepo(CLEAN)
    link = await create_share_link(repo, "u1", "m1", 30)
    _, _, stored, _ = repo.created[0]
    assert stored == hash_token(link.token) and stored != link.token
    assert len(stored) == 64 and link.token not in stored
    assert hash_token(link.token) == hash_token(link.token)  # stable lookup key


async def test_expiry_comes_from_the_setting_not_the_code():
    repo = SpyRepo(CLEAN)
    now = datetime(2026, 11, 2, tzinfo=UTC)
    link = await create_share_link(repo, "u1", "m1", 7, now=now)
    assert link.expires_at == now + timedelta(days=7)
    assert repo.created[0][3] == link.expires_at
