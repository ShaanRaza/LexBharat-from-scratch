"""The Act BM25 sparse repair (data/repair_act_sparse.py; DATA-GAPS section 9). Pipeline step 5 (Search):
the keyword half of hybrid search.

About half of the state and regulatory Acts carry raw term counts where BM25 weights belong, and for such a
point keyword search found nothing. The script copies the non-central Acts out of the ORIGINAL (read only)
into a staging collection on the copy instance with each broken sparse vector re-encoded. These tests cover
the parts that need no fastembed and no Qdrant: what counts as broken, what is refused, and that nothing can
be written to an original or to the serving collection.

Run for real (not here), 4 Nov 2026, against the live instances: plan over 20,000 points 49.6% broken;
193 broken points asked a keyword question built from their own words: found in the top 100 0 of 193 before
the repair, 184 of 193 after. The full copy and its verification are recorded in DECISIONS A133.
"""

from __future__ import annotations

import pytest

from data import repair_act_sparse as r


def sv(pairs: dict[int, float]) -> dict:
    return {"indices": list(pairs), "values": list(pairs.values())}


# --- what counts as broken ---------------------------------------------------------------------------
def test_a_vector_equal_to_the_fresh_encoding_is_not_broken():
    assert r.differs(sv({1: 1.2, 5: 0.7}), sv({5: 0.7, 1: 1.2})) is False  # order does not matter


def test_raw_term_counts_are_broken_even_when_they_share_the_index_set():
    """The signature found in the data: integer-only values where BM25 weights belong. A test on the
    index set alone (data/sparse_fix.py) would miss these if the tokens matched."""
    stored, fresh = sv({1: 2.0, 5: 1.0, 9: 3.0}), sv({1: 1.31, 5: 0.84, 9: 1.57})
    assert r.only_indices_differ(stored, fresh) is False  # same tokens
    assert r.differs(stored, fresh) is True  # but wrong weights


def test_a_different_set_of_tokens_is_broken():
    assert r.differs(sv({1: 1.0}), sv({2: 1.0})) is True
    assert r.only_indices_differ(sv({1: 1.0}), sv({2: 1.0})) is True
    assert r.differs(sv({1: 1.0}), sv({1: 1.0, 2: 0.5})) is True  # an extra token


def test_float_noise_under_the_tolerance_is_not_broken_but_a_real_difference_is():
    assert r.differs(sv({1: 1.00000}), sv({1: 1.00005})) is False
    assert r.differs(sv({1: 1.0}), sv({1: 1.001})) is True


def test_an_empty_vector_against_an_empty_encoding_is_not_broken():
    assert r.differs(sv({}), sv({})) is False


# --- the original is never written ------------------------------------------------------------------------
@pytest.mark.parametrize("dest", ["legal_corpus_v1", "legal_corpus_v2", "acts_india", "kanoon_v1"])
def test_the_destination_may_not_be_an_original_or_the_serving_collection(dest, monkeypatch):
    calls = []
    monkeypatch.setattr(r, "copy_http", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(r, "orig_scroll", lambda *a, **k: calls.append(a))
    args = type("A", (), {"dest": dest, "limit": 10})()
    with pytest.raises(SystemExit) as e:
        r.copy(args)
    assert "REFUSED" in str(e.value) and calls == []  # not even a read


def test_the_copy_instance_helper_refuses_any_other_port(monkeypatch):
    monkeypatch.setattr(r, "COPY", "http://localhost:6333")  # the original
    with pytest.raises(AssertionError):
        r.copy_http("/collections", method="GET")


def test_only_the_two_read_helpers_can_reach_the_original():
    """Every function that mentions the original's address is one of the two read helpers, and they
    use POST on scroll and on retrieve-by-id only: no write, delete or payload route exists for it."""
    import ast
    import inspect

    src = inspect.getsource(r)
    tree = ast.parse(src)
    funcs = [f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)]
    touching = {
        f.name
        for f in funcs
        if any(isinstance(n, ast.Name) and n.id == "ORIG" for n in ast.walk(f))  # the constant, not the word
    }
    assert touching == {"orig_scroll", "orig_retrieve"}
    for name in touching:
        seg = ast.get_source_segment(src, next(f for f in funcs if f.name == name))
        for bad in ('"PUT"', '"DELETE"', "/points/delete", "/points/payload", "/index"):
            assert bad not in seg, (name, bad)


def test_the_source_filter_selects_everything_except_the_central_acts():
    assert r.NOT_CENTRAL == {"must_not": [{"key": "jurisdiction", "match": {"value": "central"}}]}
    assert r.SOURCE == "acts_india"


def test_a_read_that_fails_stops_without_retrying(monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise TimeoutError("slow")

    monkeypatch.setattr(r.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit) as e:
        r.orig_scroll(None, 10, with_vector=False)
    assert "HARD STOP" in str(e.value) and "No retry" in str(e.value) and len(calls) == 1
