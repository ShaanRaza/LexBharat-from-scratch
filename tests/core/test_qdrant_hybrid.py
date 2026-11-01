"""QdrantStore hybrid search, against a fake client (no live Qdrant, no fastembed).

What is checked: one call carrying a dense and a sparse prefetch merged by RRF; the
keyword half uses the QUERY-side encoder; named sections / case numbers skip the merge;
Voyage down runs the keyword half alone; language_code filters are refused.
"""

from types import SimpleNamespace

import pytest

from adapters.qdrant import (
    DENSE_VECTOR,
    SPARSE_VECTOR,
    SUPREME_COURT,
    QdrantStore,
    VectorStoreUnavailable,
    english_supreme_court,
)
from core.settings import Settings


def _point(i, text="body"):
    return SimpleNamespace(id=i, score=0.5, payload={"chunk_id": f"c{i}", "text": text})


class FakeClient:
    def __init__(self, fail=False):
        self.queries, self.scrolls, self.fail = [], [], fail

    async def query_points(self, collection, **kw):
        if self.fail:
            raise RuntimeError("boom")
        self.queries.append((collection, kw))
        return SimpleNamespace(points=[_point(1), _point(2)])

    async def scroll(self, collection, **kw):
        self.scrolls.append((collection, kw))
        return [_point(3)], None


def _store(client, calls=None):
    def encode(text):
        if calls is not None:
            calls.append(text)
        return [7, 9], [1.5, 0.5]

    return QdrantStore(Settings(SEAL_KEY="k"), sparse_encoder=encode, client=client)


def _fields(flt):
    return {c.key: c.match.value for c in flt.must}


async def test_hybrid_is_one_call_dense_plus_sparse_merged_by_rrf():
    c, calls = FakeClient(), []
    hits = await _store(c, calls).search(
        "kanoon_v1", [0.1, 0.2], "bail", english_supreme_court(), 50
    )
    assert len(c.queries) == 1 and not c.scrolls
    _, kw = c.queries[0]
    assert [p.using for p in kw["prefetch"]] == [DENSE_VECTOR, SPARSE_VECTOR]
    assert kw["prefetch"][0].query == [0.1, 0.2]
    assert kw["prefetch"][1].query.indices == [7, 9]
    assert kw["query"].fusion.value == "rrf"
    assert kw["limit"] == 50 and all(p.limit == 50 for p in kw["prefetch"])
    # the court filter is inside BOTH halves, and is court, not language_code
    for p in kw["prefetch"]:
        assert _fields(p.filter) == {"court": SUPREME_COURT}
    assert calls == ["bail"]
    assert [h.record_id for h in hits] == ["c1", "c2"]


async def test_voyage_down_runs_keyword_half_alone():
    c = FakeClient()
    await _store(c).search("kanoon_v1", None, "bail", {}, 10)
    ((_, kw),) = c.queries
    assert [p.using for p in kw["prefetch"]] == [SPARSE_VECTOR]
    assert kw["query"].fusion.value == "rrf"


@pytest.mark.parametrize("key", ["section_number", "case_number"])
async def test_named_section_or_case_number_skips_the_merge(key):
    c, calls = FakeClient(), []
    await _store(c, calls).search("kanoon_v1", [0.1], "x", {key: "302"}, 50)
    ((_, kw),) = c.queries
    assert "prefetch" not in kw and kw["using"] == DENSE_VECTOR
    assert _fields(kw["query_filter"]) == {key: "302"}
    assert calls == []  # the keyword encoder is not even used


async def test_exact_lookup_without_vector_scrolls_by_filter():
    c = FakeClient()
    hits = await _store(c).search("kanoon_v1", None, "x", {"case_number": "1"}, 5)
    assert not c.queries and len(c.scrolls) == 1
    assert [h.record_id for h in hits] == ["c3"]


async def test_language_code_filter_is_refused():
    with pytest.raises(ValueError):
        await _store(FakeClient()).search(
            "kanoon_v1", [0.1], "x", {"language_code": "EN"}, 5
        )


async def test_client_failure_becomes_vector_store_unavailable():
    with pytest.raises(VectorStoreUnavailable):
        await _store(FakeClient(fail=True)).search("kanoon_v1", [0.1], "x", {}, 5)


async def test_uploads_collection_still_refused_on_law_search():
    s = Settings(SEAL_KEY="k")
    with pytest.raises(PermissionError):
        await _store(FakeClient()).search(
            s.QDRANT_UPLOADS_COLLECTION, [0.1], "x", {}, 5
        )


async def test_missing_fastembed_is_reported_not_swallowed(monkeypatch):
    import builtins

    real = builtins.__import__

    def deny(name, *a, **k):
        if name == "fastembed":
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", deny)
    store = QdrantStore(Settings(SEAL_KEY="k"), client=FakeClient())
    with pytest.raises(VectorStoreUnavailable, match="fastembed"):
        await store.search("kanoon_v1", [0.1], "x", {}, 5)
