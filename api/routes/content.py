"""Cases, Acts, search, stats. Acts and stats are PUBLIC (no login)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from api import schemas as s
from api.auth import CurrentUser, User
from api.errors import ApiError

router = APIRouter()


async def _prov(request: Request) -> s.Provenance:
    cov = await request.app.state.repo.data_as_of()
    if not cov:
        raise ApiError(503, "service_unavailable", "Data is not loaded yet.")
    return s.Provenance(
        data_as_of=cov[0],
        snapshot_version=cov[1],
        credit=request.app.state.core_settings.DATA_CREDIT,
    )


@router.get("/cases/{record_id}", response_model=s.CaseOut)
async def get_case(record_id: str, request: Request, user: CurrentUser = User):
    case = await request.app.state.repo.get_case(record_id)
    if case is None:
        raise ApiError(404, "not_found", "Judgment not found.")
    # Only listed fields: no judges, no party names (unreliable in the dataset).
    return s.CaseOut(
        record_id=case["record_id"], title=None,  # parties: never shown
         court=case.get("court"),
        decision_date=case.get("decision_date"), case_number=case.get("case_number"),
        citation_string=case.get("citation_string"), url=case.get("url"),
        paragraphs=case["paragraphs"], provenance=await _prov(request),
    )  # fmt: skip


@router.get("/acts/{act}/sections/{n}", response_model=s.SectionOut)
async def get_section(act: str, n: str, request: Request):
    sec = await request.app.state.repo.get_section(act, n)
    if sec is None:
        raise ApiError(404, "not_found", "Section not found.")
    return s.SectionOut(
        act_slug=act, act_name=sec["act_name"], act_year=sec.get("act_year"),
        section=sec["section"], section_title=sec.get("section_title"),
        text=sec["text"] or "", source_url=sec.get("source_url"),
        in_force=sec["in_force"] if sec["act_status_checked"] else None,
        act_status_checked=sec["act_status_checked"], provenance=await _prov(request),
    )  # fmt: skip


@router.get("/stats", response_model=s.StatsResponse)
async def stats(request: Request):
    rows, live = await request.app.state.repo.stats()
    # Gated by the FEATURE_STATS_LIVE switch (hand check must pass first).
    if not request.app.state.core_settings.FEATURE_STATS_LIVE:
        rows, live = [], False
    return s.StatsResponse(rows=rows, live=live, provenance=await _prov(request))


@router.get("/search", response_model=s.SearchResponse)
async def search(
    q: str = Query(min_length=1), user: CurrentUser = User
) -> s.SearchResponse:
    # Direct search needs the vector store + reranker (core). Wired with the bridge.
    raise ApiError(501, "feature_disabled", "Direct search is not built yet.")
