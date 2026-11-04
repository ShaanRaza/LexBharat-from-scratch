"""The per-court embedding health check (scan/embedding_health.py). Pipeline step 5 (Search) measurement code; nothing here
changes behaviour.

What these pin down: the three-way reading of a re-embed cosine (and that the lines sit where the measured populations
leave a gap), the sample allocation, that the script can only READ the originals, and that the one stage that spends Voyage
tokens will not start without --go or over its cap. The real figures come from the real data; these use tiny synthetic arrays.
"""

from __future__ import annotations

import numpy as np
import pytest

from scan import embedding_health as eh


def test_classify_separates_the_three_measured_populations():
    # voyage-4's own vectors reproduce at 1.000; identified lite/large chunks sit at 0.672-0.972; dead Kerala vectors at -0.138..0.133
    cos = np.array([1.0, 0.9995, 0.99, 0.972, 0.672, 0.6, 0.51, 0.133, 0.0, -0.138])
    got = eh.classify(cos).tolist()
    assert got == [0, 0, 0, 1, 1, 3, 3, 2, 2, 2]


def test_the_lines_leave_the_observed_gap_open_on_both_sides():
    assert (
        eh.DEAD_MAX_OBSERVED
        < eh.UNRELATED_BELOW
        < eh.OTHER_MODEL_MIN_OBSERVED
        < eh.SAME
    )


def test_wilson_interval_of_a_clean_court_is_not_zero_width():
    lo, hi = eh.wilson(0, 1100)
    assert (
        lo == 0.0 and 0.003 < hi < 0.004
    )  # about 3.5 in a thousand, so a clean sample still bounds the count
    lo, hi = eh.wilson(77, 1100)
    assert lo < 0.07 < hi
    assert eh.wilson(0, 0) == (0.0, 1.0)


def test_length_bands_are_half_open_and_cover_everything():
    assert [
        eh.length_band(x) for x in (0, 499, 500, 1499, 1500, 2999, 3000, 10**7)
    ] == [0, 0, 1, 1, 2, 2, 3, 3]


def test_allocation_reads_a_small_group_whole_and_gives_big_ones_more():
    sizes = {
        ("legal_corpus_v1", "A"): 2_000_000,
        ("legal_corpus_v1", "B"): 500_000,
        ("legal_corpus_v2", "C"): 5,
        ("legal_corpus_v2", "D"): 1050,
    }
    q = eh.allocate(sizes)
    assert q[("legal_corpus_v1", "A")] == eh.QUOTA_BIG
    assert q[("legal_corpus_v1", "B")] == eh.QUOTA_SMALL
    assert q[("legal_corpus_v2", "C")] == 5
    assert q[("legal_corpus_v2", "D")] == 1050


def test_cosine_rows_is_one_for_equal_rows_and_scale_free():
    a = np.random.default_rng(1).normal(size=(5, 8))
    assert np.allclose(eh.cosine_rows(a, a * 3), 1.0)


def test_only_reads_of_the_two_originals_are_allowed():
    for path in (
        "/collections/legal_corpus_v1/points/scroll",
        "/collections/legal_corpus_v2/points",
        "/collections/legal_corpus_v1/points/count",
    ):
        assert eh._READ_PATHS.match(path)
    for path in (
        "/collections/legal_corpus_v1",  # a collection call
        "/collections/kanoon_v1/points/scroll",  # not one of the two originals
        "/collections/legal_corpus_v1/points/delete",
        "/collections/legal_corpus_v2/points/vectors",
        "/collections/legal_corpus_v1/snapshots",
        "/collections/acts_india/points/scroll",
    ):
        assert not eh._READ_PATHS.match(path)
    with pytest.raises(PermissionError):
        eh.orig_read("/collections/legal_corpus_v1/points/delete", {})


def test_embed_will_not_start_without_go(tmp_path, monkeypatch):
    monkeypatch.setattr(eh, "HOME", tmp_path)
    with pytest.raises(SystemExit) as e:
        eh.cmd_embed(go=False)
    assert "--go" in str(e.value)


def test_embed_refuses_a_priced_sample_over_the_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(eh, "HOME", tmp_path)
    (tmp_path / "price.json").write_text('{"within_cap": false}')
    with pytest.raises(SystemExit) as e:
        eh.cmd_embed(go=True)
    assert "over the cap" in str(e.value)


def test_the_cap_is_six_dollars_of_voyage_4_tokens():
    assert eh.CAP_TOKENS == 100_000_000
    assert eh.price_usd(eh.CAP_TOKENS) == pytest.approx(6.0)
    assert eh.price_usd(1_000_000, batch=True) == pytest.approx(0.06 * 0.67)


def test_ledger_tokens_counts_only_this_jobs_tags(tmp_path, monkeypatch):
    led = tmp_path / "l.jsonl"
    led.write_text(
        '{"t":1,"model":"voyage-4","tokens":100,"tag":"health:v1_HCBM"}\n'
        '{"t":2,"model":"voyage-4","tokens":7,"tag":"kerala batch 3"}\n'
        '{"t":3,"model":"voyage-4","tokens":5,"tag":"health:preflight"}\n'
    )
    monkeypatch.setattr(eh, "LEDGER", led)
    assert eh.ledger_tokens() == 105
