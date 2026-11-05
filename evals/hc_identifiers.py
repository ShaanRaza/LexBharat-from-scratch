"""How many judgments yield a neutral citation, and a case reference? (A124)

    .venv/bin/python -m evals.hc_identifiers                       # practice fixtures
    .venv/bin/python -m evals.hc_identifiers --records hc.parquet  # the data session

INPUT: records with `full_text` (or `text`), `court`, `decision_date`, `case_number` and
optionally `citation`. A record that HAS a stored citation is not eligible (the stored
string is never replaced); `--ignore-stored` counts it anyway, which is the only way to
run the practice fixtures, because every one of them carries a stored citation (none
is empty). That run proves the counting, not the coverage.

OUTPUT: records, how many had a candidate in the header, how many passed all three
guards, why the rest were rejected, how many had a candidate only in the body (the
trap), and how many yield a case reference (when there is no neutral citation).
Nothing here reads the Qdrant collection or the data directory.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from core.hc_citation import case_reference, extract_neutral_citation
from evals.title_keys import PRACTICE, read_records


def measure(records: Sequence[dict[str, Any]], ignore_stored: bool = False) -> dict:
    eligible = [r for r in records if ignore_stored or not r.get("citation")]
    reasons: Counter[str] = Counter()
    refs = 0
    for r in eligible:
        res = extract_neutral_citation(
            r.get("full_text") or r.get("text") or "",
            r.get("court"),
            r.get("decision_date"),
        )
        reasons[res.reason] += 1
        if not res.citation and case_reference(
            r.get("case_number"), r.get("court"), r.get("decision_date")
        ):
            refs += 1
    header = sum(
        n for k, n in reasons.items() if k not in ("no_candidate", "body_only")
    )
    return {
        "records": len(records),
        "eligible_no_stored_citation": len(eligible),
        "had_a_candidate_in_the_header": header,
        "passed_all_three_guards": reasons["ok"],
        "rejected_by_reason": {
            k: n for k, n in sorted(reasons.items()) if k not in ("ok", "no_candidate")
        },
        "no_candidate_anywhere": reasons["no_candidate"],
        "yield_a_case_reference_instead": refs,
        "yield_nothing": len(eligible) - reasons["ok"] - refs,
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--records", type=Path)
    ap.add_argument("--ignore-stored", action="store_true")
    a = ap.parse_args(argv)
    if a.records:
        recs, src = read_records(a.records), str(a.records)
    else:
        recs = read_records(PRACTICE / "judgments.jsonl.gz")
        src, a.ignore_stored = "practice fixtures (all with a stored citation)", True
    m = measure(recs, a.ignore_stored)
    print(json.dumps({"source": src, **m}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
