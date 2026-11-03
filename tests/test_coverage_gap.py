"""The overnight coverage-gap scan (scan/coverage_gap.py; lane A). Pure parts and the retry rule: no Qdrant, no parquet.

Pipeline steps touched: none (a read-only measurement). Run with the repo venv; the script itself needs
numpy, pyarrow and duckdb, so only importable parts are tested here (numpy is a dependency of the repo)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from scan import coverage_gap as g


def test_hashes_are_stable_64_bit_and_case_keys_drop_the_chunk_number():
    assert (
        g.H("KLHC010348322009_001")
        == g.H("KLHC010348322009_001")
        != g.H("KLHC010348322009_002")
    )
    assert 0 <= g.H("x") < 2**64
    assert g.case_key("KLHC010348322009_001") == "KLHC010348322009"
    assert g.case_key("2019_INSC_1387_003") == "2019_INSC_1387"
    assert g.case_key("nounderscore") == "nounderscore"


@pytest.mark.parametrize(
    "cid,code",
    [
        ("KLHC010348322009_001", "KLHC"),
        ("WBCHCA01123_4", "WBCHCA"),
        ("2019_INSC_1387_003", "INSC"),
        ("1952_INSC_28_078", "INSC"),
        ("IND_central_1", "IND"),
        ("123_x", "?"),
        ("", "?"),
    ],
)
def test_the_court_code_comes_from_the_id_prefix(cid, code):
    assert g.code_of(cid) == code


def _h(*ids):
    return np.array([g.H(i) for i in ids], dtype=np.uint64)


def test_compare_separates_whole_missing_cases_from_scattered_chunks():
    p = ["A_1_001", "A_1_002", "B_2_001", "B_2_002", "B_2_003", "C_3_001", "D_4_001"]
    q = [
        "A_1_001",
        "B_2_001",
        "B_2_003",
        "X_9_001",
    ]  # A: one of two chunks; B: two of three; C and D wholly absent; X not in the parquet
    p_ch, p_ca = _h(*p), _h(*[g.case_key(x) for x in p])
    q_ch, q_ca = _h(*q), _h(*[g.case_key(x) for x in q])
    r = g.compare(p_ch, p_ca, q_ch, q_ca)
    assert (r["parquet_chunks"], r["qdrant_chunks"], r["overlap_chunks"]) == (7, 4, 3)
    assert r["parquet_only_chunks"] == 4  # A_1_002, B_2_002, C_3_001, D_4_001
    assert (
        r["parquet_only_in_whole_missing_cases"] == 2 and r["whole_missing_cases"] == 2
    )  # C and D
    assert (
        r["parquet_only_in_partial_cases"] == 2 and r["partial_cases"] == 2
    )  # A and B are findable but incomplete
    assert r["qdrant_only_chunks"] == 1 and r["qdrant_only_whole_cases"] == 1  # X


def test_compare_counts_a_duplicated_parquet_chunk_once_and_a_duplicated_qdrant_chunk_once():
    p = ["A_1_001", "A_1_001", "B_2_001"]
    q = ["A_1_001", "A_1_001", "A_1_001"]
    r = g.compare(
        _h(*p), _h(*[g.case_key(x) for x in p]), _h(*q), _h(*[g.case_key(x) for x in q])
    )
    assert (
        r["parquet_chunks"],
        r["qdrant_chunks"],
        r["overlap_chunks"],
        r["parquet_only_chunks"],
    ) == (2, 1, 1, 1)


# --- the night's retry rule -----------------------------------------------------------------------------------------------
class FakeResp:
    def __init__(self, body):
        self._b = json.dumps(body).encode()

    def read(self):
        return self._b


@pytest.fixture
def clock(monkeypatch):
    slept = []
    monkeypatch.setattr(g.time, "sleep", lambda s: slept.append(s))
    return slept


def test_a_failed_read_is_retried_after_30_seconds_and_then_succeeds(
    monkeypatch, clock
):
    calls, logs = [], []

    def urlopen(req, timeout):
        calls.append(timeout)
        if len(calls) < 3:
            raise TimeoutError("slow")
        return FakeResp({"result": {"count": 7}})

    monkeypatch.setattr(g.urllib.request, "urlopen", urlopen)
    out = g.orig_post(
        "/collections/legal_corpus_v2/points/count", {"exact": True}, logs.append
    )
    assert out == {"count": 7} and len(calls) == 3
    assert set(calls) == {60}  # the 60 s timeout, every time
    assert clock.count(30) == 2  # a 30 s back-off after each of the two failures
    assert len(logs) == 2 and all(m.startswith("FAIL") for m in logs)


def test_five_consecutive_failures_hard_stop(monkeypatch, clock):
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        raise ConnectionError("down")

    monkeypatch.setattr(g.urllib.request, "urlopen", urlopen)
    with pytest.raises(g.Stop):
        g.orig_post("/collections/legal_corpus_v1/points/scroll", {}, lambda m: None)
    assert len(calls) == 5 and clock.count(30) == 4  # no back-off after the last one


def test_the_count_of_consecutive_failures_resets_after_a_success(monkeypatch, clock):
    seq = iter([ConnectionError("x")] * 4 + [None])
    n = {"i": 0}

    def urlopen(req, timeout):
        n["i"] += 1
        e = next(seq)
        if e:
            raise e
        return FakeResp({"result": {"points": [], "next_page_offset": None}})

    monkeypatch.setattr(g.urllib.request, "urlopen", urlopen)
    assert (
        g.orig_post("/collections/legal_corpus_v2/points/scroll", {}, lambda m: None)[
            "points"
        ]
        == []
    )
    assert n["i"] == 5  # four failures never hard-stopped it


@pytest.mark.parametrize(
    "path",
    [
        "/collections/legal_corpus_v2/points",
        "/collections/acts_india/points/scroll",
        "/collections/legal_corpus_v2/points/delete",
        "/collections/legal_corpus_v2/points/payload",
        "/collections/legal_corpus_v2",
        "/collections/kanoon_v1/points/scroll",
    ],
)
def test_only_scroll_and_count_of_the_two_corpus_collections_are_ever_allowed(
    path, monkeypatch
):
    monkeypatch.setattr(
        g.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("a request was sent")),
    )
    with pytest.raises(g.Stop):
        g.orig_post(path, {}, lambda m: None)


def test_the_script_has_no_write_route_to_the_original():
    import inspect

    src = inspect.getsource(g)
    for bad in (
        'method="PUT"',
        'method="DELETE"',
        "/points/delete",
        "/points/payload",
        "/index",
        "voyage",
        "embed",
    ):
        assert bad not in src.replace("embedded", "").replace("embedding", "").replace(
            "no embedding", ""
        ), bad


# --- the scan: checkpoint every page, resume where it stopped ------------------------------------------------------------------
def _fake_scroll(pages):
    state = {"i": 0, "offsets": []}

    def post(path, body, log):
        if path.endswith("/count"):
            return {"count": sum(len(p) for p in pages)}
        state["offsets"].append(body.get("offset"))
        pts = pages[state["i"]]
        state["i"] += 1
        nxt = (state["i"] * 1000) if state["i"] < len(pages) else None
        return {
            "points": [
                {"id": i, "payload": {"chunk_id": c, "court": "L"}}
                for i, c in enumerate(pts)
            ],
            "next_page_offset": nxt,
        }

    return post, state


def test_the_scan_checkpoints_every_page_and_resumes_from_the_saved_offset(
    tmp_path, monkeypatch
):
    pages = [
        ["KLHC01_1_001", "KLHC01_1_002"],
        ["KLHC01_2_001"],
        ["KLHC01_3_001", "KLHC01_3_002"],
    ]
    post, st = _fake_scroll(pages)
    monkeypatch.setattr(g, "orig_post", post)
    ctx = g.Ctx(tmp_path)
    g.stage_scan(
        ctx, ["legal_corpus_v2"], limit_pages=1
    )  # stop after one page, as a crash would
    state = json.loads((tmp_path / "scan/legal_corpus_v2/state.json").read_text())
    assert (
        state["pages"] == 1
        and state["points"] == 2
        and state["done"] is False
        and state["offset"] == 1000
    )
    post2, st2 = _fake_scroll(pages[1:])  # the resumed run asks for the saved offset
    monkeypatch.setattr(g, "orig_post", post2)
    g.stage_scan(ctx, ["legal_corpus_v2"])
    assert st2["offsets"][0] == 1000  # it did not start over
    state = json.loads((tmp_path / "scan/legal_corpus_v2/state.json").read_text())
    assert (
        state["done"] is True and state["points"] == 5 and state["count_at_start"] == 3
    )
    assert len(list((tmp_path / "scan/legal_corpus_v2").glob("page_*.npz"))) == 3
    ch, ca, co, lb, labels, stt = g.load_scan(ctx, "legal_corpus_v2")
    assert len(ch) == 5 and stt["done"]


def test_a_finished_collection_is_not_scanned_again(tmp_path, monkeypatch):
    d = tmp_path / "scan/legal_corpus_v2"
    d.mkdir(parents=True)
    (d / "state.json").write_text(
        json.dumps({"offset": None, "pages": 4, "points": 9, "done": True})
    )
    monkeypatch.setattr(
        g,
        "orig_post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("scanned again")),
    )
    g.stage_scan(g.Ctx(tmp_path), ["legal_corpus_v2"])
