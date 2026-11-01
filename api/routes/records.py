"""Read-only record routes: judgment view, Act section (public), stats (public), search."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api import notices
from api.deps import (
    CurrentUser,
    current_user,
    pipeline_dep,
    settings_dep,
    store_dep,
)
from api.errors import ApiError
from api.pipeline import ResearchPipeline
from api.schemas import (
    ActSectionOut,
    CaseOut,
    InForceStatus,
    SearchOut,
    StatsOut,
)
from api.store import Store
from core.settings import Settings

router = APIRouter(tags=["records"])

# Supreme Court only until Phase 2 (docs/API.md). The value is how the corpus names it.
STATS_COURT_DEFAULT = "Supreme Court of India"


def split_paragraphs(full_text: str | None) -> list[dict]:
    """Cut a judgment into paragraphs with anchors p1, p2, ... so a citation link can
    jump to one (`/cases/<id>#p12`). Blank line = paragraph break."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", full_text or "") if p.strip()]
    return [{"anchor": f"p{i}", "text": p} for i, p in enumerate(parts, start=1)]


@router.get("/cases/{record_id}", response_model=CaseOut, summary="Full judgment")
async def get_case(
    *,
    record_id: str,
    _: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    case = await store.get_case(record_id)
    if case is None:
        raise ApiError(404, "not_found", "No record with that ID in the dataset.")
    as_of = await store.data_as_of(case["court"])
    return CaseOut(
        record_id=case["record_id"],
        title=case["title"],
        court=case["court"],
        decision_date=case["decision_date"],
        case_number=case["case_number"],
        citation=case["citation"],
        # A stored citation string is shown exactly as recorded, never retyped.
        citation_label=notices.CITATION_AS_RECORDED if case["citation"] else None,
        disposition=case["disposition"],
        outcome_label=case["outcome_label"],
        pdf_url=case["pdf_url"],
        paragraphs=split_paragraphs(case["full_text"]),
        provenance=notices.provenance(settings, as_of),
    )


@router.get(
    "/acts/{act}/sections/{section}",
    response_model=ActSectionOut,
    summary="One Act section (public, no login)",
)
async def get_act_section(
    *,
    act: str,
    section: str,
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    row = await store.get_act_section(act, section)
    if row is None:
        raise ApiError(404, "not_found", "No such Act section in the dataset.")
    # In-force status is shown ONLY where act_status is filled (1,568 of 22,264 Acts).
    # Everything else is labelled "in-force status not checked" (CLAUDE.md section 6).
    if row["act_status"]:
        status = InForceStatus(
            checked=True,
            act_status=row["act_status"],
            in_force=row["in_force"],
            label=row["act_status"],
        )
    else:
        status = InForceStatus(checked=False, label=notices.IN_FORCE_UNCHECKED)
    as_of = await store.data_as_of(None)
    return ActSectionOut(
        record_id=row["record_id"],
        act_name=row["act_name"],
        act_year=row["act_year"],
        section_number=row["section_number"],
        section_title=row["section_title"],
        text=row["text"],
        status=status,
        source_url=row["source_url"],
        provenance=notices.provenance(settings, as_of),
    )


@router.get(
    "/stats", response_model=StatsOut, summary="Outcome counts (public, no login)"
)
async def get_stats(
    *,
    year: Annotated[int | None, Query(ge=1800, le=2100)] = None,
    court: str = STATS_COURT_DEFAULT,
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    # Two gates: the global switch, and this court's own `stats_live` flag. Both stay
    # OFF until the 50-judgment hand check passes (docs/TESTING.md).
    if not settings.FEATURE_STATS_LIVE or not await store.stats_live(court):
        raise ApiError(
            404, "stats_not_live", "Outcome statistics are not available yet."
        )
    rows = await store.case_stats(court, year)
    as_of = await store.data_as_of(court)
    return StatsOut(
        court=court,
        year=year,
        rows=rows,
        total=sum(r["count"] for r in rows),
        # Descriptive only: counts, never predictions or chances (CLAUDE.md section 6).
        description="Counts of how cases were decided. Descriptive only.",
        provenance=notices.provenance(settings, as_of),
    )


@router.get("/search", response_model=SearchOut, summary="Search, no AI answer")
async def search(
    *,
    q: Annotated[str, Query(min_length=2, max_length=500)],
    court: str | None = None,
    year: Annotated[int | None, Query(ge=1800, le=2100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    _: Annotated[CurrentUser, Depends(current_user)],
    pipeline: Annotated[ResearchPipeline, Depends(pipeline_dep)],
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    hits = await pipeline.search(
        query=q, filters={"court": court, "year": year}, limit=limit
    )
    as_of = await store.data_as_of(court)
    return SearchOut(
        items=[h.__dict__ for h in hits], provenance=notices.provenance(settings, as_of)
    )
