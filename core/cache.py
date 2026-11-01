"""Step 4 - Cache: exact match on (rewritten query + filters + model), 7 days.

Only answers that passed verification are cached; upload chats never are. A cached
answer is stored with its seal and re-checked with is_sealed() when read back, so a
tampered or stale-key entry is a miss, not an answer."""

from __future__ import annotations

import dataclasses
import json

from adapters.cache import cache_key
from core.contracts import (
    Citation,
    Decision,
    Deps,
    Footer,
    PipelineRequest,
    PipelineResult,
    RemovedCitation,
    RewrittenQuery,
    VerifiedAnswer,
    is_sealed,
)


def key_for(rq: RewrittenQuery, decision: Decision, model: str) -> str:
    f = json.dumps(dataclasses.asdict(decision.filters), sort_keys=True)
    return cache_key(rq.query, f, model)


def dump_result(result: PipelineResult) -> str:
    a = result.answer
    if a is None:
        raise ValueError("only answered results are cached")
    d = {
        "text": a.text,
        "seal": a._seal.hex(),
        "citations": [dataclasses.asdict(c) for c in a.citations],
        "removed": [dataclasses.asdict(r) for r in a.removed],
        "confidence": result.confidence,
        "model": result.model,
        "personal": result.footer.personal_advice_flag,
    }
    return json.dumps(d)


def load_result(raw: str, footer: Footer) -> PipelineResult | None:
    try:
        d = json.loads(raw)
        ans = VerifiedAnswer(
            d["text"],
            tuple(Citation(**c) for c in d["citations"]),
            tuple(RemovedCitation(**r) for r in d["removed"]),
            _seal=bytes.fromhex(d["seal"]),
        )
        if not is_sealed(ans):
            return None
        footer = dataclasses.replace(footer, personal_advice_flag=d["personal"])
        return PipelineResult(
            "answered",
            ans,
            footer,
            confidence=d["confidence"],
            cache_hit=True,
            model=d["model"],
        )
    except (ValueError, KeyError, TypeError):
        return None


async def cache_lookup(
    request: PipelineRequest, key: str, footer: Footer, deps: Deps
) -> PipelineResult | None:
    if request.document_ids:
        return None
    raw = await deps.cache.get(key)
    return load_result(raw, footer) if raw else None


async def cache_store(
    request: PipelineRequest, key: str, result: PipelineResult, deps: Deps
) -> None:
    if request.document_ids or result.outcome != "answered":
        return
    await deps.cache.set(key, dump_result(result), deps.settings.ANSWER_CACHE_TTL_DAYS)
