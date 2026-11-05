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


async def delete_user_document_vectors(
    store: VectorStore, user_id: str, document_id: str
) -> None:
    """Hard delete of one document's vectors. Needs BOTH ids (the store filters on
    both), so deleting by document_id alone cannot touch another user's file."""
    if not user_id or not user_id.strip() or not document_id or not document_id.strip():
        raise PermissionError("user_id and document_id are required")
    await store.delete_upload_vectors(user_id, document_id)


async def count_user_document_vectors(
    store: VectorStore, user_id: str, document_id: str
) -> int:
    """How many vectors a document still has: the leftover check."""
    if not user_id or not user_id.strip() or not document_id or not document_id.strip():
        raise PermissionError("user_id and document_id are required")
    return await store.count_upload_vectors(user_id, document_id)
