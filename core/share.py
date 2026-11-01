"""Share a saved answer by link (PRD-v2 O14). The trust-critical rule lives here.

Plain words: an answer may be shared only if it was built purely from the public
dataset. When an answer is saved (pipeline step 11) the pipeline records whether an
upload or a remembered matter fact shaped it (the provenance flags, A47). Creating a
link is REFUSED when either flag is set. A database trigger (migration 0009) enforces
the same rule, so a bug here cannot create a link either.

The link's token is random (256 bits) and only its SHA-256 is stored, so a leaked
database does not leak live links. Links expire (a setting) and can be revoked; the
public route reads the row on every request, so revoking takes effect at once.

Not a pipeline step."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

RefusalReason = Literal[
    "not_an_answer", "shaped_by_upload", "shaped_by_matter_fact", "unknown_provenance"
]


class ShareRefused(Exception):
    """This answer may not be shared. `reason` says why."""

    def __init__(self, reason: RefusalReason):
        super().__init__(reason)
        self.reason = reason


class MessageNotFound(Exception):
    pass


@dataclass(frozen=True)
class CreatedLink:
    id: str
    token: str  # shown ONCE; only its hash is stored
    expires_at: datetime


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_shareable(message: dict) -> None:
    """Raise ShareRefused unless this stored message may be shared."""
    if message.get("role") != "assistant":
        raise ShareRefused("not_an_answer")
    # Fail closed: a flag must be exactly False. Missing or unreadable provenance is
    # never read as "safe to share".
    up, fact = message.get("shaped_by_upload"), message.get("shaped_by_matter_fact")
    if up is True:
        raise ShareRefused("shaped_by_upload")
    if fact is True:
        raise ShareRefused("shaped_by_matter_fact")
    if up is not False or fact is not False:
        raise ShareRefused("unknown_provenance")


async def create_share_link(
    repo: Any, user_id: str, message_id: str, ttl_days: int, now: datetime | None = None
) -> CreatedLink:
    msg = await repo.get_message_for_share(user_id, message_id)  # user-filtered
    if msg is None:
        raise MessageNotFound(message_id)
    check_shareable(msg)
    token = new_token()
    expires = (now or datetime.now(UTC)) + timedelta(days=ttl_days)
    row = await repo.create_share_link(user_id, message_id, hash_token(token), expires)
    return CreatedLink(str(row["id"]), token, expires)
