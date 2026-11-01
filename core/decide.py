"""Step 3 - DECIDE (Jev): scope check, safety check, filters, knowledge notes.

Out-of-scope or a "trick" request stops the pipeline here (no search, no writing cost).
Filters are built from the entities step 2 pulled out - plain Python, no Jev call.
"""

from __future__ import annotations

from adapters.jev import DecisionAdapter, DecisionUnavailable
from adapters.qdrant import SearchFilters
from core.models import DecideResult, RewriteResult


async def decide(
    rewrite: RewriteResult,
    decisions: DecisionAdapter,
    *,
    is_upload_chat: bool = False,
) -> DecideResult:
    filters = SearchFilters(
        act_name=rewrite.act_name,
        section_number=rewrite.section,
        case_number=rewrite.case_number,
        year_from=rewrite.year,
        year_to=rewrite.year,
    )
    try:
        scope = await decisions.scope(
            rewrite.query, contains_upload_text=is_upload_chat
        )
        safety = await decisions.safety(
            rewrite.query, contains_upload_text=is_upload_chat
        )
    except DecisionUnavailable:
        # Both Jev and the fallback are down. Search is still protected by the gate and
        # the verifier, so carry on with plain defaults and say so (degraded=True).
        return DecideResult("in_scope", "normal", filters, degraded=True)
    return DecideResult(
        scope=scope.choice,
        safety=safety.choice,
        filters=filters,
        jev_used="jev" in (scope.source, safety.source),
    )
