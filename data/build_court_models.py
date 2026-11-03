"""Build core/court_models.json: which Voyage model embedded each court's chunks (A128).

Plain words: the corpus is embedded by three models, and they differ by court (and, inside some
courts, by document). One query vector can only match one of them, so a query is embedded once
per model and each vector is searched only among the courts that model built. This file says,
for each source collection and court, which model to use: the MAJORITY model of a measured
sample (data/court_model_sample.csv: the 46 court groups of DATA-GAPS section 13, plus the
Supreme Court from section 12).

A court is registered only if its group was measured on at least MIN_SAMPLE healthy chunks, and
nothing else is: a court, tribunal or source that is not listed here is REFUSED, never given a
default model (a wrong default silently loses recall). A tie for the majority is refused too.
The residual (7.6% of sampled chunks sit outside their court's majority model) is accepted by
A128: no free per-point label exists.

    python data/build_court_models.py            # writes core/court_models.json
    python data/build_court_models.py --check    # exits 1 if the file is out of date
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "court_model_sample.csv"
OUT = ROOT / "core" / "court_models.json"
MIN_SAMPLE = 20
MODELS = ("voyage-4", "voyage-4-lite", "voyage-4-large")


def build() -> dict:
    ids = json.loads((ROOT / "core" / "court_ids.json").read_text())
    all_codes = sorted(c for ct in ids["courts"].values() for c in ct["prefixes"])
    collections: dict[str, dict] = {}
    for r in csv.DictReader(SAMPLE.open()):
        col = collections.setdefault(
            r["collection"], {"courts": {}, "not_registered": {}}
        )
        counts = {
            "voyage-4": int(r["voyage_4"]),
            "voyage-4-lite": int(r["voyage_4_lite"]),
            "voyage-4-large": int(r["voyage_4_large"]),
        }
        n = int(r["healthy_chunks"])
        top = sorted(counts.items(), key=lambda kv: -kv[1])
        code = r["court_code"]
        if n < MIN_SAMPLE:
            col["not_registered"][code] = (
                f"measured on {n} chunk(s), fewer than {MIN_SAMPLE}"
            )
        elif top[0][1] == top[1][1]:
            col["not_registered"][code] = "a tie for the majority model"
        else:
            col["courts"][code] = {
                "model": top[0][0],
                "sample": {"n": n, **counts},
                "outside_majority": n - top[0][1],
            }
    for name, col in collections.items():
        for code in all_codes:
            if code not in col["courts"] and code not in col["not_registered"]:
                col["not_registered"][code] = "not measured in this collection"
        col["courts"] = dict(sorted(col["courts"].items()))
        col["not_registered"] = dict(sorted(col["not_registered"].items()))
    return {
        "_note": "The embedding model per court, from the majority of a measured sample (A128). Anything not listed under `courts` is refused, never defaulted. Built by data/build_court_models.py from data/court_model_sample.csv; do not edit by hand.",
        "min_sample": MIN_SAMPLE,
        "measured": "2026-11-02/03",
        "models": list(MODELS),
        "collections": dict(sorted(collections.items())),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = json.dumps(build(), indent=1) + "\n"
    if a.check:
        sys.exit(0 if OUT.exists() and OUT.read_text() == text else 1)
    OUT.write_text(text)
    d = json.loads(text)
    for name, c in d["collections"].items():
        print(
            f"{name}: {len(c['courts'])} courts registered, {len(c['not_registered'])} refused"
        )


if __name__ == "__main__":
    main()
