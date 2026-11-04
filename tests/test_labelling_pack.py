"""The labelling pack builder (evals/labelling/build_pack.py): which sentence of an answer is credited to which source,
that every question without a cited answer is listed and none is silently dropped, and the row/reading-load arithmetic.
Synthetic data only; the real answers are produced by evals/labelling/run_real.py. Not a pipeline step."""

from __future__ import annotations

import pytest

from evals.labelling import build_pack as bp


def test_a_marker_credits_the_sentence_before_it_to_that_source():
    out = bp.claims_by_source(
        "Murder is punished with death [S1]. Fine may be added [S2][S1]."
    )
    assert out["S1"] == ["Murder is punished with death", "Fine may be added"]
    assert out["S2"] == ["Fine may be added"]


def test_a_marker_placed_after_the_full_stop_credits_the_sentence_before_it():
    out = bp.claims_by_source(
        "The firm traded at Bombay. [S1] It also traded at Indore. [S2]"
    )
    assert out == {
        "S1": ["The firm traded at Bombay."],
        "S2": ["It also traded at Indore."],
    }


def test_a_sentence_is_not_repeated_for_the_same_source_and_unmarked_text_is_not_credited():
    out = bp.claims_by_source(
        "Same claim [S1]. Same claim [S1]. Trailing text with no marker."
    )
    assert out == {"S1": ["Same claim"]}
    assert bp.claims_by_source("No markers at all.") == {}


def _result(qid, outcome="answered", cites=(), text="", key="", passages=()):
    return {
        "id": qid, "question": f"q {qid}", "outcome": outcome, "message_key": key, "error": "",
        "answer_text": text, "citations": list(cites), "passages": list(passages),
    }  # fmt: skip


def _cite(sid, title="A v B", url="http://x/y.pdf"):
    return {"source_id": sid, "record_id": f"rec-{sid}", "status": "verified", "citation_string": "(2020) 1 SCC 1",
            "pdf_url": url, "source_url": None, "title": title, "quote": None, "kind": "judgment"}  # fmt: skip


def test_one_row_per_citation_and_every_question_without_a_cited_answer_is_listed():
    results = [
        _result("a", cites=[_cite("S1"), _cite("S2")], text="One [S1]. Two [S2].",
                passages=[{"source_id": "S1", "text": "passage one"}, {"source_id": "S2", "text": "passage two"}]),
        _result("b", outcome="not_found", key="not_found"),
        _result("c", outcome="answered", cites=[], text="An answer with no surviving citation."),
        _result("d", outcome="out_of_scope", key="out_of_scope:needs_lower_court"),
    ]  # fmt: skip
    rows, none = bp.rows_from_results(results)
    assert [(r["qid"], r["source_id"]) for r in rows] == [("a", "S1"), ("a", "S2")]
    assert rows[0]["claim"] == "One" and rows[0]["passage"] == "passage one"
    assert [n["id"] for n in none] == ["b", "c", "d"]  # nothing is dropped
    assert none[1]["reason"].startswith("answered, but no citation")
    assert len(rows) + len({n["id"] for n in none}) >= len(results)


def test_a_citation_whose_claim_cannot_be_found_says_so_instead_of_leaving_a_blank():
    rows, _ = bp.rows_from_results(
        [
            _result(
                "a",
                cites=[_cite("S3")],
                text="No marker here.",
                passages=[{"source_id": "S3", "text": "p"}],
            )
        ]
    )
    assert "does not mark which sentence" in rows[0]["claim"]


def test_reading_load_counts_words_not_minutes_and_the_time_sample_is_fixed():
    rows = [
        {"claim": "a b", "authority": "c", "passage": "d e f"},
        {"claim": "x", "authority": "y", "passage": "z"},
    ]
    load = bp.reading_load(rows)
    assert load["rows"] == 2 and load["words_total"] == 9 and load["words_max"] == 6
    assert bp.pick_time_sample([{}] * 50) == bp.pick_time_sample([{}] * 50)
    assert (
        len(bp.pick_time_sample([{}] * 50)) == 10
        and len(bp.pick_time_sample([{}] * 4)) == 4
    )


def test_the_spreadsheet_has_a_dropdown_with_exactly_the_three_labels_and_one_row_per_citation(
    tmp_path,
):
    pytest.importorskip("openpyxl")
    import openpyxl

    rows, none = bp.rows_from_results(
        [_result("a", cites=[_cite("S1")], text="One [S1].", passages=[{"source_id": "S1", "text": "passage"}]),
         _result("b", outcome="not_found", key="not_found")]
    )  # fmt: skip
    out = tmp_path / "p.xlsx"
    bp.write_xlsx(rows, none, out, [1])
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Read me first", "Labels", "Not labelled", "Time test"]
    ws = wb["Labels"]
    assert ws.max_row == 2  # header + one citation
    dv = ws.data_validations.dataValidation[0]
    assert dv.formula1 == '"Supported,Partly supported,Not supported"'
    assert wb["Not labelled"].max_row == 2
