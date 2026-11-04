"""Write core/coverage.json from what the corpus holds (decisions O7, A51; gate item 19).

Plain words: the courts come from `core/court_ids.json` (every court the snapshot's record ids
name, measured over all 32.6M judgment rows) and the instruments are the three `jurisdiction`
values the Act collections carry. Everything else in coverage.json (the sentence, the refusal
buckets, the excluded list) is kept from the file as it stands, because those are wording and
scope decisions, not measurements. `sentence_approved` is never touched.

    .venv/bin/python -m data.coverage_report --write   # regenerate core/coverage.json
    .venv/bin/python -m data.coverage_report           # check: exit 1 if the file is stale

What it does NOT do: it does not count points in Qdrant. The per-court point counts are in
docs/DATA-GAPS.md sections 19 and 21 and the Act inventory in section 20; this script only
turns the court table into the file's `courts`, so the two cannot drift. A court is listed
here only if section 21 found it in the original collections (COURTS_IN_QDRANT below)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "core" / "coverage.json"
COURT_IDS = ROOT / "core" / "court_ids.json"

# The Supreme Court keeps the id the code and tests already use.
SC_KEY, SC_ID = "supreme-court", "supreme_court"

# DATA-GAPS section 21 (4 Nov 2026): the 26 courts with points in legal_corpus_v1/v2. A court in
# court_ids.json that is not here would be listed in the file without being searchable.
COURTS_IN_QDRANT = 26

# Instruments are what the SERVED collection holds, not what is staged. `kanoon_v1` holds the
# Supreme Court and 74,484 Central Act points (1,568 Acts, DATA-GAPS section 20); the 1,024,068
# State and regulatory points sit in the staging collection `acts_noncentral_v1` and have never
# been promoted (A133), so they are NOT listed. Add them here only when they are promoted.
INSTRUMENTS = [
    ("central_acts", "Central Acts", "central"),
]

# Scope, not measurement: what is out. High Courts are IN (owner, 3 Nov 2026). Tribunals are out
# at launch (G-T, A139). District courts are out because the dataset holds no judgment file for
# them: its 26 judgment files are the Supreme Court and 25 High Courts (DATASET.md).
EXCLUDED = ["district courts", "tribunals"]
LOWER_COURT_BUCKET = (
    "Needs a judgment of a district court or another court below the High Courts."
)

GENERATED_BY = (
    "data/coverage_report.py from core/court_ids.json (snapshot v2026.08, measured "
    "2026-11-03), docs/DATA-GAPS.md sections 19, 20 and 21 (4 Nov 2026), and the "
    "`jurisdiction` values of the Act collections"
)

NOTE = (
    "Written by data/coverage_report.py; do not widen it by hand. This is the ONLY place a "
    "coverage category may be written (tests/test_coverage_source.py). INSTRUMENTS are what "
    "the served collection holds: Central Acts only. State Acts and regulations (1,024,068 "
    "points) are staged in acts_noncentral_v1, never promoted (A133), and are not listed. "
    "So the five statutes the Act inventory found absent (CrPC 1973, Consumer Protection "
    "1986, Payment of Gratuity 1972, Employees' Compensation 1923, the Constitution) are NOT "
    "held: their text lives only in the staging collection. The Indian Trusts Act 1882 is not "
    "in the dataset at all. COURTS follow the owner's launch scope (every High Court in v1, "
    "3 Nov 2026) over the original collections legal_corpus_v1/v2, and the served "
    "`kanoon_v1` does NOT yet hold them (it serves the Supreme Court only: 381,271 points, "
    "measured 4 Nov 2026) until the launch collection is built (PRD-v2 section 7, item 19). "
    "Held means in the corpus, not complete: 2,865,144 whole cases (18.26%) have no chunk in "
    "Qdrant (A141, open), and there is no length exclusion (owner). OWNER ITEM, not resolved "
    "here: the sentence ends 'anything after the data-as-of date', and the snapshot is "
    "labelled v2026.08 while the latest Supreme Court judgment held is dated 6 November 2025 "
    "(reported by the SC lane), so that date may be months after the content it describes."
)


def build(measured_at: str) -> dict:
    cur = json.loads(COVERAGE.read_text(encoding="utf-8"))
    ids = json.loads(COURT_IDS.read_text(encoding="utf-8"))["courts"]
    if len(ids) != COURTS_IN_QDRANT:
        raise SystemExit(
            f"court_ids.json names {len(ids)} courts, DATA-GAPS section 21 found "
            f"{COURTS_IN_QDRANT} in Qdrant: re-measure before regenerating"
        )
    courts = []
    sc = ids[SC_KEY]
    courts.append(
        {
            "id": SC_ID,
            "name": sc["label"],
            "covered_label": "Supreme Court judgments",
            "payload": {"court": sc["label"]},
        }
    )
    high = []
    for key, c in ids.items():
        if key == SC_KEY:
            continue
        name = " ".join(c["label"].split())
        high.append(
            {
                "id": key.replace("-", "_"),
                "name": name,
                "covered_label": f"{name} judgments",
                "payload": {"court": c["label"]},
            }
        )
    courts += sorted(high, key=lambda c: c["name"])
    out = {
        "status": "measured",
        "note": NOTE,
        "measured_at": measured_at,
        "generated_by": GENERATED_BY,
        "sentence_approved": cur["sentence_approved"],
        "sentence_template": cur["sentence_template"],
        "courts_phrase": "Supreme Court and High Court judgments",
        "instruments_phrase": "the Central Acts listed on our coverage page",
        "not_in_dataset_message": cur["not_in_dataset_message"],
        "courts": courts,
        "instruments": [
            {"id": i, "covered_label": label, "payload": {"jurisdiction": j}}
            for i, label, j in INSTRUMENTS
        ],
        "excluded": EXCLUDED,
        "buckets": {**cur["buckets"], "needs_lower_court": LOWER_COURT_BUCKET},
    }
    return out


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    cur = json.loads(COVERAGE.read_text(encoding="utf-8"))
    when = cur.get("measured_at") or date.today().isoformat()
    text = render(build(when))
    if "--write" in sys.argv:
        COVERAGE.write_text(text, encoding="utf-8")
        print(f"wrote {COVERAGE.relative_to(ROOT)} ({when})")
    else:
        stale = COVERAGE.read_text(encoding="utf-8") != text
        print(
            "core/coverage.json is STALE" if stale else "core/coverage.json is current"
        )
        sys.exit(1 if stale else 0)
