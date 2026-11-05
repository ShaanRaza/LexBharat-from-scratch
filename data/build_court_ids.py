"""Build core/court_ids.json: which court an id prefix means (CLAUDE.md section 6).

Plain words: a judgment's record id starts with letters that name its court (KLHC...,
WBCHCA...), and the Supreme Court's ids start with a year and INSC. Measured across all
32,572,660 judgment rows of the snapshot v2026.08 (3 Nov 2026): 30 prefixes, and every one
of them occurs in exactly one source file, so each maps to exactly one court. The `court`
LABEL is another matter: 0.58% of rows carry none, 0.21% a spelling variant, and 282 rows
(0.00087%) carry another court's name. A filter on the label silently drops the first two
groups, so the id is the thing to trust and the label is kept beside it.

Input: data/court_prefix_counts.csv (one row per source file, id prefix and label, with its
row count; read once from the 26 judgment parquet files). Output: core/court_ids.json.

    python data/build_court_ids.py            # writes core/court_ids.json
    python data/build_court_ids.py --check    # exits 1 if the file is out of date

The alias list below is a judgement, not a measurement: it names labels that mean the SAME
court as the id (a spelling variant, a bench, a former name). A label that is generic ("High
Court") or shared by two courts ("High Court of Hyderabad") is kept as an alias for
classifying rows but is never used to look a court up from a label. Aliases that look
historically real are kept, not collapsed away: the original label always stays in the payload.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = ROOT / "data" / "court_prefix_counts.csv"
OUT = ROOT / "core" / "court_ids.json"

# labels that name the SAME court as the id, by source file (kfix_samecourt.py, 3 Nov 2026)
SAME: dict[str, list[str]] = {
    "allahabad": ["Allahabad High Court", "High Court of Allahabad"],
    "andhra-pradesh": ["High Court of Andhra Pradesh", "High Court of Amaravati", "High Court of Andhra", "High Court of Hyderabad"],
    "bombay": ["Bombay High Court", "High Court of Bombay", "High Court of Mumbai", "High Court", "High Court of Nagpur", "High Court of Aurangabad"],
    "calcutta": ["Calcutta High Court", "High Court of Calcutta"],
    "chhattisgarh": ["High Court Of Chhattisgarh", "High Court of Chhattisgarh"],
    "delhi": ["High Court of Delhi"],
    "gauhati": ["Gauhati High Court", "High Court of Gauhati", "High Court of Guwahati"],
    "gujarat": ["High Court of Gujarat"],
    "himachal-pradesh": ["High Court of Himachal Pradesh"],
    "jammu-and-kashmir": ["High Court of Jammu and Kashmir", "High Court of Kashmir", "High Court of Srinagar"],
    "jharkhand": ["High Court of Jharkhand"],
    "karnataka": ["High Court of Karnataka"],
    "kerala": ["High Court of Kerala"],
    "madhya-pradesh": ["High Court of Madhya Pradesh", "High Court of Madhya"],
    "madras": ["Madras High Court", "High Court of Madras", "High Court of Chennai"],
    "manipur": ["High Court of Manipur"],
    "meghalaya": ["High Court of Meghalaya"],
    "orissa": ["Orissa High Court", "High Court of Orissa"],
    "patna": ["Patna High Court", "High Court of Patna"],
    "punjab-and-haryana": ["High Court of Punjab and Haryana", "High Court of Haryana", "High Court of Chandigarh"],
    "rajasthan": ["High Court Of Rajasthan", "High Court of Rajasthan"],
    "sikkim": ["High Court of Sikkim"],
    "supreme-court": ["Supreme Court of India"],
    "telangana": ["High Court  for State of Telangana", "High Court of Telangana", "High Court of Hyderabad"],
    "tripura": ["High Court of Tripura"],
    "uttarakhand": ["High Court of Uttarakhand"],
}  # fmt: skip

# labels that name no place: kept as aliases for classifying rows, never used to look a court up
GENERIC_LABELS = ["High Court", "Court"]

SC_CODE = (
    "INSC"  # the Supreme Court has no letter prefix; its ids are <year>_INSC_<n>_<k>
)
SC_PATTERN = r"^\d{4}_INSC_\d+_\d+$"


def build() -> dict:
    rows = list(csv.DictReader(COUNTS.open()))
    by_src: dict[str, dict[str, dict[str, int]]] = collections.defaultdict(
        lambda: collections.defaultdict(lambda: collections.defaultdict(int))
    )
    for r in rows:
        by_src[r["source_file"]][r["id_prefix"]][r["court_label"]] += int(r["rows"])
    courts: dict[str, dict] = {}
    totals = collections.Counter()
    for src in sorted(by_src):
        labels: dict[str, int] = collections.defaultdict(int)
        prefixes: dict[str, int] = {}
        for pref, lab in by_src[src].items():
            code = SC_CODE if pref == "" else pref
            prefixes[code] = sum(lab.values())
            for k, v in lab.items():
                labels[k] += v
        named = {k: v for k, v in labels.items() if k}
        canonical = max(named, key=named.get)
        aliases = [a for a in SAME[src] if a != canonical]
        same = {canonical, *aliases}
        usual = labels[canonical]
        alias_rows = sum(v for k, v in named.items() if k in same and k != canonical)
        missing = labels.get("", 0)
        foreign = sum(v for k, v in named.items() if k not in same)
        courts[src] = {
            "label": canonical,
            "aliases": aliases,
            "prefixes": dict(sorted(prefixes.items())),
            "rows": sum(prefixes.values()),
            "label_rows": {
                "usual": usual,
                "alias": alias_rows,
                "missing": missing,
                "other_court": foreign,
            },
            "other_court_labels": {
                k: v
                for k, v in sorted(named.items(), key=lambda kv: -kv[1])
                if k not in same
            },
        }
        totals.update(
            {
                "rows": courts[src]["rows"],
                "usual": usual,
                "alias": alias_rows,
                "missing": missing,
                "other_court": foreign,
            }
        )
    return {
        "_note": "IDENTIFICATION, not coverage: which court an id prefix means, from the snapshot's own data. What the product covers is core/coverage.json and only that. Built by data/build_court_ids.py from data/court_prefix_counts.csv; do not edit by hand.",
        "snapshot": "v2026.08",
        "measured": "2026-11-03",
        "supreme_court_id_pattern": SC_PATTERN,
        "generic_labels": GENERIC_LABELS,
        "totals": dict(totals),
        "courts": courts,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if a.check:
        sys.exit(0 if OUT.exists() and OUT.read_text() == text else 1)
    OUT.write_text(text)
    t = json.loads(text)["totals"]
    print(
        f"wrote {OUT.relative_to(ROOT)}: {len(json.loads(text)['courts'])} courts, {t}"
    )


if __name__ == "__main__":
    main()
