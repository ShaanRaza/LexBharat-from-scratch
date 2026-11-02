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


# --- the three options added for the model comparison (A100) --------------------------

from pathlib import Path  # noqa: E402

from adapters.voyage import VoyageClient  # noqa: E402
from evals.known_item import (  # noqa: E402
    BudgetedEmbedder,
    BudgetExceeded,
    _main,
    _sample_deps,
    builder_for,
    load_paraphraser,
    make_parser,
    read_ids,
    with_query_model,
)


def _args(*argv):
    return make_parser().parse_args(list(argv))


# 1. --strategy paraphrased, with the model call handed in


async def test_paraphrased_uses_the_function_it_is_handed_and_nothing_else():
    calls = []

    async def fake_model(sentence):
        calls.append(sentence)
        return "REWRITTEN " + sentence

    build = builder_for("paraphrased", fake_model)
    c = Chunk("c1", "One long enough sentence to be chosen as the query here.")
    (q,) = await build_queries([c], build)
    assert q.startswith("REWRITTEN ") and calls == [q.removeprefix("REWRITTEN ")]


def test_paraphrased_without_a_model_call_is_refused_not_faked():
    with pytest.raises(SystemExit, match="--paraphraser"):
        builder_for("paraphrased")


def test_the_paraphraser_is_loaded_by_name_and_must_be_async():
    fn = load_paraphraser("evals.known_item:_stub_paraphrase")
    assert fn.__name__ == "_stub_paraphrase"
    with pytest.raises(SystemExit, match="async"):
        load_paraphraser("os.path:join")
    with pytest.raises(SystemExit, match="package.module:function"):
        load_paraphraser("nonsense")


def test_the_eval_module_imports_no_model_or_vendor_library():
    src = Path("evals/known_item.py").read_text()
    for banned in ("import litellm", "import openai", "import anthropic", "genai"):
        assert banned not in src


# 2. --query-model: the override exists in the measurement path and nowhere else


class _Capture(VoyageClient):
    def __init__(self, settings):
        super().__init__(settings)
        self.models = []

    async def _post(self, path, body):
        self.models.append(body["model"])
        return {"data": [{"embedding": [0.0]}]}


async def test_the_override_names_the_model_for_the_measurement_embedder_only():
    base = Settings(SEAL_KEY="k")  # type: ignore[arg-type]
    other = "legal_corpus_v1"  # a collection nobody recorded a model for
    # without the override, the refusal (A120) holds
    with pytest.raises(UnknownEmbeddingModel):
        await _Capture(base).embed("q", other)
    # with it, the measurement embedder sends the model it was told to
    over = with_query_model(base, other, "voyage-4")
    c = _Capture(over)
    await c.embed("q", other)
    assert c.models == ["voyage-4"]
    await _Capture(with_query_model(base, other, "voyage-4-large")).embed("q", other)


def test_the_override_leaves_the_original_settings_and_the_refusal_untouched():
    base = Settings(SEAL_KEY="k")  # type: ignore[arg-type]
    before = dict(base.VOYAGE_EMBED_MODELS)
    over = with_query_model(base, "legal_corpus_v1", "voyage-4")
    assert over is not base and over.embed_model_for("legal_corpus_v1") == "voyage-4"
    assert base.VOYAGE_EMBED_MODELS == before
    with pytest.raises(UnknownEmbeddingModel):
        base.embed_model_for("legal_corpus_v1")
    # a recorded collection is not changed for anyone else either
    assert base.embed_model_for("kanoon_v1") == before["kanoon_v1"]
    with pytest.raises(ValueError):
        with_query_model(base, "x", "  ")


def test_nothing_outside_evals_can_reach_the_override():
    """The override is defined and used only under evals/. core/, adapters/, api/ and
    workers/ must neither define nor import it, so the live pipeline keeps A120."""
    for folder in ("core", "adapters", "api", "workers"):
        for path in Path(folder).rglob("*.py"):
            text = path.read_text()
            assert "with_query_model" not in text, path
            assert "evals.known_item" not in text, path
            assert "query_model" not in text.lower().replace("embed_model", ""), path
    from core.settings import Settings as S

    assert not hasattr(S, "with_query_model") and not hasattr(S, "QUERY_MODEL")


async def test_the_cli_override_does_not_change_the_global_settings(tmp_path):
    from core.settings import get_settings

    before = dict(get_settings().VOYAGE_EMBED_MODELS)
    a = _args("--sample", "--n", "5", "--query-model", "voyage-4")
    assert await _main(a) == 0
    assert get_settings().VOYAGE_EMBED_MODELS == before


# 3. --ids-file


def test_ids_can_come_from_json_a_wrapped_list_or_plain_lines(tmp_path):
    (tmp_path / "a.json").write_text('["x", "y", "x"]')
    (tmp_path / "b.json").write_text('{"ids": ["p", "q"]}')
    (tmp_path / "c.txt").write_text("# confirmed voyage-4\nm\n\n n \nm\n")
    assert read_ids(tmp_path / "a.json") == ["x", "y"]  # order kept, repeat dropped
    assert read_ids(tmp_path / "b.json") == ["p", "q"]
    assert read_ids(tmp_path / "c.txt") == ["m", "n"]


def test_bad_or_empty_id_files_are_errors(tmp_path):
    (tmp_path / "e.txt").write_text("# nothing\n")
    (tmp_path / "n.json").write_text("[1, 2]")
    (tmp_path / "o.json").write_text('{"ids": "oops"}')
    for name in ("e.txt", "n.json", "o.json"):
        with pytest.raises(ValueError):
            read_ids(tmp_path / name)


async def test_an_id_list_measures_exactly_those_chunks_and_is_recorded(tmp_path):
    _, store, _ = await _sample_deps()
    ids = [h.record_id for h in store.law[10:15]]
    (tmp_path / "ids.txt").write_text("\n".join(ids))
    out = tmp_path / "r.json"
    a = _args("--sample", "--ids-file", str(tmp_path / "ids.txt"), "--out", str(out))
    assert await _main(a) == 0
    doc = json.loads(out.read_text())
    assert set(doc["modes"]["hybrid"]["ranks"]) == set(ids)
    assert doc["meta"]["ids_given"] == 5 and doc["meta"]["n_measured"] == 5
    assert doc["meta"]["ids_file"] == "ids.txt"


async def test_ids_that_are_not_found_are_counted_not_hidden(tmp_path, capsys):
    _, store, _ = await _sample_deps()
    ids = [store.law[0].record_id, "no-such-chunk"]
    (tmp_path / "ids.txt").write_text("\n".join(ids))
    out = tmp_path / "r.json"
    await _main(_args("--sample", "--ids-file", str(tmp_path / "ids.txt"),
                      "--out", str(out)))  # fmt: skip
    meta = json.loads(out.read_text())["meta"]
    assert meta["ids_given"] == 2 and meta["n_measured"] == 1
    assert "1 of 2 ids not found" in capsys.readouterr().out


def test_ids_file_and_replay_cannot_be_combined():
    with pytest.raises(SystemExit):
        _args("--ids-file", "a.txt", "--replay", "b.json")


# the spend cap


async def test_the_token_cap_stops_the_run_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "r.json"
    rc = await _main(_args("--sample", "--n", "20", "--max-voyage-tokens", "10",
                           "--out", str(out)))  # fmt: skip
    assert rc == 2 and not out.exists() and "STOPPED" in capsys.readouterr().out


async def test_the_budget_counts_every_embed_call_and_reports_an_estimate():
    class Inner:
        async def embed(self, text, collection):
            return [0.0]

    b = BudgetedEmbedder(Inner(), 20)
    await b.embed("x" * 40, "c")  # ~10 tokens
    assert b.tokens == 10
    with pytest.raises(BudgetExceeded):
        await b.embed("y" * 80, "c")
    unlimited = BudgetedEmbedder(Inner(), None)
    await unlimited.embed("z" * 4000, "c")
    assert unlimited.tokens == 1000


async def test_paraphrased_runs_from_the_command_line_with_the_demo_stub(tmp_path):
    out = tmp_path / "r.json"
    assert await _main(_args("--sample", "--n", "8", "--strategy", "paraphrased",
                             "--out", str(out))) == 0  # fmt: skip
    assert json.loads(out.read_text())["meta"]["strategy"] == "paraphrased"
