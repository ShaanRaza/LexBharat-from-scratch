"""The ONE function that queries a user's uploaded documents (CLAUDE.md section 6).

Plain words: every upload search in the product goes through search_user_documents().
It refuses an empty user_id, passes the user_id to the store (which always filters on
it), and checks every returned hit again - so even a store bug cannot leak another
lawyer's client file. No other code may build an upload query; a test greps for that.
"""

from __future__ import annotations

from collections.abc import Sequence

from adapters.qdrant import Hit, VectorStore


async def search_user_documents(
    store: VectorStore,
    user_id: str,
    vector: Sequence[float] | None,
    text: str,
    document_ids: Sequence[str],
    limit: int,
) -> list[Hit]:
    if not user_id or not user_id.strip():
        raise PermissionError("user_id is required for upload queries")
    hits = await store.search_uploads(user_id, vector, text, document_ids, limit)
    safe = [h for h in hits if h.payload.get("user_id") == user_id]
    if len(safe) != len(hits):
        raise PermissionError("store returned another user's upload record")
    return safe
