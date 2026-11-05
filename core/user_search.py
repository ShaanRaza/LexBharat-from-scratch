"""The ONE function that searches a user's own saved work (history and search).

Plain words: every search over conversations and answers goes through search_my_work().
It refuses an empty user_id, passes the user_id to the repository (whose query always
filters on it), and checks every returned row again, so even a repository bug cannot
return another user's row. Nothing else may call the repository's search; a test greps
for that. Same pattern as core/uploads.py. Not a pipeline step."""

from __future__ import annotations

from typing import Any

MAX_QUERY = 200


async def search_my_work(
    repo: Any, user_id: str, query: str, limit: int = 20
) -> list[dict]:
    if not user_id or not user_id.strip():
        raise PermissionError("user_id is required to search saved work")
    q = " ".join(query.split())[:MAX_QUERY]
    if not q:
        return []
    rows = await repo.search_user_work(user_id, q, min(max(limit, 1), 50))
    safe = [r for r in rows if str(r.get("user_id")) == str(user_id)]
    if len(safe) != len(rows):
        raise PermissionError("repository returned another user's row")
    return safe
