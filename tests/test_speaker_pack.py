"""The advocate review pack builder (evals/labelling/build_speaker_pack.py): every pair is reviewed, the shared pairs are
identical in both packs, the halves are balanced, nothing the system concluded reaches a cell, and the closed list is the
one the scoring uses. Synthetic data only. Not a pipeline step."""

from __future__ import annotations

import pytest

from evals.labelling import build_speaker_pack as sp


def _pairs(n=79, hard=9):
    return [
        {
            "question": f"question {i}",
            "sentence": f"sentence {i} says something",
            "passage": " ".join(f"w{i}x{j}" for j in range(40 + i)),
            "stratum": "hard" if i < hard else "other",
        }
        for i in range(n)
    ]


def test_every_pair_is_reviewed_and_the_halves_are_balanced():
    a, b, shared = sp.split_pairs(_pairs())
    ids_a, ids_b = {r["pair_id"] for r in a}, {r["pair_id"] for r in b}
    assert ids_a | ids_b == {f"P{i:02d}" for i in range(1, 80)}
    assert len(shared) == 20 and shared == ids_a & ids_b
    assert abs(len(a) - len(b)) <= 1
    assert len(a) == len(set(ids_a)) and len(b) == len(
        set(ids_b)
    )  # no row twice in one pack


def test_the_shared_pairs_are_the_flagged_ones_first_then_a_random_fill():
    pairs = _pairs(hard=9)
    _, _, shared = sp.split_pairs(pairs)
    flagged = {f"P{i:02d}" for i in range(1, 10)}
    assert flagged <= shared and len(shared) == 20


def test_more_flagged_pairs_than_the_shared_size_are_all_still_shared():
    _, _, shared = sp.split_pairs(_pairs(hard=25))
    assert len(shared) == 25


def test_the_split_is_reproducible_and_the_two_packs_are_ordered_differently():
    a1, b1, _ = sp.split_pairs(_pairs())
    a2, b2, _ = sp.split_pairs(_pairs())
    assert [r["pair_id"] for r in a1] == [r["pair_id"] for r in a2]
    assert [r["pair_id"] for r in a1][:20] != sorted(r["pair_id"] for r in a1)[:20]
    assert [r["pair_id"] for r in a1] != [r["pair_id"] for r in b1]
    # the flagged pairs are not bunched at the top: the final shuffle mixes them in
    flagged = {f"P{i:02d}" for i in range(1, 10)}
    assert {r["pair_id"] for r in a1[:9]} != flagged
    assert {r["pair_id"] for r in b1[:9]} != flagged


def test_the_list_of_answers_matches_the_scoring_classes():
    assert len(sp.LABELS) == len(set(sp.LABELS)) == 9
    classes = sp.CORRECT | sp.MISATTRIBUTED | sp.UNSUPPORTED | sp.UNDECIDED
    assert classes == set(sp.LABELS)
    assert not (sp.CORRECT & sp.MISATTRIBUTED)
    assert len(sp.CORRECT) == 2 and len(sp.MISATTRIBUTED) == 5


def test_reading_load_counts_words_and_the_hours_figure_is_an_estimate_range():
    rows = [{"question": "a b", "sentence": "c d e", "passage": "f " * 95}]
    assert sp.words(rows[0]) == 100
    assert sp.reading_load(rows)["words_median"] == 100
    lo, hi = sp.estimate_hours(rows * 10)
    assert 0 < lo < hi


def test_the_workbook_carries_no_conclusion_and_has_the_one_question(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    pairs = _pairs()
    # poison every field a conclusion might leak through: the extra keys must never be written
    for p in pairs:
        p["real"] = ["SECRET-VERDICT"]
        p["hand"] = "SECRET-LABEL"
    a, b, shared = sp.split_pairs(pairs)
    out = tmp_path / "a.xlsx"
    sp.write_xlsx(a, out, "Advocate A", sp.time_sample(a), shared)
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Read me first", "Review", "Choices", "Time test"]
    text = " ".join(
        str(c.value)
        for ws in wb
        for row in ws.iter_rows()
        for c in row
        if c.value is not None
    )
    for banned in (
        "SECRET-VERDICT",
        "SECRET-LABEL",
        "stratum",
        "hard",
        "supports",
        "does_not_support",
    ):
        assert banned not in text
    ws = wb["Review"]
    assert ws.max_row == len(a) + 1
    assert "WHO is saying" in ws["E1"].value
    assert [c.value for c in wb["Choices"]["A"] if c.value] == sp.LABELS
    assert ws.data_validations.dataValidation[0].formula1 == "Choices!$A$1:$A$9"
