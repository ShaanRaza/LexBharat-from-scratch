"""Known-item retrieval (decision A100): scoring, the three modes, the slice and the
query builders, all with scripted retrievers and fakes (no Qdrant, no keys)."""

import json

import pytest

from adapters.qdrant import FakeVectorStore
from adapters.voyage import FakeEmbedder
from core.settings import Settings, UnknownEmbeddingModel
from evals.known_item import (
    Chunk,
    Slice,
    build_queries,
    first_words,
    middle_sentence,
    paraphrased,
    rank_of,
    render_table,
    run_known_item,
    sample_chunks,
    score,
    store_retriever,
    to_json,
    wilson,
)

CHUNKS = [Chunk(f"c{i}", f"Chunk number {i}. " * 10) for i in range(20)]


def at_rank(rank: int, target_of):
    """A retriever that returns 50 ids with the target at the given 1-based place."""

    async def retrieve(query, mode):
        target = target_of(query)
        others = [f"other{i}" for i in range(50)]
        others.insert(rank - 1, target)
        return others[:50]

    return retrieve


def target_of(query: str) -> str:
    return "c" + query.split()[2].rstrip(".")


async def test_a_perfect_retriever_scores_one():
    async def retrieve(query, mode):
        return [target_of(query), "x"]

    res = await run_known_item(CHUNKS, middle_sentence(), retrieve)
    for mode in ("dense", "sparse", "hybrid"):
        m = res[mode].metrics
        assert m.recall == {10: 1.0, 50: 1.0} and m.mrr == 1.0 and m.not_found == 0


async def test_a_retriever_that_returns_nothing_scores_zero():
    async def retrieve(query, mode):
        return []

    res = await run_known_item(CHUNKS, middle_sentence(), retrieve)
    m = res["hybrid"].metrics
    assert m.recall == {10: 0.0, 50: 0.0} and m.mrr == 0.0 and m.not_found == 20


async def test_rank_37_counts_for_recall_at_50_and_not_at_10():
    res = await run_known_item(CHUNKS, middle_sentence(), at_rank(37, target_of))
    m = res["dense"].metrics
    assert m.recall[10] == 0.0 and m.recall[50] == 1.0
    assert m.mrr == pytest.approx(1 / 37)
    assert set(res["dense"].ranks.values()) == {37}


def test_the_boundaries_of_the_cutoffs():
    m = score([10, 11, 50, None])
    assert m.recall == {10: 0.25, 50: 0.75} and m.not_found == 1
    assert m.mrr == pytest.approx((1 / 10 + 1 / 11 + 1 / 50) / 4)
    assert rank_of("a", ["b", "a"]) == 2 and rank_of("z", ["b", "a"]) is None
    with pytest.raises(ValueError):
        score([])


def test_the_interval_brackets_the_share_and_stays_inside_zero_to_one():
    lo, hi = wilson(190, 200)
    assert lo < 0.95 < hi and 0 <= lo and hi <= 1
    assert wilson(0, 0) == (0.0, 0.0) and wilson(200, 200)[1] == 1.0


async def test_each_mode_is_asked_in_its_own_mode_and_scored_apart():
    """Dense finds half, sparse all, hybrid none: three different numbers."""
    seen = []

    async def retrieve(query, mode):
        seen.append(mode)
        t = target_of(query)
        n = int(t[1:])
        if mode == "sparse" or (mode == "dense" and n % 2 == 0):
            return [t]
        return []

    res = await run_known_item(CHUNKS, first_words(5), retrieve)
    assert {r: res[r].metrics.recall[50] for r in res} == {
        "dense": 0.5,
        "sparse": 1.0,
        "hybrid": 0.0,
    }
    assert set(seen) == {"dense", "sparse", "hybrid"}
    only = await run_known_item(CHUNKS, first_words(5), retrieve, modes=("sparse",))
    assert list(only) == ["sparse"]


async def test_a_mode_that_cannot_run_is_reported_and_the_others_still_run():
    async def retrieve(query, mode):
        if mode != "sparse":
            raise UnknownEmbeddingModel("no model recorded for this collection")
        return [target_of(query)]

    res = await run_known_item(CHUNKS, first_words(5), retrieve)
    assert res["dense"].metrics is None and "no model recorded" in res["dense"].error
    assert res["sparse"].metrics.recall[50] == 1.0
    assert "could not run" in render_table(res)


async def test_a_real_bug_is_not_swallowed_as_a_mode_error():
    async def retrieve(query, mode):
        raise KeyError("bug")

    with pytest.raises(KeyError):
        await run_known_item(CHUNKS, first_words(5), retrieve)


async def test_an_empty_slice_is_an_error_not_a_zero():
    with pytest.raises(ValueError):
        await run_known_item([], first_words(5), at_rank(1, target_of))


async def test_query_builders_are_swappable_and_async_ones_work():
    c = Chunk(
        "c1",
        "Short. This is a much longer middle sentence with many words in it. "
        "Another fairly long sentence follows right after the middle one here. "
        "A third lengthy sentence closes the passage with enough words.",
    )
    assert first_words(3)(c) == "Short. This is"
    assert middle_sentence()(c).startswith("Another fairly long sentence")
    assert middle_sentence()(Chunk("x", "tiny text")) == "tiny text"  # fallback

    async def shout(text):
        return text.upper()

    qs = await build_queries([c], paraphrased(shout))
    assert qs == [middle_sentence()(c).upper()]
    assert await build_queries([c], first_words(2)) == ["Short. This"]


def _store(n=12):
    s = Settings(SEAL_KEY="k")  # type: ignore[arg-type]
    store = FakeVectorStore(s)
    for i in range(n):
        court = "A" if i < 6 else "B"
        store.add_law(
            f"r{i:02d}",
            f"The matter number {i} concerns the unique doctrine word{i} in detail "
            f"and the court held that doctrine{i} applies here to the facts at hand.",
            court=court,
        )
    return s, store


async def test_the_slice_limits_by_payload_and_by_id_range():
    s, store = _store()
    a = await sample_chunks(store, Slice(s.CORPUS_COLLECTION, {"court": "A"}), 50)
    assert len(a) == 6 and all(int(c.record_id[1:]) < 6 for c in a)
    r = await sample_chunks(
        store, Slice(s.CORPUS_COLLECTION, id_from="r03", id_to="r05"), 50
    )
    assert sorted(c.record_id for c in r) == ["r03", "r04", "r05"]
    assert len(await sample_chunks(store, Slice(s.CORPUS_COLLECTION), 4)) == 4


def test_a_slice_cannot_use_the_exact_lookup_keys():
    with pytest.raises(ValueError, match="exact-lookup"):
        Slice("c", {"case_number": "1"}).must()


async def test_end_to_end_through_the_real_adapter_interface_with_fakes():
    s, store = _store()
    sl = Slice(s.CORPUS_COLLECTION, {"court": "B"})
    chunks = await sample_chunks(store, sl, 6)
    retrieve = store_retriever(store, FakeEmbedder(), s.CORPUS_COLLECTION, sl.must())
    res = await run_known_item(chunks, first_words(12), retrieve)
    assert res["hybrid"].metrics.n == 6 and res["hybrid"].metrics.recall[50] == 1.0


async def test_the_dense_half_is_never_run_without_a_vector():
    """A down embedder fails the run; it must not quietly become keyword-only."""
    from adapters.voyage import VoyageUnavailable

    s, store = _store()
    chunks = await sample_chunks(store, Slice(s.CORPUS_COLLECTION), 3)
    retrieve = store_retriever(store, FakeEmbedder(down=True), s.CORPUS_COLLECTION)
    res = await run_known_item(chunks, first_words(8), retrieve)
    assert VoyageUnavailable.__name__ in res["dense"].error
    assert VoyageUnavailable.__name__ in res["hybrid"].error
    assert res["sparse"].metrics.recall[50] == 1.0


async def test_the_json_is_machine_readable_and_carries_no_text():
    res = await run_known_item(CHUNKS, middle_sentence(), at_rank(37, target_of))
    doc = json.loads(json.dumps(to_json(res, {"strategy": "middle_sentence"})))
    h = doc["modes"]["hybrid"]
    assert h["recall@10"] == 0.0 and h["recall@50"] == 1.0 and h["n"] == 20
    assert h["recall@50_ci95"][0] < 1.0 and len(h["ranks"]) == 20
    assert "Chunk number" not in json.dumps(doc)  # ids and numbers only


async def test_the_table_lists_all_three_modes_side_by_side():
    res = await run_known_item(CHUNKS, middle_sentence(), at_rank(37, target_of))
    t = render_table(res).splitlines()
    assert "recall@10" in t[0] and "recall@50" in t[0] and "MRR" in t[0]
    assert [row.split()[0] for row in t[2:]] == ["dense", "sparse", "hybrid"]
