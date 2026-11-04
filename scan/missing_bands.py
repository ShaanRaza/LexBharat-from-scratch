"""The missing cases by LENGTH BAND: count, share, cost to include, and a few real examples of each (A141).

Whether to load the short orders is a decision about what law the product covers, so it is the OWNER's, and
`core/coverage.json` (A51/O7) is where the answer would be recorded. This does not propose a cut-off. It gives the owner
the bands to draw the line between.

Length of a case = the length of its judgment text in characters (the largest `char_end` over its chunks; the stored header
line that sits at the top of every chunk is not counted). Cost = the exact Voyage tokens of its chunks, counted locally
(`scan/missing_tokens.py`, `data/voyage_token_count.py`), at list price. Read only, no Qdrant call, no spend.

Needs: `scan/missing_rows.py` and `scan/missing_tokens.py` to have finished, `pyarrow`.
  python -m scan.missing_bands
Writes <home>/missing_bands.json and <home>/missing_bands_examples.md. The examples file holds party names from public
judgments and is written OUTSIDE the repo.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import numpy as np

from data import voyage_token_count as vtc
from scan import coverage_gap as g

# judgment-text length bands, in characters (upper edge exclusive); the last is open
CHAR_EDGES = [0, 250, 500, 1000, 1500, 2000, 3000, 4000, 8000]
# chunk length bands, in Voyage tokens
TOKEN_EDGES = [0, 100, 200, 400, 800, 1200, 1600]
USD_INR = 85.0  # an assumption, as in c_embed.py and COSTS.md; not a quoted rate
PER_BAND_EXAMPLES = 3
SEED = 41140


def label(edges: list[int], i: int, unit: str) -> str:
    lo = edges[i]
    if i + 1 == len(edges):
        return f"{lo:,}+ {unit}"
    return f"{lo:,}-{edges[i + 1] - 1:,} {unit}"


def band_table(
    case_chars,
    case_tokens,
    case_chunks,
    case_code,
    case_year,
    code_names,
    recent_from: int,
):
    """One row per length band. Pure arrays in, plain numbers out (tested without any data)."""
    n = len(case_chars)
    tot_tokens = int(case_tokens.sum())
    which = np.digitize(case_chars, CHAR_EDGES[1:])  # 0..len(edges)-1
    rows = []
    for b in range(len(CHAR_EDGES)):
        m = which == b
        cases = int(m.sum())
        tok = int(case_tokens[m].sum())
        top = collections.Counter(case_code[m].tolist()).most_common(3)
        rows.append(
            {
                "band": label(CHAR_EDGES, b, "chars"),
                "cases": cases,
                "share_of_cases": cases / n,
                "chunks": int(case_chunks[m].sum()),
                "tokens": tok,
                "share_of_tokens": tok / tot_tokens,
                "recent_cases": int((m & (case_year >= recent_from)).sum()),
                "top_courts": [(code_names[c], k / max(cases, 1)) for c, k in top],
            }
        )
    # "include this band and everything longer": what drawing the line at the bottom of each band keeps
    for b, r in enumerate(rows):
        keep = which >= b
        r["if_line_drawn_here_cases_kept"] = int(keep.sum())
        r["if_line_drawn_here_cases_excluded"] = int((~keep).sum())
        r["if_line_drawn_here_tokens"] = int(case_tokens[keep].sum())
    return rows


def prices(tokens: int) -> dict:
    out = {}
    for model in ("voyage-4-lite", "voyage-4"):
        for batch in (True, False):
            usd = vtc.price_usd(tokens, model, batch=batch)
            out[f"{model} {'batch' if batch else 'standard'}"] = {
                "usd": usd,
                "inr": usd * USD_INR,
            }
    return out


def main() -> None:
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=str(g.HOME_DEFAULT))
    ap.add_argument("--recent-from", type=int, default=2016)
    a = ap.parse_args()
    home = Path(a.home)
    codes = json.loads((home / "parquet" / "codes.json").read_text())
    files = sorted(g.PARQUET_DIR.glob("in_*_judgments.parquet"))
    cols = collections.defaultdict(list)
    for fi, f in enumerate(files):
        rows = np.load(home / "missing_rows" / f"{f.stem}.npy")
        if not len(rows):
            continue
        z = np.load(home / "parquet" / f"{f.stem}.npz")
        ck = np.load(home / "missing_tokens" / f"{f.stem}.npz")
        if not np.array_equal(ck["chash"], z["chash"][rows]):
            raise SystemExit(
                f"{f.stem}: token checkpoint is not aligned with the cached rows"
            )
        char_end = (
            pq.ParquetFile(f)
            .read(columns=["char_end"])
            .column("char_end")
            .fill_null(0)
            .to_numpy(zero_copy_only=False)[rows]
        )
        for k, v in (
            ("cash", ck["cash"]),
            ("code", ck["code"]),
            ("tokens", ck["tokens"]),
            ("year", ck["year"]),
            ("chars", char_end),
            ("file", np.full(len(rows), fi, dtype=np.int16)),
            ("row", rows),
            ("chash", ck["chash"]),
        ):
            cols[k].append(v)
        print(f"{f.name}: {len(rows):,}", flush=True)
    c = {k: np.concatenate(v) for k, v in cols.items()}
    _, first = np.unique(
        c["chash"], return_index=True
    )  # a repeated chunk id counts once, as section 19 does
    c = {k: v[first] for k, v in c.items()}
    expect = json.loads((home / "missing_set.json").read_text())[
        "integrity_vs_section_19"
    ]
    cases_u, inv = np.unique(c["cash"], return_inverse=True)
    if [len(cases_u), len(c["cash"])] != [expect["cases"][1], expect["chunks"][1]]:
        raise SystemExit(
            f"INTEGRITY FAILED: {len(cases_u):,} cases / {len(c['cash']):,} chunks vs section 19 {expect['cases'][1]:,} / {expect['chunks'][1]:,}"
        )
    n = len(cases_u)
    case_chars = np.zeros(n, dtype=np.int64)
    np.maximum.at(case_chars, inv, c["chars"].astype(np.int64))
    case_tokens = np.bincount(inv, weights=c["tokens"], minlength=n).astype(np.int64)
    case_chunks = np.bincount(inv, minlength=n)
    case_code = np.zeros(n, dtype=np.int8)
    case_code[inv] = c["code"]
    case_year = np.zeros(n, dtype=np.int16)
    case_year[inv] = c["year"]
    table = band_table(
        case_chars, case_tokens, case_chunks, case_code, case_year, codes, a.recent_from
    )
    # chunk-length histogram, in billed tokens
    tw = np.digitize(c["tokens"], TOKEN_EDGES[1:])
    chunk_hist = [
        {
            "band": label(TOKEN_EDGES, b, "tokens"),
            "chunks": int((tw == b).sum()),
            "share": float((tw == b).mean()),
            "tokens": int(c["tokens"][tw == b].sum()),
        }
        for b in range(len(TOKEN_EDGES))
    ]
    for r in table:
        r["cost_to_include_this_band"] = prices(r["tokens"])
        r["cost_if_line_drawn_here"] = prices(r["if_line_drawn_here_tokens"])
    out = {
        "cases": n,
        "chunks": int(len(c["cash"])),
        "tokens": int(case_tokens.sum()),
        "recent_from_year": a.recent_from,
        "usd_inr_assumed": USD_INR,
        "case_length_bands": table,
        "chunk_length_histogram": chunk_hist,
        "all_cost": prices(int(case_tokens.sum())),
        "recent_cost": prices(int(case_tokens[case_year >= a.recent_from].sum())),
        "recent_cases": int((case_year >= a.recent_from).sum()),
    }
    (home / "missing_bands.json").write_text(json.dumps(out, indent=1))

    # examples: a few random cases per band, first 500 characters of the case's first chunk
    rng = np.random.default_rng(SEED)
    which = np.digitize(case_chars, CHAR_EDGES[1:])
    lines = [
        "# Examples from each length band of the missing cases\n",
        f"Seed {SEED}. {PER_BAND_EXAMPLES} cases drawn at random from each band; for each, the first 500 characters of the case's first chunk exactly as stored (the `Case: ... Court: ...` lines are part of the stored text). "
        "Length is the judgment text in characters. Nothing is edited. This file holds party names from public judgments, so it is kept outside the repo.\n",
    ]
    for b, row in enumerate(table):
        pool = np.flatnonzero(which == b)
        lines.append(
            f"\n## Band {b + 1}: {row['band']} ({row['cases']:,} cases, {row['share_of_cases']:.1%} of the missing cases)\n"
        )
        if not len(pool):
            continue
        for ci in sorted(
            rng.choice(pool, size=min(PER_BAND_EXAMPLES, len(pool)), replace=False)
        ):
            idx = np.flatnonzero(inv == ci)
            first_row = idx[
                np.argmin(c["row"][idx])
            ]  # lowest row = the case's first chunk in its file
            f = files[int(c["file"][first_row])]
            pf = pq.ParquetFile(f)
            starts = np.cumsum(
                [0]
                + [
                    pf.metadata.row_group(i).num_rows
                    for i in range(pf.metadata.num_row_groups)
                ]
            )
            r = int(c["row"][first_row])
            rg = int(np.searchsorted(starts, r, side="right") - 1)
            rec = (
                pf.read_row_group(
                    rg,
                    columns=[
                        "case_id",
                        "court",
                        "decision_date",
                        "year",
                        "text",
                        "total_chunks",
                    ],
                )
                .take([r - int(starts[rg])])
                .to_pylist()[0]
            )
            lines += [
                f"### {rec['case_id']}",
                f"{rec['court']} | decided {rec['decision_date']} | judgment text {int(case_chars[ci]):,} characters | {int(case_chunks[ci])} chunk(s)\n",
                "```",
                rec["text"][:500],
                "```\n",
            ]
    (home / "missing_bands_examples.md").write_text("\n".join(lines))
    print(f"wrote {home / 'missing_bands.json'} and missing_bands_examples.md")
    for r in table:
        print(
            f"{r['band']:>20} {r['cases']:>9,} cases {r['share_of_cases']:6.1%}  {r['tokens'] / 1e6:8.1f}M tokens {r['share_of_tokens']:6.1%}"
        )


if __name__ == "__main__":
    main()
