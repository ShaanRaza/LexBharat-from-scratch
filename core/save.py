"""Step 11 - Save: message, source ids, decisions, confidence, model, token counts.
The usage meter counts one answer (never for cache hits, errors or non-answers)."""

from __future__ import annotations

import dataclasses

from core.contracts import Deps, PipelineRequest, PipelineResult


async def save(
    request: PipelineRequest, result: PipelineResult, deps: Deps
) -> PipelineResult:
    """Input: finished result. Output: the same result with `counted` filled in."""
    counted = result.outcome == "answered" and not result.cache_hit
    result = dataclasses.replace(result, counted=counted)
    await deps.store.save(request, result)
    if counted:
        await deps.usage.count_one(request.user_id)
    return result
