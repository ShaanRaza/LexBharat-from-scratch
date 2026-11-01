"""Per-user hourly limits for the helper routes (A52).

Plain words: "Improve my question" and next-question suggestions each call a paid model
but are not answers, so they never use the answer limit. Instead each user gets a fixed
number of calls per hour (a setting, not a number in code). The counter lives in Redis
through adapters/cache.py; if the counter cannot be reached the call is refused, because
a paid model call must not run with no limit at all."""

from __future__ import annotations

import logging
import time

from fastapi import Request

from api.errors import ApiError
from core.spend import AiCall

log = logging.getLogger("api.ratelimit")
WINDOW_S = 3600


async def enforce_hourly(
    request: Request, user_id: str, name: str, limit: int | None
) -> None:
    """Count one call; raise 429 when the user is over `limit` this hour.
    `limit` None switches the limit off."""
    if limit is None:
        return
    key = f"rl:{name}:{user_id}:{int(time.time() // WINDOW_S)}"
    if not await request.app.state.limiter.hit(key, limit, WINDOW_S):
        raise ApiError(
            429, "rate_limited", "Too many requests. Please try again later."
        )


async def record_spend(request: Request, user_id: str, call: AiCall) -> None:
    """Add the call's tokens to the daily AI spend. Never fails the request."""
    try:
        await request.app.state.repo.record_ai_call(user_id, call)
    except Exception:  # noqa: BLE001
        log.exception("could not record AI spend for %s", call.feature)
