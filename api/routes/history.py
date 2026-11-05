"""History and search across the user's OWN saved work (PRD-v2 section 4.2).

PostgreSQL full text, no new vendor. Always through core/user_search.py, which filters
on user_id and checks every row again."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from api import schemas as s
from api.auth import CurrentUser, User
from core.user_search import search_my_work

router = APIRouter()


@router.get("/history/search", response_model=s.HistorySearch)
async def search_history(
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=50),
    user: CurrentUser = User,
):
    rows = await search_my_work(request.app.state.repo, user.id, q, limit)
    return s.HistorySearch(items=rows)
