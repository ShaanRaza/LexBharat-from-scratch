"""The advocate review pack for the "who is speaking" question (DATA-GAPS sections 22 and 25).

ONE QUESTION per row, and only one: in the cited passage, who is saying the words that support this sentence? It replaces the
generic Supported / Partly / Not-supported labelling task for these pairs, because a passage can support a sentence in the
word-overlap sense while the words are a party's rejected argument or a lower court's holding (DATA-GAPS 22). The pack is the
instrument that gives the figure comparable to the 6.3% found by hand: pairs where the answer is a party, a rejected argument,
a lower court, another authority or an order on the facts, over pairs reviewed.

Design (written down before any advocate sees it):
  * The unit is the (sentence, cited passage) pair, the same unit as the hand count. The passage is shown IN FULL, as the writer saw it.
  * Blind. Nothing the system or its author concluded is in any cell: not the hand reading, not the real claim check's verdict, not a
    stratum. Row order is shuffled with a fixed seed so the pairs of one question do not sit together and hint at a pattern.
  * Two workbooks (advocate A, advocate B). SHARED pairs, the same in both, measure agreement; every other pair goes to exactly one
    advocate. Shared pairs are stratified (the pairs the hand reading flagged, plus the pair the real check removed, plus a random fill),
    because agreement measured on clean pairs alone says nothing about the hard class. Report raw agreement and say it is stratified.
  * Answers come from a closed list (LABELS). Only the first two are correct; see SCORING.

The workbook holds judgment text and party names, so it is written OUTSIDE the repo. Needs `openpyxl` (not a repo dependency).

  python -m evals.labelling.build_speaker_pack --pairs pairs.json --out-dir ~/pack
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

LABELS = [
    "The court: its own holding or reasoning",
    "The statute itself, quoted by the court",
    "A party or counsel: an argument",
    "Counsel: an argument the court rejected",
    "A lower court or tribunal, recited",
    "Another authority the court cites",
    "The court's order on these facts, not a rule",
    "Nobody: the passage does not say this",
    "Cannot tell from this passage alone",
]
CORRECT = set(LABELS[:2])
MISATTRIBUTED = set(LABELS[2:7])  # the class DATA-GAPS 22 counts
UNSUPPORTED = {LABELS[7]}
UNDECIDED = {LABELS[8]}
SCORING = (
    "Correct: the court, or the statute quoted by the court. Misattributed (the 6.3% class): a party, a rejected argument, a lower "
    "court, another authority, an order on the facts. Unsupported: nobody. Undecided: cannot tell. The figure is misattributed over "
    "pairs reviewed, reported with an interval and with the undecided count beside it."
)
SEED = 51150
SHARED_N = 20
WORDS_PER_MINUTE = (
    150,
    250,
)  # an ESTIMATE range for reading dense legal prose; replace with the timed figure


def split_pairs(pairs: list[dict], seed: int = SEED, shared_n: int = SHARED_N):
    """(A rows, B rows, shared ids). Each pair gets an id P01.. in input order. Shared pairs are every pair with a `stratum` of
    "hard" first, then a seeded random fill to `shared_n`. The rest alternate between A and B after a seeded shuffle, so the two
    halves differ by at most one pair."""
    rng = random.Random(seed)  # noqa: S311 - a reproducible assignment, not a secret
    rows = [{**p, "pair_id": f"P{i:02d}"} for i, p in enumerate(pairs, 1)]
    hard = [r for r in rows if r.get("stratum") == "hard"]
    rest = [r for r in rows if r.get("stratum") != "hard"]
    rng.shuffle(rest)
    need = max(0, shared_n - len(hard))
    shared = hard + rest[:need]
    own = rest[need:]
    a_own, b_own = own[0::2], own[1::2]
    a = shared + a_own
    b = shared + b_own
    rng.shuffle(a)
    rng.shuffle(b)
    return a, b, {r["pair_id"] for r in shared}


def words(r: dict) -> int:
    return (
        len(r["question"].split())
        + len(r["sentence"].split())
        + len(r["passage"].split())
    )


def reading_load(rows: list[dict]) -> dict:
    """Words per row (question + sentence + passage). A count, not a time."""
    w = sorted(words(r) for r in rows)
    if not w:
        return {}
    return {
        "rows": len(w),
        "words_median": int(statistics.median(w)),
        "words_p90": w[int(0.9 * (len(w) - 1))],
        "words_max": w[-1],
        "words_total": sum(w),
    }


def estimate_hours(rows: list[dict], wpm=WORDS_PER_MINUTE) -> tuple[float, float]:
    """An estimate of reading time only (no deciding, no writing), from words at `wpm`. NOT a timed figure."""
    total = sum(words(r) for r in rows)
    return total / wpm[1] / 60, total / wpm[0] / 60


def time_sample(rows: list[dict], n: int = 10) -> list[int]:
    rng = random.Random(SEED + 1)  # noqa: S311
    return sorted(rng.sample(range(1, len(rows) + 1), min(n, len(rows))))


def write_xlsx(
    rows: list[dict], path: Path, who: str, sample: list[int], shared: set[str]
) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    rd = wb.active
    rd.title = "Read me first"
    for i, line in enumerate(_readme(len(rows), who), 1):
        c = rd.cell(row=i, column=1, value=line)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if line.isupper():
            c.font = Font(bold=True, size=13)
    rd.column_dimensions["A"].width = 110

    ws = wb.create_sheet("Review")
    heads = [
        ("Row", 6), ("The question that was asked", 30), ("The sentence from the answer", 44),
        ("The passage it cites, in full", 95),
        ("WHO is saying the words in the passage that support this sentence? (pick one)", 36),
        ("Say who or where, if you did not pick the first two", 36), ("Minutes (optional)", 11), ("Pair", 7),
    ]  # fmt: skip
    for j, (h, w) in enumerate(heads, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="C55A11" if j in (5, 6, 7) else "1F3864")
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[1].height = 48
    for i, r in enumerate(rows, 1):
        vals = [
            i,
            r["question"],
            r["sentence"],
            r["passage"],
            "",
            "",
            None,
            r["pair_id"],
        ]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i + 1, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.font = Font(size=9 if j == 4 else 10)
        lines = max(
            len(r["passage"]) / 110 + r["passage"].count("\n"),
            len(r["sentence"]) / 48,
            len(r["question"]) / 32,
            4,
        )
        ws.row_dimensions[i + 1].height = min(409, 12.5 * lines + 8)
    dv = DataValidation(type="list", formula1=f"Choices!$A$1:$A${len(LABELS)}", allow_blank=True, showErrorMessage=True,
                        errorTitle="Pick from the list", error="Choose one of the listed answers.")  # fmt: skip
    ws.add_data_validation(dv)
    dv.add(f"E2:E{len(rows) + 1}")
    ws.freeze_panes = "D2"
    ws.sheet_view.zoomScale = 85
    ws.column_dimensions.group("H", "H", outline_level=1, hidden=True)

    ch = wb.create_sheet("Choices")
    for i, lab in enumerate(LABELS, 1):
        ch.cell(row=i, column=1, value=lab)
    ch.column_dimensions["A"].width = 60

    ts = wb.create_sheet("Time test")
    ts.column_dimensions["A"].width = 100
    for i, line in enumerate(_timetest(sample), 1):
        ts.cell(row=i, column=1, value=line).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _readme(n: int, who: str) -> list[str]:
    return [
        f"HOW TO USE THIS SHEET ({who})",
        "",
        "What this is. A legal research tool wrote answers and cited a source passage for each sentence. A sentence can match its "
        "passage word for word and still be wrong to cite, because the words in the passage were not the court's own view. This sheet "
        "asks you one question per row about that, and nothing else.",
        "",
        f"What you see. {n} rows on the 'Review' sheet. Each row: the question that was asked, ONE sentence from the answer, and the "
        "whole passage that sentence cites.",
        "",
        "What to do. Read the sentence, then the passage. Find the words in the passage that say what the sentence says. In the orange "
        "column pick who is saying them:",
        "  The court: its own holding or reasoning. The court states it as its view in this judgment.",
        "  The statute itself, quoted by the court. The judgment reproduces the provision.",
        "  A party or counsel: an argument. A submission by a party's lawyer, not adopted by the court.",
        "  Counsel: an argument the court rejected. As above, and the court goes on to reject it.",
        "  A lower court or tribunal, recited. The decision of the court below, or of a tribunal, as the judgment reports it.",
        "  Another authority the court cites. A different judgment's holding, quoted or described in support.",
        "  The court's order on these facts, not a rule. The disposal of this appeal, which the sentence turns into a general rule.",
        "  Nobody: the passage does not say this.",
        "  Cannot tell from this passage alone. Use this when the answer depends on the rest of the judgment, and say what you would need.",
        "If you pick anything other than the first two, write a few words in the next column saying who or where. Skip nothing silently: "
        "a blank means 'not done'.",
        "",
        "You are NOT judging whether the sentence is good law, and not whether the answer is a good one. Only who is speaking.",
        "",
        "Some pairs appear in both advocates' sheets. That is deliberate, so we can see where two careful readers differ. Please do not "
        "compare notes while you work.",
        "",
        "TIMING",
        "Please time the ten rows listed on the 'Time test' sheet and write the minutes in the 'Minutes (optional)' column. Do not "
        "quote hours for the whole sheet until that is done.",
        "",
        "The sheet holds judgment text and party names from public court records. Please do not forward it outside the team.",
    ]


def _timetest(sample: list[int]) -> list[str]:
    return [
        "TIME TEST",
        "",
        "Time these rows, one at a time, from the moment you start reading the sentence until you have picked an answer and written the note.",
        "Write the minutes in the 'Minutes (optional)' column of the 'Review' sheet.",
        "",
        "Rows to time (a fixed random sample, not the first ten): "
        + ", ".join(map(str, sample)),
        "",
        "After ten rows: the median of those minutes times the number of rows is the honest estimate of the hours. Quote that, not a guess.",
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    pairs = json.loads(a.pairs.read_text())
    ra, rb, shared = split_pairs(pairs)
    for who, rows in (("Advocate A", ra), ("Advocate B", rb)):
        sample = time_sample(rows)
        out = a.out_dir / f"Advocate-review-pack-{who[-1]}.xlsx"
        write_xlsx(rows, out, who, sample, shared)
        print(who, reading_load(rows), "time-test rows", sample, "->", out)
    print("pairs", len(pairs), "shared", len(shared), "A", len(ra), "B", len(rb))
    lo, hi = estimate_hours(ra)
    print(
        f"ESTIMATE, reading only, not timed: A {lo:.1f} to {hi:.1f} hours at {WORDS_PER_MINUTE[1]} to {WORDS_PER_MINUTE[0]} words a minute"
    )


if __name__ == "__main__":
    main()
