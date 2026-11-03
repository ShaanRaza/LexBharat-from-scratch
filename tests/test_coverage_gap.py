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


# --- the verdict binds on whole missing cases (owner, 4 Nov 2026) --------------------------------------------------
KL, BM, TG = (g.LAUNCH_CODES[c] for c in ("KLHC", "HCBM", "HBHC"))


def _synthetic_home(tmp_path):
    """A tiny parquet and a tiny Qdrant with known shapes, written in the formats the stages write.
    KLHC: 10 English cases of 2 chunks, 1 wholly absent, 1 with a chunk missing (label empty on every point).
    HBHC: 100 cases of 2 chunks, a chunk missing from 3 of them (scattered 1.5%, no whole case missing).
    HCBM: 100 cases, all present, plus one wholly absent HINDI case. One id names no court (absent) and one
    Qdrant point with an id naming no court."""
    _, codes = g.court_table()
    codes = [*codes, "?"]
    cix = {c: i for i, c in enumerate(codes)}
    langs = {"en": 0, "hi": 1}
    par, qd = [], []  # (chunk id, lang, label)
    for i in range(10):
        for k in (1, 2):
            cid = f"KLHC{i:04d}_{k:03d}"
            par.append((cid, "en", ""))
            if i < 8 or (i == 8 and k == 1):
                qd.append((cid, "en", ""))
    for i in range(100):
        for k in (1, 2):
            cid = f"HBHC{i:04d}_{k:03d}"
            par.append((cid, "en", ""))
            if not (i < 3 and k == 2):
                qd.append((cid, "en", "labelled"))
        cid = f"HCBM{i:04d}_001"
        par.append((cid, "en", ""))
        qd.append((cid, "en", "labelled"))
    par.append(("HCBM9999_001", "hi", ""))
    par.append(("123_x", "en", ""))
    qd.append(("456_y", "en", ""))

    def arrays(rows):
        ch = np.array([g.H(r[0]) for r in rows], dtype=np.uint64)
        ca = np.array([g.H(g.case_key(r[0])) for r in rows], dtype=np.uint64)
        co = np.array(
            [
                cix[g.code_of(r[0])] if g.code_of(r[0]) in cix else cix["?"]
                for r in rows
            ],
            dtype=np.int8,
        )
        return ch, ca, co

    d = tmp_path / "parquet"
    d.mkdir()
    ch, ca, co = arrays(par)
    np.savez(
        d / "in_x.npz",
        chash=ch,
        cash=ca,
        code=co,
        lang=np.array([langs[r[1]] for r in par], dtype=np.int16),
    )
    (d / "langs.json").write_text(json.dumps(langs))
    (d / "codes.json").write_text(json.dumps(codes))
    for coll in g.COLLECTIONS:
        sd = tmp_path / "scan" / coll
        sd.mkdir(parents=True)
        rows = qd if coll == "legal_corpus_v2" else []
        ch, ca, co = (
            arrays(rows)
            if rows
            else (
                np.array([], np.uint64),
                np.array([], np.uint64),
                np.array([], np.int8),
            )
        )
        labels = {"": 0, "labelled": 1}
        np.savez(
            sd / "page_000000.npz",
            chash=ch,
            cash=ca,
            code=co,
            label=np.array([labels[r[2]] for r in rows], dtype=np.int32),
        )
        (sd / "labels.json").write_text(json.dumps(labels))
        (sd / "state.json").write_text(
            json.dumps(
                {
                    "offset": None,
                    "pages": 1,
                    "points": len(rows),
                    "done": True,
                    "count_at_start": len(rows),
                }
            )
        )
    return g.Ctx(tmp_path)


def test_the_gate_binds_on_whole_missing_cases_and_reports_scattered_chunks_beside_it(
    tmp_path,
):
    res = g.stage_analyze(_synthetic_home(tmp_path))
    k, t, b = res["gate"][KL], res["gate"][TG], res["gate"][BM]
    assert (k["english_cases"], k["whole_missing_english_cases"]) == (10, 1) and k[
        "whole_pct"
    ] == 10.0
    assert k["scattered_english_chunks"] == 1 and k["scattered_pct"] == pytest.approx(
        5.0
    )  # 1 of 20 chunks
    # scattered above the threshold, but it does not bind
    assert t["whole_missing_english_cases"] == 0 and t[
        "scattered_pct"
    ] == pytest.approx(1.5)
    # the Hindi case wholly absent from Qdrant is not English, so it is not a missing English case
    assert b["whole_missing_english_cases"] == 0 and b["english_cases"] == 100
    assert res["tripped_whole_cases"] == [KL] and res["verdict_defect"] is True
    # reported, not binding (overall: 4 scattered of 322 chunks is also over 1%)
    assert set(res["scattered_would_trip"]) == {KL, TG, "All courts"}


def test_scattered_chunks_alone_never_make_a_defect():
    scattered_only = {"whole_pct": 0.0, "scattered_pct": 7.5}
    v = g.verdict({"a": scattered_only}, {"whole_pct": 0.0, "scattered_pct": 7.5})
    assert (
        v["verdict_defect"] is False
        and v["tripped_whole_cases"] == []
        and v["scattered_would_trip"] == ["a", "All courts"]
    )
    whole = {
        "whole_pct": g.GATE_THRESHOLD_PCT,
        "scattered_pct": 0.0,
    }  # exactly at the line trips
    assert g.verdict({"a": whole}, {"whole_pct": 0.1, "scattered_pct": 0.0})[
        "tripped_whole_cases"
    ] == ["a"]
    assert g.verdict({"a": {"whole_pct": 0.0, "scattered_pct": 0.0}}, whole)[
        "tripped_whole_cases"
    ] == ["All courts"]


def test_the_court_comes_from_the_id_and_unlabelled_or_unclassifiable_rows_are_kept_and_counted(
    tmp_path,
):
    res = g.stage_analyze(_synthetic_home(tmp_path))
    cs = res["court_source"]
    assert "chunk id prefix" in cs["method"] and cs["parquet_label_read"] is False
    assert (
        cs["parquet_rows_id_names_no_court"] == 1
        and cs["qdrant_points_id_names_no_court"]["legal_corpus_v2"] == 1
    )
    # every Kerala point carries no label (17) plus the unclassifiable point (1): a label-based run drops them all
    assert cs["qdrant_points_without_court_label"]["legal_corpus_v2"] == 18
    # and the id-based comparison still sees Kerala's gap in full
    assert res["gate"][KL]["whole_missing_english_cases"] == 1
    assert (
        res["codes"]["?"]["parquet_only_chunks"] == 1
    )  # the unclassifiable parquet row is in the totals


def test_section_19_and_morning_say_which_condition_tripped_and_where_the_court_came_from(
    tmp_path,
):
    ctx = _synthetic_home(tmp_path)
    res = g.stage_analyze(ctx)
    text = g.write_section(ctx, res, [])
    assert f"whole missing cases TRIPPED in {KL}" in text
    assert "would have tripped in" in text and "does not bind" in text
    assert "taken from the chunk id, not from the `court` label" in text
    morning = g.morning_text(ctx, res, "committed locally (not pushed)")
    assert "COVERAGE DEFECT" in morning and f"tripped in: **{KL}**" in morning
    assert "Court came from the chunk ID, not the label" in morning
    # the single-query-vector comparison is settled (A136), so it is not listed as a job
    assert "Not on the to-do list" in morning and "gate item 29" in morning
