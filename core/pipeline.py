"""The fixed 11-step pipeline. Not an agent: the same steps, in the same order, always.

remember -> rewrite -> decide -> cache -> search -> rerank -> gate -> answer -> verify
-> show -> save.   (show lives in core/show.py and runs from the result.)

Guarantee: the only way to produce outcome "answered" is a VerifiedAnswer sealed by
the verifier (PipelineResult refuses anything else).
"""

from __future__ import annotations

import asyncio
import logging

from adapters.jev import begin_run
from core.answer import answer, model_for
from core.cache import cache_lookup, cache_store, key_for
from core.contracts import (
    Deps,
    Footer,
    PipelineRequest,
    PipelineResult,
)
from core.decide import decide
from core.memory import remember
from core.rerank import rerank
from core.rewrite import rewrite
from core.save import save
from core.search import embed_query, search

log = logging.getLogger(__name__)


def _footer(deps: Deps, personal: bool = False) -> Footer:
    s = deps.settings
    return Footer(
        data_as_of=s.DATA_AS_OF,
        snapshot_version=s.SNAPSHOT_VERSION,
        credit=s.DATA_CREDIT,
        personal_advice_flag=personal,
    )


async def _run(request: PipelineRequest, deps: Deps) -> PipelineResult:
    footer = _footer(deps)
    # Usage check first: an over-limit user must cost no AI call (TESTING.md).
    # Trade-off: they also cannot read cached answers until the limit resets.
    if not await deps.usage.allowed(request.user_id, request.plan):
        return PipelineResult("usage_limit", None, footer, "usage_limit")
    memory = remember(request)  # 1
    rq = await rewrite(request, memory, deps)  # 2
    # 3: decisions run in parallel with the Voyage embedding
    decision, vector = await asyncio.gather(
        decide(rq, deps, uploads=bool(request.document_ids)),
        embed_query(rq.query, deps),
    )
    footer = _footer(deps, decision.safety == "personal_advice")
    if decision.safety == "trick":
        return PipelineResult("out_of_scope", None, footer, "blocked:trick")
    if not decision.in_scope:
        return PipelineResult(
            "out_of_scope", None, footer, f"out_of_scope:{decision.scope}"
        )
    model = model_for(request.plan, deps)
    key = key_for(rq, decision, model)  # 4
    hit = await cache_lookup(request, key, footer, deps)
    if hit is not None:
        return hit  # free: not counted against the limit
    found = await search(request, rq, decision, vector, deps)  # 5
    top = await rerank(rq, found.passages, deps)  # 6
    gate = await deps.gate(rq, top, deps)  # 7
    if not gate.passages:
        return PipelineResult(
            "not_found", None, footer, "not_found", confidence=gate.confidence
        )
    draft = await answer(request, rq, decision, gate, deps)  # 8
    verified = await deps.verify(draft, gate.passages, deps)  # 9
    if not verified.citations:
        # No surviving citation (all failed, or none were written): not an answer.
        # (verify() already wrote the removals to invented_citation_log.)
        return PipelineResult(
            "not_found",
            None,
            footer,
            "not_found",
            confidence=gate.confidence,
            removed=verified.removed,
        )
    result = PipelineResult(
        "answered",
        verified,
        footer,
        "keyword_only" if found.keyword_only else "",
        confidence=gate.confidence,
        model=draft.model,
        input_tokens=draft.input_tokens,
        output_tokens=draft.output_tokens,
        removed=verified.removed,
    )
    await cache_store(request, key, result, deps)  # only verified answers
    return result


async def run_pipeline(request: PipelineRequest, deps: Deps) -> PipelineResult:
    """Steps 1-9 and 11. Any failure becomes outcome "error"; nothing partial."""
    begin_run()  # Jev batches only calls from this run
    try:
        result = await _run(request, deps)
    except Exception as e:  # noqa: BLE001
        log.exception("pipeline failed")
        result = PipelineResult(
            "error", None, _footer(deps), "error", error=type(e).__name__
        )
    return await save(request, result, deps)  # 11
