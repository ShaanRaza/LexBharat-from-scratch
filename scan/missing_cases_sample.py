"""Twenty whole-missing English cases, drawn uniformly at random, with the first 500 characters of each (A141, step 1a).

The whole decision to load the 2.87M cases rests on their being real law, and section 19's classification was automatic
(language and length). This lets a person read some. The draw is uniform over CASES, so the courts appear in proportion to
the gap, not in proportion to anything convenient. Same missing set as section 19 (checked against results.json).

Read only, local, no Qdrant call, no cost. The output holds party names from public judgments, so it is written
OUTSIDE the repo (default: <home>/missing_cases_sample.md).

  python -m scan.missing_cases_sample --seed 41120 --n 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from scan import coverage_gap as g
from scan import missing_set as ms

COLS = [
    "case_id",
    "chunk_id",
    "chunk_index",
    "total_chunks",
    "text",
    "year",
    "decision_date",
    "court",
    "language_code",
]


def main() -> None:
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=str(g.HOME_DEFAULT))
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=41120)
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--tokens-lo",
        type=int,
        default=None,
        help="only cases whose chunks total at least this many Voyage tokens (needs missing_tokens/)",
    )
    ap.add_argument(
        "--tokens-hi", type=int, default=None, help="and fewer than this many"
    )
    a = ap.parse_args()
    home = Path(a.home)
    results = json.loads((home / "results.json").read_text())
    langs = json.loads((home / "parquet" / "langs.json").read_text())
    en = langs["en"]
    q_ch, q_ca = ms.load_q(home)
    per_file = []  # (file, candidate rows, their case hashes)
    for f in sorted(g.PARQUET_DIR.glob("in_*_judgments.parquet")):
        z = np.load(home / "parquet" / (f.stem + ".npz"))
        ch, ca, lg = z["chash"], z["cash"], z["lang"]
        cand = np.flatnonzero(~np.isin(ch, q_ch) & (lg == en) & ~np.isin(ca, q_ca))
        per_file.append((f, cand, ca[cand]))
        print(f"{f.name}: {len(np.unique(ca[cand])):,} cases", flush=True)
    ranged = a.tokens_lo is not None or a.tokens_hi is not None
    if ranged:
        parts = [np.load(f) for f in sorted((home / "missing_tokens").glob("in_*.npz"))]
        tc = np.concatenate([p["cash"] for p in parts])
        tt = np.concatenate([p["tokens"] for p in parts]).astype(np.int64)
        uniq, inv = np.unique(tc, return_inverse=True)
        tot = np.bincount(inv, weights=tt)
        lo = a.tokens_lo if a.tokens_lo is not None else 0
        hi = a.tokens_hi if a.tokens_hi is not None else np.inf
        allowed = uniq[(tot >= lo) & (tot < hi)]
        per_file = [
            (f, cand[np.isin(cases, allowed)], cases[np.isin(cases, allowed)])
            for f, cand, cases in per_file
        ]
    counts = [len(np.unique(c)) for _, _, c in per_file]
    total = sum(counts)
    expect = sum(c["whole_missing_english_cases"] for c in results["codes"].values())
    if not ranged and total != expect:
        raise SystemExit(
            f"INTEGRITY FAILED: {total:,} cases here, {expect:,} in section 19"
        )
    picks = np.sort(
        np.random.default_rng(a.seed).choice(total, size=a.n, replace=False)
    )
    bounds = np.cumsum([0, *counts])
    lines = [
        f"# {a.n} whole-missing English cases, drawn uniformly at random"
        + (
            f" from those of {a.tokens_lo or 0} to {a.tokens_hi or 'any'} Voyage tokens"
            if ranged
            else ""
        )
        + "\n",
        f"Seed {a.seed}; {total:,} cases in the population ("
        + (
            "a length slice of the set"
            if ranged
            else "the same set as DATA-GAPS section 19"
        )
        + "). For each: the first 500 "
        "characters of the case's first chunk exactly as it sits in the parquet (the `Case: ... Court: ...` line is part of "
        "the stored text). Nothing is edited.\n",
    ]
    for k, p in enumerate(picks, 1):
        fi = int(np.searchsorted(bounds, p, side="right") - 1)
        f, cand, cases = per_file[fi]
        uniq = np.unique(cases)
        chosen = uniq[p - bounds[fi]]
        rows = cand[cases == chosen]
        pf = pq.ParquetFile(f)
        starts = np.cumsum(
            [0]
            + [
                pf.metadata.row_group(i).num_rows
                for i in range(pf.metadata.num_row_groups)
            ]
        )
        recs = []
        for rg in np.unique(np.searchsorted(starts, rows, side="right") - 1):
            sel = rows[(rows >= starts[rg]) & (rows < starts[rg + 1])] - starts[rg]
            recs += (
                pf.read_row_group(int(rg), columns=COLS).take(sel.tolist()).to_pylist()
            )
        recs.sort(key=lambda r: r["chunk_index"])
        r0 = recs[0]
        lines += [
            f"## {k}. {r0['case_id']}",
            f"{r0['court']} | decided {r0['decision_date']} (year {r0['year']}) | {len(recs)} chunk(s) missing of "
            f"{r0['total_chunks']} | first chunk is {len(r0['text']):,} characters | language {r0['language_code']}\n",
            "```",
            r0["text"][:500],
            "```\n",
        ]
    out = Path(a.out) if a.out else home / "missing_cases_sample.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
