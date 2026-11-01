"""The 11-step research pipeline, in fixed order. A fixed pipeline, not an agent.

    remember -> rewrite -> decide -> cache -> search -> rerank -> gate
             -> answer -> verify -> show -> save

`run_pipeline` calls one function per step (each in its own file in core/). Early exits:
  - out of scope / blocked request  -> stop after step 3 (no search, no writing cost)
  - nothing clears the gate         -> "not found", nothing written, nothing saved
  - model provider down             -> sources only, no written answer
  - cache hit                       -> steps 5-8 skipped, user's limit not charged

Step 9 (verify) is ALWAYS run on everything that reaches the user, including cache hits.
`run_pipeline` has no flag to skip it, `PipelineDeps` has no slot to replace it, and
`show()` rejects any answer the verifier did not produce.
"""

from __future__ import annotations

from dataclasses import dataclass

from adapters.cache import AnswerCache
from adapters.gemini import LLMClient, LLMUnavailable
from adapters.jev import DecisionAdapter, DecisionUnavailable
from adapters.qdrant import VectorStore
from adapters.voyage import VoyageClient
from core import copy
from core.answer import answer, model_for_plan
from core.cache import cache_lookup
from core.decide import decide
from core.gate import gate
from core.models import (
    AnswerDraft,
    PipelineRequest,
    PipelineResult,
    Source,
)
from core.remember import remember
from core.rerank import rerank
from core.rewrite import rewrite
from core.save import MessageRepository, save
from core.search import search
from core.settings import Settings
from core.show import show
from core.verify import verify_answer


@dataclass
class PipelineDeps:
    """Everything the pipeline talks to. Tests pass Fakes; production passes real ones."""

    settings: Settings
    llm: LLMClient
    voyage: VoyageClient
    store: VectorStore
    decisions: DecisionAdapter
    cache: AnswerCache
    repo: MessageRepository


async def run_pipeline(request: PipelineRequest, deps: PipelineDeps) -> PipelineResult:
    s = deps.settings

    # 1. Remember
    memory = await remember(request.history, request.summary, deps.llm, s)
    # 2. Rewrite
    rw = await rewrite(request.message, memory, deps.llm, s)
    # 3. Decide
    decision = await decide(rw, deps.decisions, is_upload_chat=request.is_upload_chat)
    base = {"memory": memory, "rewrite": rw, "decision": decision}
    if decision.scope != "in_scope":
        return PipelineResult("out_of_scope", copy.COVERAGE, **base)
    if decision.safety == "trick":
        return PipelineResult("blocked", copy.BLOCKED, **base)

    # 4. Cache
    model = model_for_plan(s, request.plan)
    lookup = await cache_lookup(
        rw.query,
        decision.filters,
        model,
        deps.cache,
        is_upload_chat=request.is_upload_chat,
    )

    keyword_only = False
    if lookup.hit and lookup.payload is not None:
        # Steps 5-8 skipped. We rebuild the draft and sources exactly as first used.
        p = lookup.payload
        sources = tuple(Source(**d) for d in p["sources"])
        draft = AnswerDraft(
            p["draft_text"], p["model"], p["tokens_in"], p["tokens_out"]
        )
        jev_used = decision.jev_used
    else:
        # 5. Search   6. Re-rank
        found = await search(rw, decision.filters, deps.voyage, deps.store)
        keyword_only = found.keyword_only
        ranked = await rerank(rw.query, found, deps.voyage)
        # 7. Gate
        try:
            gated = await gate(
                rw.query,
                ranked,
                deps.decisions,
                s,
                is_upload_chat=request.is_upload_chat,
            )
        except DecisionUnavailable:
            return PipelineResult("unavailable", copy.TRY_AGAIN, **base)
        if not gated.found:
            return PipelineResult(
                "not_found", copy.NOT_FOUND, keyword_only=keyword_only, **base
            )
        sources = gated.sources
        jev_used = decision.jev_used or gated.jev_used
        # 8. Answer
        try:
            draft = await answer(rw.query, sources, deps.llm, s, model)
        except LLMUnavailable:
            return PipelineResult(
                "llm_unavailable",
                copy.TRY_AGAIN,
                sources=sources,
                keyword_only=keyword_only,
                **base,
            )

    # 9. Verify - always, no exceptions.
    verified = await verify_answer(
        draft.text,
        sources,
        deps.store,
        deps.decisions,
        is_upload_chat=request.is_upload_chat,
    )

    # 10. Show
    records = {}
    for c in verified.citations:
        record = await deps.store.get_record(c.record_id)
        if record is not None:
            records[c.record_id] = record
    final = show(verified, records, s, safety=decision.safety)

    # 11. Save
    message_id = await save(
        request,
        rw,
        decision,
        sources,
        draft,
        verified,
        final,
        deps.repo,
        deps.cache,
        lookup.key,
        s,
        from_cache=lookup.hit,
        jev_used=jev_used,
    )
    return PipelineResult(
        "answered",
        final=final,
        sources=sources,
        from_cache=lookup.hit,
        keyword_only=keyword_only,
        saved_message_id=message_id,
        **base,
    )
