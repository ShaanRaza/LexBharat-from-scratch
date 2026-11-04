"""The fixed 11-step pipeline. Not an agent: the same steps, in the same order, always.

remember -> rewrite -> decide -> cache -> search -> rerank -> gate -> answer -> verify
-> show -> save.   (show lives in core/show.py and runs from the result.)

Guarantee: the only way to produce outcome "answered" is a VerifiedAnswer sealed by
the verifier (PipelineResult refuses anything else).
"""

from __future__ import annotations

import asyncio
import logging

from core.answer import answer, model_for
from core.cache import cache_lookup, cache_store, key_for
from core.contracts import (
    AnswerProvenance,
    Deps,
    Footer,
    OnStep,
    PipelineRequest,
    PipelineResult,
    StepEvent,
)
from core.coverage import data_as_of_text
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
        data_as_of=data_as_of_text(),
        snapshot_version=s.SNAPSHOT_VERSION,
        credit=s.DATA_CREDIT,
        personal_advice_flag=personal,
    )


def _emit(on_step: OnStep | None, event: StepEvent) -> None:
    """Tell the caller which step is running. Never lets a progress problem touch the
    answer: a failing callback is logged and ignored."""
    if on_step is None:
        return
    try:
        on_step(event)
    except Exception:  # noqa: BLE001
        log.warning("progress callback failed", exc_info=True)


def provenance_for(request: PipelineRequest, passages) -> AnswerProvenance:
    """Step 11 input: did an upload or a matter fact shape this answer? Fails closed:
    an upload chat counts as upload-shaped even if no upload passage survived."""
    return AnswerProvenance(
        shaped_by_upload=bool(request.document_ids)
        or any(p.kind == "upload" for p in passages),
        shaped_by_matter_fact=bool(request.matter_facts),
    )


async def _run(
    request: PipelineRequest, deps: Deps, on_step: OnStep | None = None
) -> tuple[PipelineResult, str | None]:
    """Steps 1-9. Returns the result and, only for a freshly written verified answer,
    the cache key to store it under AFTER step 11 has saved and counted it."""
    footer = _footer(deps)
    # Usage check first: an over-limit user must cost no AI call (TESTING.md).
    # Trade-off: they also cannot read cached answers until the limit resets.
    if not await deps.usage.allowed(request.user_id, request.plan):
        return PipelineResult("usage_limit", None, footer, "usage_limit"), None
    _emit(on_step, StepEvent("understanding"))
    memory = remember(request)  # 1
    rq = await rewrite(request, memory, deps)  # 2
    # 3: decisions run in parallel with the Voyage embedding
    decision, vector = await asyncio.gather(
        decide(rq, deps, uploads=bool(request.document_ids)),
        embed_query(rq.query, deps),
    )
    footer = _footer(deps, decision.safety == "personal_advice")
    if decision.safety == "trick":
        return PipelineResult("out_of_scope", None, footer, "blocked:trick"), None
    if not decision.in_scope:
        return (
            PipelineResult(
                "out_of_scope", None, footer, f"out_of_scope:{decision.scope}"
            ),
            None,
        )
    model = model_for(request.plan, deps)
    key = key_for(rq, decision, model)  # 4
    hit = await cache_lookup(request, key, footer, deps)
    if hit is not None:
        return hit, None  # free: not counted against the limit
    _emit(on_step, StepEvent("searching"))
    found = await search(request, rq, decision, vector, deps)  # 5
    top = await rerank(rq, found.passages, deps)  # 6
    _emit(on_step, StepEvent("checking", found=len(found.passages)))
    gate = await deps.gate(rq, top, deps)  # 7
    if not gate.passages:
        return (
            PipelineResult(
                "not_found", None, footer, "not_found", confidence=gate.confidence
            ),
            None,
        )
    _emit(
        on_step,
        StepEvent("writing", found=len(found.passages), kept=len(gate.passages)),
    )
    draft = await answer(request, rq, decision, gate, deps)  # 8
    _emit(on_step, StepEvent("verifying"))
    verified = await deps.verify(draft, gate.passages, deps)  # 9
    if not verified.citations:
        # No surviving citation (all failed, or none were written): not an answer.
        # (verify() already wrote the removals to invented_citation_log.)
        return (
            PipelineResult(
                "not_found",
                None,
                footer,
                "not_found",
                confidence=gate.confidence,
                removed=verified.removed,
            ),
            None,
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
        provenance=provenance_for(request, gate.passages),
    )
    return result, key


async def run_pipeline(
    request: PipelineRequest, deps: Deps, on_step: OnStep | None = None
) -> PipelineResult:
    """Steps 1-9 and 11. Any failure becomes outcome "error"; nothing partial."""
    deps.begin_run()  # Jev batches only calls from this run
    key: str | None = None
    try:
        result, key = await _run(request, deps, on_step)
    except Exception as e:  # noqa: BLE001
        log.exception("pipeline failed")
        result = PipelineResult(
            "error", None, _footer(deps), "error", error=type(e).__name__
        )
    saved = await save(request, result, deps)  # 11: saves, then counts
    # Cache only AFTER the answer is saved and counted. If saving or counting raised,
    # the answer was never delivered, so it must not be in the cache where a retry
    # would serve it free and uncounted (A59).
    if key is not None and saved.outcome == "answered":
        await cache_store(request, key, saved, deps)  # only verified answers
    return saved
