"""A126's dedup rule for the copy step (data/dedupe_copy.py). Pipeline step 5 (Search): fewer points.

The rule: delete a DEAD copy of a chunk where a live copy exists; keep both live copies (they are
usually the same text under two different models, and nothing free says which is which); keep
everything when unsure; never delete the last copy. Checked on REAL Kerala groups from the original
(tests/fixtures/kerala_dup_groups.json), on synthetic cases, and by fuzzing the invariants.

Also validated outside the unit tests, read-only on the original, 4 Nov 2026: 940 real groups,
480 holding a dead copy (400 pairs, 60 triples, 20 quads) all resolved to deleting exactly the dead
copy, 460 all-live groups kept whole, 0 wrong deletions (DECISIONS A132).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from data import dedupe_copy as dc

FIX = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "kerala_dup_groups.json").read_text())["groups"]
MU = np.load(dc.DIRECTION).astype(np.float64)
RNG = np.random.default_rng(3)


def _members(group):
    return [
        dc.Member(m["id"], np.array(m["vector"], dtype=np.float64), dc.detector_score(np.array(m["vector"]), MU))
        for m in group["members"]
    ]


# --- real groups ----------------------------------------------------------------------------------
def test_the_fixture_holds_real_pairs_of_both_kinds_and_a_triple():
    kinds = {g["kind"] for g in FIX}
    assert kinds == {"pair dead+live", "pair live+live", "triple with a dead copy"}
    for g in FIX:
        assert all(len(m["vector"]) == 1024 for m in g["members"])


@pytest.mark.parametrize("group", FIX, ids=[f"{g['kind']}-{g['chunk_id']}" for g in FIX])
def test_a_real_group_deletes_exactly_the_dead_copy_and_nothing_in_a_live_group(group):
    members = _members(group)
    plan = dc.plan_group(members)
    dead = {m["id"] for m in group["members"] if m["truth_dead"]}
    ids = {m["id"] for m in group["members"]}
    assert set(plan.delete) == dead  # a dead copy is removed; a live group loses nothing
    assert set(plan.keep) == ids - dead and set(plan.delete) | set(plan.keep) == ids
    assert plan.status == ("dead_removed" if dead else "all_live")


def test_the_two_live_copies_of_a_real_live_group_are_different_models_and_both_are_kept():
    live = [g for g in FIX if g["kind"] == "pair live+live"]
    for g in live:
        a, b = _members(g)
        cos = float(a.vector @ b.vector / np.linalg.norm(a.vector) / np.linalg.norm(b.vector))
        assert 0.85 < cos < 0.99  # two models embedding the same text, not the same vector
        assert dc.plan_group([a, b]).keep == (a.id, b.id)


# --- synthetic cases ------------------------------------------------------------------------------
def _vec(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=1024)
    return v / np.linalg.norm(v)


def _near(v: np.ndarray, cos: float, seed: int) -> np.ndarray:
    """A unit vector at (about) the given cosine to v."""
    w = _vec(seed)
    w = w - (w @ v) * v
    w /= np.linalg.norm(w)
    return cos * v + np.sqrt(1 - cos**2) * w


def M(i, vec, score):
    return dc.Member(i, vec, score)


def test_a_single_copy_is_kept():
    p = dc.plan_group([M(1, _vec(1), 0.5)])
    assert (p.status, p.delete, p.keep) == ("single", (), (1,))


def test_two_agreeing_live_copies_are_both_kept_even_if_they_are_the_same_vector():
    v = _vec(2)
    assert dc.plan_group([M(1, v, 0.5), M(2, v, 0.5)]).status == "all_live"
    assert dc.plan_group([M(1, v, 0.5), M(2, _near(v, 0.95, 5), 0.6)]).delete == ()


def test_a_pair_that_disagrees_removes_the_clearly_lower_scoring_copy():
    v = _vec(3)
    p = dc.plan_group([M(10, _near(v, 0.01, 6), 0.002), M(11, v, 0.45)])
    assert (p.status, p.delete, p.keep) == ("dead_removed", (10,), (11,))
    # and it does not matter which comes first
    q = dc.plan_group([M(11, v, 0.45), M(10, _near(v, 0.01, 6), 0.002)])
    assert q.delete == (10,)


def test_a_pair_that_disagrees_but_the_detector_cannot_separate_is_kept_whole():
    v = _vec(4)
    close = dc.plan_group([M(1, _near(v, 0.0, 7), 0.05), M(2, v, 0.07)])  # 0.02 apart, under the margin
    assert (close.status, close.delete) == ("unclear", ())
    neither = dc.plan_group([M(1, _near(v, 0.0, 7), 0.20), M(2, v, 0.50)])  # no copy under the line
    assert (neither.status, neither.delete) == ("unclear", ())


def test_a_long_healthy_chunk_scoring_low_is_not_deleted_by_the_detector_alone():
    """The detector's length bias (about 1% of long healthy vectors fall under 0.10) cannot
    delete anything: two copies that AGREE are kept whatever their scores."""
    v = _vec(5)
    p = dc.plan_group([M(1, v, 0.04), M(2, _near(v, 0.96, 8), 0.5)])
    assert p.status == "all_live" and p.delete == ()
    both_low = dc.plan_group([M(1, v, 0.05), M(2, _near(v, 0.96, 8), 0.06)])
    assert both_low.status == "all_live" and both_low.delete == ()


def test_a_triple_with_one_odd_copy_removes_only_that_copy():
    v = _vec(6)
    p = dc.plan_group([M(1, v, 0.5), M(2, _near(v, 0.95, 9), 0.48), M(3, _near(v, 0.0, 10), 0.003)])
    assert (p.status, p.delete, p.keep) == ("dead_removed", (3,), (1, 2))


def test_a_triple_where_two_copies_disagree_with_everyone_is_unclear_and_kept():
    p = dc.plan_group([M(1, _vec(11), 0.4), M(2, _vec(12), 0.003), M(3, _vec(13), 0.002)])
    assert (p.status, p.delete) == ("unclear", ())


def test_a_triple_whose_remaining_copies_disagree_is_unclear_and_kept():
    v = _vec(14)
    p = dc.plan_group([M(1, v, 0.5), M(2, _near(v, 0.3, 15), 0.45), M(3, _vec(16), 0.001)])
    assert p.delete == ()


def test_the_dead_copy_must_be_under_the_detector_line_as_well():
    v = _vec(17)
    p = dc.plan_group([M(1, v, 0.5), M(2, _near(v, 0.0, 18), 0.12), M(3, _near(v, 0.97, 19), 0.5)])
    assert p.status == "unclear" and p.delete == ()  # disagrees with the rest but scores 0.12


# --- invariants, fuzzed -----------------------------------------------------------------------------
def test_whatever_the_vectors_the_last_copy_is_never_deleted_and_only_a_dead_removed_group_deletes():
    for t in range(3000):
        n = int(RNG.integers(1, 6))
        base = _vec(1000 + t)
        mem = []
        for i in range(n):
            kind = RNG.choice(["same", "near", "far"])
            vec = base if kind == "same" else _near(base, float(RNG.uniform(0.3, 0.99)), 5000 + t * 7 + i) if kind == "near" else _vec(9000 + t * 7 + i)
            mem.append(M(100 + i, vec, float(RNG.uniform(-0.1, 0.7))))
        p = dc.plan_group(mem)
        ids = {m.id for m in mem}
        assert set(p.keep) | set(p.delete) == ids and not set(p.keep) & set(p.delete)
        assert len(p.keep) >= 1, "the last copy was deleted"
        assert len(p.delete) <= 1, "more than one copy deleted from one group"
        if p.status != "dead_removed":
            assert p.delete == ()


# --- the collection plan and the script -------------------------------------------------------------
def test_the_collection_plan_counts_every_kind_and_the_identical_live_pairs():
    v = _vec(20)
    groups = {
        "a": [M(1, v, 0.5), M(2, v, 0.5)],  # live, the same vector
        "b": [M(3, v, 0.5), M(4, _near(v, 0.93, 21), 0.5)],  # live, two models
        "c": [M(5, _near(v, 0.0, 22), 0.001), M(6, v, 0.5)],  # dead + live
        "d": [M(7, _vec(23), 0.3), M(8, _vec(24), 0.002), M(9, _vec(25), 0.001)],  # unclear
    }
    pl = dc.plan_collection(groups)
    assert dict(pl.statuses) == {"all_live": 2, "dead_removed": 1, "unclear": 1}
    assert pl.delete == [5] and pl.delete_chunk == {5: "c"}
    assert pl.identical_live_pairs == 1 and pl.unclear[0][0] == "d"


def test_the_script_refuses_the_original_collections(monkeypatch):
    calls = []
    monkeypatch.setattr(dc, "http", lambda *a, **k: calls.append(a))
    for name in ("legal_corpus_v1", "legal_corpus_v2", "acts_india"):
        monkeypatch.setattr("sys.argv", ["dedupe_copy.py", name, "--apply"])
        with pytest.raises(SystemExit) as e:
            dc.main()
        assert "REFUSED" in str(e.value)
    assert calls == []
