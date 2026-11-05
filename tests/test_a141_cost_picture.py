"""The A141 cost-picture measurements (scan/missing_set.py, scan/missing_tokens.py, evals/a141/*). Pipeline step 5 (Search)
measurement code; nothing here changes behaviour.

What these pin down: the per-court aggregation (whole cases, chunks per case, by year), that nothing can be written to an
original or to a collection the script did not make, and that the one script that spends Voyage tokens will not start
without an explicit --go. The real figures come from the real data (DATA-GAPS section 19 and the A141 cost document); these
tests use tiny synthetic arrays.
"""

from __future__ import annotations

import numpy as np
import pytest

from evals.a141 import load_cost, model_choice, sparse_only_sim
from scan import missing_set as ms
from scan import missing_tokens as mt


def _arrays():
    # court 0: case A has 3 chunks (year 2020), case B has 1 chunk (2015), one chunk id appears twice (counted once)
    # court 1: case C has 2 chunks (year 2019)
    chash = np.array([1, 2, 3, 4, 4, 5, 6], dtype=np.uint64)
    cash = np.array([10, 10, 10, 20, 20, 30, 30], dtype=np.uint64)
    code = np.array([0, 0, 0, 0, 0, 1, 1], dtype=np.int8)
    chars = np.array([100, 200, 300, 50, 50, 400, 600], dtype=np.int32)
    year = np.array([2020, 2020, 2020, 2015, 2015, 2019, 2019], dtype=np.int16)
    return chash, cash, code, chars, year


def test_aggregate_counts_cases_chunks_and_a_repeated_chunk_id_once():
    a = ms.aggregate(*_arrays())
    assert a[0]["cases"] == 2 and a[0]["chunks"] == 4 and a[0]["chars"] == 650
    assert a[1]["cases"] == 1 and a[1]["chunks"] == 2 and a[1]["chars"] == 1000
    assert a[0]["chunks_per_case_mean"] == pytest.approx(2.0)
    assert a[0]["chunks_per_case_max"] == 3
    assert (
        a[0]["chunks_per_case_hist"]["1"] == 1
        and a[0]["chunks_per_case_hist"]["3"] == 1
    )
    assert a[1]["chunks_per_case_hist"]["2"] == 1


def test_aggregate_by_year_gives_cases_chunks_and_size_per_year():
    a = ms.aggregate(*_arrays())
    assert a[0]["by_year"] == {2015: [1, 1, 50], 2020: [1, 3, 600]}
    assert a[1]["by_year"] == {2019: [1, 2, 1000]}


def test_the_histogram_covers_every_case_exactly_once():
    chash = np.arange(1, 40, dtype=np.uint64)
    cash = np.repeat(np.arange(1, 14, dtype=np.uint64), 3)[:39]  # 13 cases of 3 chunks
    cash[30:] = 99  # one case of 9 chunks
    a = ms.aggregate(
        chash,
        cash,
        np.zeros(39, np.int8),
        np.ones(39, np.int32),
        np.full(39, 2021, np.int16),
    )
    assert sum(a[0]["chunks_per_case_hist"].values()) == a[0]["cases"]


def test_the_copy_instance_reader_refuses_anything_but_scroll_and_count():
    for path in (
        "/collections/x/points/upsert",
        "/collections/x",
        "/collections/x/points/delete",
    ):
        with pytest.raises(SystemExit):
            ms.copy_post(path, {})


def test_the_local_token_count_is_one_less_per_text_than_the_tokenizer_returns():
    class Enc:
        def __init__(self, n):
            self.ids = list(range(n))

    class Tok:
        def encode_batch(self, texts):
            return [
                Enc(len(t.split()) + 1) for t in texts
            ]  # one special token per text, as the real one

    out = mt.count(Tok(), ["a b c", "d", "e f"])
    assert out.tolist() == [3, 1, 2]


@pytest.mark.parametrize(
    "mod, path",
    [
        (sparse_only_sim, "/collections/legal_corpus_v2/points/delete"),
        (sparse_only_sim, "/collections/kanoon_v1/points"),
        (model_choice, "/collections/kanoon_v1/points"),
        (model_choice, "/collections/a128_multicourt"),
        (load_cost, "/collections/kanoon_v1/points"),
        (load_cost, "/collections/a128_multicourt/points"),
    ],
)
def test_the_scratch_writers_refuse_to_write_anywhere_but_their_own_collections(
    mod, path, monkeypatch
):
    calls = []
    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    with pytest.raises(SystemExit):
        mod.call("PUT", path, {})
    assert calls == []  # refused before any request


def test_the_voyage_spending_stage_will_not_start_without_go(monkeypatch):
    monkeypatch.setattr("sys.argv", ["model_choice", "embed"])
    with pytest.raises(SystemExit) as e:
        model_choice.main()
    assert "--go" in str(e.value)


def test_each_dense_model_has_its_own_court_code_and_scratch_collection():
    assert set(model_choice.REP) == set(model_choice.COLL) == set(model_choice.PRICE)
    assert len(set(model_choice.COLL.values())) == 3
    assert not set(model_choice.COLL.values()) & {"kanoon_v1", "a128_multicourt"}


# --- data/voyage_token_count.py: the exact-price capability -----------------------------------------------
class _FakeTok:
    """One token per word plus ONE special token per text, like the real tokenizer (billed = local - 1)."""

    class _E:
        def __init__(self, n):
            self.ids = list(range(n))

    def encode_batch(self, texts):
        return [self._E(len(t.split()) + 1) for t in texts]


def test_billed_tokens_subtract_the_one_special_token_per_text():
    from data import voyage_token_count as v

    assert v.billed_tokens(["a b c", "d", ""], tokenizer=_FakeTok()) == [3, 1, 0]


def test_billed_tokens_handle_more_than_one_batch_of_texts():
    from data import voyage_token_count as v

    out = v.billed_tokens(["w"] * 2500, tokenizer=_FakeTok())
    assert len(out) == 2500 and set(out) == {1}


def test_price_is_list_price_and_batch_is_one_third_cheaper():
    from data import voyage_token_count as v

    assert v.price_usd(1_000_000, "voyage-4") == pytest.approx(0.06)
    assert v.price_usd(1_000_000, "voyage-4-lite", batch=True) == pytest.approx(0.0134)
    assert v.price_usd(5_594_712 // 3 * 3, "voyage-4-large") == pytest.approx(
        5_594_712 // 3 * 3 / 1e6 * 0.12
    )


def test_price_refuses_a_model_it_has_no_price_for():
    from data import voyage_token_count as v

    with pytest.raises(ValueError):
        v.price_usd(1000, "voyage-3-mystery")


# --- scan/missing_bands.py: the length bands the owner draws the line between ------------------------------------
def test_length_bands_put_each_case_in_exactly_one_band_and_the_totals_reconcile():
    from scan import missing_bands as mb

    chars = np.array([100, 249, 250, 499, 500, 999, 1000, 7999, 8000, 50000])
    tokens = np.array([30, 70, 80, 150, 160, 300, 310, 2000, 2100, 15000])
    chunks = np.array([1, 1, 1, 1, 1, 1, 1, 2, 3, 10])
    code = np.array([0, 0, 1, 1, 0, 0, 1, 1, 0, 0], dtype=np.int8)
    year = np.array(
        [2020, 2010, 2020, 2020, 2016, 2015, 2024, 2000, 2016, 2025], dtype=np.int16
    )
    rows = mb.band_table(chars, tokens, chunks, code, year, ["AA", "BB"], 2016)
    assert sum(r["cases"] for r in rows) == 10
    assert sum(r["tokens"] for r in rows) == int(tokens.sum())
    assert sum(r["chunks"] for r in rows) == int(chunks.sum())
    # the edges: 249 is in the first band, 250 in the second; 7999 below the open band, 8000 in it
    assert [r["cases"] for r in rows][:3] == [2, 2, 2] and rows[-1]["cases"] == 2
    assert rows[1]["band"] == "250-499 chars" and rows[-1]["band"] == "8,000+ chars"
    # drawing the line at the bottom of band 2 excludes exactly the cases in bands 0 and 1
    assert rows[2]["if_line_drawn_here_cases_excluded"] == 4
    assert rows[2]["if_line_drawn_here_cases_kept"] == 6
    assert rows[0]["if_line_drawn_here_cases_excluded"] == 0
    assert (
        rows[0]["recent_cases"] == 1
    )  # only the 100-char case is both in band 0 and from 2016 on


def test_band_prices_use_the_vendor_prices_and_the_batch_discount():
    from scan import missing_bands as mb

    p = mb.prices(1_000_000_000)
    assert p["voyage-4-lite standard"]["usd"] == pytest.approx(20.0)
    assert p["voyage-4 batch"]["usd"] == pytest.approx(60.0 * 0.67)
    assert p["voyage-4-lite batch"]["inr"] == pytest.approx(20.0 * 0.67 * mb.USD_INR)
