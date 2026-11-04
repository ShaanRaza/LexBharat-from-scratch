"""Write core/coverage.json from what the SERVED collection holds (decisions O7, A51, A146).

Plain words: coverage is what `kanoon_v1` serves today, not what the corpus holds elsewhere and
not the launch intent. Measured 4 Nov 2026: 381,271 Supreme Court points and 74,484 Central Act
points, nothing else. So the file lists the Supreme Court and Central Acts. The High Courts
(legal_corpus_v1/v2) and the State Acts and regulations (acts_noncentral_v1) are held in other
collections and reach users only when promoted; the change that does that must add them to
HELD_COURTS / INSTRUMENTS below and regenerate the file, the docs and the tests (PRD-v2
section 7, items 19 and 24). Wording (the sentence, the refusal buckets) is kept from the file as
it stands, because that is a decision, not a measurement. `sentence_approved` is never touched.

    .venv/bin/python -m data.coverage_report --write   # regenerate core/coverage.json
    .venv/bin/python -m data.coverage_report           # check: exit 1 if the file is stale

Court names come from `core/court_ids.json` so they cannot drift from the record-id table."""

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

# The courts `kanoon_v1` serves. To add the High Courts, put their `court_ids.json` keys here
# (and set COURTS_PHRASE so the sentence does not name 25 of them) in the change that builds the
# High Court serving collection.
HELD_COURTS = [SC_KEY]
COURTS_PHRASE = ""

# Instruments are what the SERVED collection holds, not what is staged. `kanoon_v1` holds the
# Supreme Court and 74,484 Central Act points (1,568 Acts, DATA-GAPS section 20); the 1,024,068
# State and regulatory points sit in the staging collection `acts_noncentral_v1` and have never
# been promoted (A133), so they are NOT listed. Add them here only when they are promoted.
INSTRUMENTS = [
    ("central_acts", "Central Acts", "central"),
]

# Scope, not measurement: what is out. High Courts are out until they are served (A146); tribunals
# are out at launch (G-T, A139); district courts are out because the dataset holds no judgment
# file for them (26 judgment files: the Supreme Court and 25 High Courts, DATASET.md).
EXCLUDED = ["High Courts", "district courts", "tribunals"]
HIGH_COURT_BUCKET = "Needs a judgment of a High Court."

GENERATED_BY = (
    "data/coverage_report.py from the held collection `kanoon_v1` (facets of `court` and "
    "`jurisdiction`, 4 Nov 2026), docs/DATA-GAPS.md section 20, and core/court_ids.json"
)

NOTE = (
    "Written by data/coverage_report.py; do not widen it by hand. This is the ONLY place a "
    "coverage category may be written (tests/test_coverage_source.py). It records what the "
    "SERVED collection `kanoon_v1` holds, measured 4 Nov 2026: 381,271 Supreme Court points "
    "and 74,484 Central Act points, nothing else. High Courts (legal_corpus_v1/v2) and State "
    "Acts and regulations (1,024,068 points in the staging collection acts_noncentral_v1, "
    "never promoted, A133) are NOT listed: the owner widened scope on 3 Nov 2026, but that is "
    "intent and this file records what is held. The change that serves them must add them "
    "here (HELD_COURTS, INSTRUMENTS) and regenerate. So the five statutes the Act inventory "
    "found absent (CrPC 1973, Consumer Protection 1986, Payment of Gratuity 1972, "
    "Employees' Compensation 1923, the Constitution) are NOT held: their text lives only in "
    "the staging collection. The Indian Trusts Act 1882 is not in the dataset at all. There "
    "is no length exclusion (owner); held does not mean complete (A141 is open). OWNER ITEM, "
    "not resolved here: the sentence ends 'anything after the data-as-of date', and the "
    "snapshot is labelled v2026.08 while the latest Supreme Court judgment held is dated 6 "
    "November 2025 (reported by the SC lane), so the date overstates currency by about nine "
    "months."
)


def ordered_buckets(cur: dict) -> dict:
    """The refusal buckets in the contract's order, High Courts as the wording says."""
    rest = {
        k: v
        for k, v in cur.items()
        if k not in ("needs_lower_court", "needs_high_court")
    }
    return {"needs_high_court": HIGH_COURT_BUCKET, **rest}


def build(measured_at: str) -> dict:
    cur = json.loads(COVERAGE.read_text(encoding="utf-8"))
    ids = json.loads(COURT_IDS.read_text(encoding="utf-8"))["courts"]
    courts = []
    for key in HELD_COURTS:
        c = ids[key]
        name = " ".join(c["label"].split())
        courts.append(
            {
                "id": SC_ID if key == SC_KEY else key.replace("-", "_"),
                "name": name,
                "covered_label": "Supreme Court judgments"
                if key == SC_KEY
                else f"{name} judgments",
                "payload": {"court": c["label"]},
            }
        )
    return {
        "status": "measured",
        "note": NOTE,
        "measured_at": measured_at,
        "generated_by": GENERATED_BY,
        "sentence_approved": cur["sentence_approved"],
        "sentence_template": cur["sentence_template"],
        **({"courts_phrase": COURTS_PHRASE} if COURTS_PHRASE else {}),
        "instruments_phrase": "the Central Acts listed on our coverage page",
        "not_in_dataset_message": cur["not_in_dataset_message"],
        "courts": courts,
        "instruments": [
            {"id": i, "covered_label": label, "payload": {"jurisdiction": j}}
            for i, label, j in INSTRUMENTS
        ],
        "excluded": EXCLUDED,
        "buckets": ordered_buckets(cur["buckets"]),
    }


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
