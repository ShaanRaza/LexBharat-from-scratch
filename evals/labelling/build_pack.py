"""Turn the pipeline's real answers into a labelling spreadsheet: ONE ROW PER CITATION (A141 follow-up).

Input: the JSONL written by `evals/labelling/run_real.py`. Output: an .xlsx a person with no technical background can work
through. Each row shows what a lawyer needs to judge one citation and nothing about how the system works:

  the question | the sentence of the answer that relies on this source | the authority (title, citation as recorded) |
  the passage the system pulled from it, in full | a link to the document | YOUR LABEL (a drop-down: Supported / Partly
  supported / Not supported) | WHY (free text) | Minutes (optional) | the whole answer, for context

A citation is judged against the SENTENCE(S) that carry its marker, not against the whole answer, because a lawyer cannot
say whether a source "supports an answer" without knowing which claim it is meant to support.

The pipeline's own verdict on the citation (its status, record id) is kept in grouped columns at the far right so it does not
anchor the reader. Questions that produced NO cited answer have no rows; they are listed on their own sheet with the reason,
because they cannot be labelled as pipeline answers.

The spreadsheet holds party names and judgment text, so it is written OUTSIDE the repo.

  python -m evals.labelling.build_pack --in pipeline_answers_v2.jsonl --out labelling_pack.xlsx

Needs `openpyxl` (not a repo dependency; see evals/a141/README.md for the scratch environment).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

LABELS = ["Supported", "Partly supported", "Not supported"]
MARK = re.compile(r"\[S(\d+)\]")
RUN = re.compile(r"((?:\s*\[S\d+\])+)")
SAMPLE_SEED = 41150


def claims_by_source(answer: str) -> dict[str, list[str]]:
    """{ "S1": [the sentence(s) that carry [S1]], ... }.

    A marker belongs to the text between the previous marker run and itself, so both "claim [S1]." and "claim. [S1]"
    (the verifier attaches a marker after the full stop, A137) credit the claim to its source. Order is preserved and a
    sentence is not repeated for the same source."""
    out: dict[str, list[str]] = {}
    pos = 0
    for m in RUN.finditer(answer):
        claim = answer[pos : m.start()].strip()
        pos = m.end()
        # the text after a run starts the next claim; a leading stray full stop or space is not part of it
        claim = claim.lstrip(".;, ").strip()
        if not claim:
            continue
        for sid in MARK.findall(m.group(1)):
            lst = out.setdefault(f"S{sid}", [])
            if claim not in lst:
                lst.append(claim)
    return out


def _words(s: str) -> int:
    return len(s.split())


def rows_from_results(results: list[dict]) -> tuple[list[dict], list[dict]]:
    """(one row per citation, one entry per question that has no cited answer)."""
    rows: list[dict] = []
    none: list[dict] = []
    for r in results:
        cites = r.get("citations") or []
        if r["outcome"] != "answered" or not cites:
            reason = r["message_key"] or r["outcome"]
            if r["outcome"] == "answered":
                reason = "answered, but no citation survived verification"
            none.append(
                {
                    "id": r["id"],
                    "question": r["question"],
                    "outcome": r["outcome"],
                    "reason": reason,
                    "error": r.get("error", ""),
                    "answer": r.get("answer_text", ""),
                }
            )
            continue
        passages = {p["source_id"]: p for p in r.get("passages", [])}
        claims = claims_by_source(r["answer_text"])
        for c in cites:
            p = passages.get(c["source_id"], {})
            text = p.get("text") or c.get("quote") or ""
            rows.append(
                {
                    "qid": r["id"],
                    "question": r["question"],
                    "claim": "\n\n".join(claims.get(c["source_id"], []))
                    or "(the answer does not mark which sentence relies on this source)",
                    "source_id": c["source_id"],
                    "authority": c.get("title")
                    or p.get("title")
                    or "(no title recorded)",
                    "citation_string": c.get("citation_string")
                    or p.get("citation_string")
                    or "",
                    "passage": text,
                    "link": c.get("pdf_url")
                    or c.get("source_url")
                    or p.get("pdf_url")
                    or p.get("source_url")
                    or "",
                    "answer": r["answer_text"],
                    "system_status": c.get("status", ""),
                    "record_id": c.get("record_id", ""),
                    "kind": c.get("kind", ""),
                }
            )
    return rows, none


def load_stub_order(path: Path | None) -> list[str]:
    if path is None:
        return []
    return [json.loads(x)["id"] for x in path.read_text().splitlines() if x.strip()]


def reading_load(rows: list[dict]) -> dict:
    """Words a reader meets per row (claim + authority + passage). A count, not a time."""
    w = [
        _words(r["claim"]) + _words(r["authority"]) + _words(r["passage"]) for r in rows
    ]
    if not w:
        return {}
    s = sorted(w)
    return {
        "rows": len(w),
        "words_median": int(statistics.median(w)),
        "words_p90": s[int(0.9 * (len(s) - 1))],
        "words_max": s[-1],
        "words_total": sum(w),
    }


def pick_time_sample(rows: list[dict], n: int = 10) -> list[int]:
    """Row numbers (1-based) of a seeded sample to time, spread over the length distribution rather than the first ten."""
    import random

    rng = random.Random(SAMPLE_SEED)  # noqa: S311 - a reproducible sample, not a secret
    return sorted(rng.sample(range(1, len(rows) + 1), min(n, len(rows))))


def write_xlsx(
    rows: list[dict], none: list[dict], path: Path, sample: list[int]
) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    readme = wb.active
    readme.title = "Read me first"
    for i, line in enumerate(_readme(len(rows), len(none), sample), 1):
        c = readme.cell(row=i, column=1, value=line)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if line and (line.isupper() or line.startswith("##")):
            c.font = Font(bold=True, size=13)
    readme.column_dimensions["A"].width = 110

    ws = wb.create_sheet("Labels")
    heads = [
        ("Row", 6), ("Question no.", 9), ("The question that was asked", 30),
        ("What the answer says that relies on this source", 44), ("The source (title; citation as recorded)", 30),
        ("The passage the system pulled from that source", 90), ("Link to the full document", 14),
        ("YOUR LABEL (pick one)", 20), ("WHY (a few words is fine)", 40), ("Minutes (optional)", 11),
        ("The whole answer, for context", 50),
        ("Source tag", 8), ("System's own status", 14), ("Record id", 22),
    ]  # fmt: skip
    for j, (h, w) in enumerate(heads, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill(
            "solid", fgColor="1F3864" if j not in (8, 9, 10) else "C55A11"
        )
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[1].height = 34
    band = [
        PatternFill("solid", fgColor="FFFFFF"),
        PatternFill("solid", fgColor="EEF3FA"),
    ]
    last_q, shade = None, 0
    for i, r in enumerate(rows, 1):
        if r["qid"] != last_q:
            shade, last_q = 1 - shade, r["qid"]
        auth = r["authority"] + (
            f"\n{r['citation_string']}" if r["citation_string"] else ""
        )
        vals = [i, r["qid"], r["question"], r["claim"], auth, r["passage"], "", "", "", None, r["answer"],
                r["source_id"], r["system_status"], r["record_id"]]  # fmt: skip
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i + 1, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.fill = band[shade]
            c.font = Font(size=9 if j == 6 else 10)
        if r["link"]:
            lc = ws.cell(row=i + 1, column=7, value="Open the document")
            lc.hyperlink = r["link"]
            lc.font = Font(color="0563C1", underline="single", size=10)
        else:
            ws.cell(row=i + 1, column=7, value="(no link recorded)")
        # Excel stops a row at 409 points: size it to the longest cell, capped, and the cell still holds all the text
        lines = max(
            len(r["passage"]) / 105 + r["passage"].count("\n"),
            len(r["claim"]) / 48 + r["claim"].count("\n"),
            len(r["answer"]) / 55,
            len(r["question"]) / 32,
            4,
        )
        ws.row_dimensions[i + 1].height = min(409, 12.5 * lines + 8)
    dv = DataValidation(type="list", formula1='"' + ",".join(LABELS) + '"', allow_blank=True, showErrorMessage=True,
                        errorTitle="Pick from the list", error="Choose Supported, Partly supported or Not supported.")  # fmt: skip
    ws.add_data_validation(dv)
    dv.add(f"H2:H{len(rows) + 1}")
    ws.freeze_panes = "D2"
    ws.sheet_view.zoomScale = 85
    ws.column_dimensions.group("L", "N", outline_level=1, hidden=True)

    ns = wb.create_sheet("Not labelled")
    for j, (h, w) in enumerate(
        [
            ("Question no.", 10),
            ("The question", 50),
            ("What happened", 38),
            ("Detail", 50),
        ],
        1,
    ):
        c = ns.cell(row=1, column=j, value=h)
        c.font = Font(bold=True)
        ns.column_dimensions[get_column_letter(j)].width = w
    for i, n in enumerate(none, 2):
        for j, v in enumerate(
            [n["id"], n["question"], n["reason"], n["error"] or n["answer"][:300]], 1
        ):
            ns.cell(row=i, column=j, value=v).alignment = Alignment(
                wrap_text=True, vertical="top"
            )

    ts = wb.create_sheet("Time test")
    ts.column_dimensions["A"].width = 100
    for i, line in enumerate(_timetest(sample), 1):
        ts.cell(row=i, column=1, value=line).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _readme(n_rows: int, n_none: int, sample: list[int]) -> list[str]:
    return [
        "HOW TO USE THIS SHEET",
        "",
        "What this is. A legal research tool answered 100 questions and cited sources for what it said. Your job is to check each citation: "
        "does the source it cites actually say what the answer claims?",
        "",
        f"What you will see. The 'Labels' sheet has {n_rows} rows. Each row is ONE citation (so one answer can have several rows). "
        "For each row you see: the question; the sentence from the answer that relies on this source; the source's title; the passage "
        "the tool pulled from the source; and a link to the full document if you want to look further.",
        "",
        "What to do. Read the claim, then read the passage. In the orange 'YOUR LABEL' column pick one from the drop-down:",
        "  Supported - the passage says what the claim says (or clearly means it).",
        "  Partly supported - the passage supports some of the claim, or something close to it, but not all of it.",
        "  Not supported - the passage does not say this, or says something different.",
        "In the 'WHY' column write a few words, especially for Partly supported and Not supported. If you cannot decide from the passage "
        "alone, open the link, then pick the closest label and say so in WHY. Skip nothing silently: a blank label means 'not done'.",
        "",
        "You are judging the CITATION, not whether the answer is good law and not whether you would have cited something else.",
        "",
        "Tip: the passage column is wide. Zoom out (bottom right of the window) to about 80% to see the claim, the passage and the label together.",
        "",
        "TIMING",
        "Please time the first ten rows (listed on the 'Time test' sheet) with a stopwatch, and write the minutes per row in the "
        "'Minutes (optional)' column. That is the number to use when quoting hours to anyone.",
        "",
        f"Questions with no citation: {n_none} of the 100 questions produced no cited answer (the tool declined, found nothing, or "
        "failed). They are on the 'Not labelled' sheet with the reason; there is nothing to check for them.",
        "",
        "The sheet holds judgment text and party names from public court records. Please do not forward it outside the team.",
    ]


def _timetest(sample: list[int]) -> list[str]:
    return [
        "TIME TEST",
        "",
        "Time these rows, one at a time, from the moment you start reading the claim until you have chosen the label and written the WHY.",
        "Write the minutes in the 'Minutes (optional)' column of the 'Labels' sheet.",
        "",
        "Rows to time (a fixed random sample, not the first ten, so it includes long and short ones): "
        + ", ".join(map(str, sample)),
        "",
        "After ten rows: the median of those minutes, times the number of rows, is the honest estimate of the hours. Quote that, not a guess.",
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--order",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "question_set.jsonl",
    )
    a = ap.parse_args()
    results = [json.loads(x) for x in a.inp.read_text().splitlines() if x.strip()]
    order = {qid: i for i, qid in enumerate(load_stub_order(a.order))}
    results.sort(key=lambda r: order.get(r["id"], 10**6))
    rows, none = rows_from_results(results)
    sample = pick_time_sample(rows)
    write_xlsx(rows, none, a.out, sample)
    load = reading_load(rows)
    print(
        f"{len(results)} questions: {len(rows)} citation rows, {len(none)} questions with no cited answer"
    )
    print("reading load (words per row):", load)
    print("time-test rows:", sample)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
