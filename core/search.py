"""Step 5 - SEARCH: top 50 chunks.

Normal path: embed the query (Voyage), then one hybrid call (meaning + keyword merged
by Reciprocal Rank Fusion inside Qdrant). A named section or case number skips the merge
and goes to an exact payload filter. If Voyage is down we fall back to keyword-only and
say so (docs/UX-COPY.md "keyword results only").
"""

from __future__ import annotations

from adapters.qdrant import SearchFilters, VectorStore
from adapters.voyage import VoyageClient, VoyageUnavailable
from core.constants import SEARCH_TOP_K
from core.models import RewriteResult, SearchResult


async def search(
    rewrite: RewriteResult,
    filters: SearchFilters,
    voyage: VoyageClient,
    store: VectorStore,
    *,
    limit: int = SEARCH_TOP_K,
) -> SearchResult:
    if filters.is_exact_lookup():
        exact = await store.exact_lookup(filters, limit)
        if exact:
            return SearchResult(hits=tuple(exact), exact=True)
        # Nothing matched exactly: fall through to normal search, never invent a hit.

    # Year filters from the rewrite are only used for exact lookups above; in hybrid
    # search they would silently hide good results, so search with entity filters off.
    broad = SearchFilters(court=filters.court, source_type=filters.source_type)
    try:
        vector = await voyage.embed(rewrite.query)
    except VoyageUnavailable:
        hits = await store.search_keyword(rewrite.query, broad, limit)
        return SearchResult(hits=tuple(hits), keyword_only=True)
    hits = await store.search_hybrid(vector, rewrite.query, broad, limit)
    return SearchResult(hits=tuple(hits))
