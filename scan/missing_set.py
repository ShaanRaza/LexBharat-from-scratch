"""What the 2,865,144 whole-missing English cases are made of (A141 cost picture). Pipeline step 5 (Search) measurement.

Read-only and local. It reuses the lane A scan's saved hashes (scan/coverage_gap.py, DATA-GAPS section 19), so the
missing set is the SAME set section 19 counted, and it checks that against results.json before it reports anything.
It adds what section 19 did not record: how long the missing chunks are (the parquet `text`, the thing that would be
embedded), how many chunks a missing case has, the decision year, and two calibration sets that turn characters into
Voyage tokens using spend that was already measured (the Kerala re-embed, the national-court embed, A129).

Nothing is written to any Qdrant, no Voyage call is made, no cost. The only network reads are scrolls of the staged
INSC collection (A129) on the COPY instance (127.0.0.1:7333).

  python -m scan.missing_set                 # everything, writes <home>/missing_set.json
  python -m scan.missing_set --limit-files 2 # a quick trial on two parquet files (the integrity check is skipped)
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import numpy as np

from scan import coverage_gap as g

COPY = "http://127.0.0.1:7333"
SC_STAGING = "kanoon_sc_new_v1"
SERVING = "kanoon_v1"
KERALA_META = Path.home() / "qdrant-kanoon" / "kerala_fix" / "new_meta.json"
RECENT_FROM_YEAR = 2016  # "the last ten years": decisions from 2016 on (2016-2025, plus anything dated 2026)
HIST_BINS = [
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4", 4, 4),
    ("5-9", 5, 9),
    ("10-19", 10, 19),
    ("20+", 20, None),
]
LEDGER = Path.home() / "qdrant-kanoon" / "kerala_fix" / "token_ledger.jsonl"


# --- pure aggregation (tested without any data) --------------------------------------------------------------
def aggregate(
    chash: np.ndarray,
    cash: np.ndarray,
    code: np.ndarray,
    chars: np.ndarray,
    year: np.ndarray,
) -> dict:
    """Per court code: whole cases, chunks, characters, chunks per case, and the same by decision year.

    A chunk id seen twice counts once (the scan's `compare` does the same). `year` 0 means the parquet gave none."""
    _, first = np.unique(chash, return_index=True)
    ca, co, nc, yr = cash[first], code[first], chars[first], year[first]
    out: dict = {}
    for k in np.unique(co):
        m = co == k
        ca_k, nc_k, yr_k = ca[m], nc[m], yr[m]
        cases, inv, per_case = np.unique(ca_k, return_inverse=True, return_counts=True)
        case_year = np.zeros(len(cases), dtype=yr_k.dtype)
        case_year[inv] = yr_k
        hist = {
            label: int(((per_case >= lo) & ((per_case <= hi) if hi else True)).sum())
            for label, lo, hi in HIST_BINS
        }
        by_year: dict[int, list[int]] = {}
        for y in np.unique(yr_k):
            sy, sc = yr_k == y, case_year == y
            by_year[int(y)] = [int(sc.sum()), int(sy.sum()), int(nc_k[sy].sum())]
        out[int(k)] = {
            "cases": int(len(cases)),
            "chunks": int(m.sum()),
            "chars": int(nc_k.sum()),
            "chunks_per_case_mean": float(m.sum() / len(cases)),
            "chunks_per_case_median": float(np.median(per_case)),
            "chunks_per_case_max": int(per_case.max()),
            "chunks_per_case_hist": hist,
            "chars_per_chunk_mean": float(nc_k.mean()),
            "chars_per_chunk_median": float(np.median(nc_k)),
            "by_year": by_year,
        }
    return out


# --- reading the parquet side ----------------------------------------------------------------------------------
def _read_cols(pf, rows: np.ndarray, cols: list[str]):
    """text length and year for the given parquet row positions, reading only the row groups that contain one."""
    import pyarrow.compute as pc

    n = pf.metadata.num_rows
    starts = np.cumsum(
        [0]
        + [pf.metadata.row_group(i).num_rows for i in range(pf.metadata.num_row_groups)]
    )
    if starts[-1] != n:
        raise SystemExit("row-group sizes do not add up to the file row count")
    chars = np.zeros(len(rows), dtype=np.int32)
    year = np.zeros(len(rows), dtype=np.int16)
    which = np.searchsorted(starts, rows, side="right") - 1
    for rg in np.unique(which):
        t = pf.read_row_group(int(rg), columns=cols)
        sel = np.flatnonzero(which == rg)
        pos = rows[sel] - starts[rg]
        chars[sel] = np.asarray(
            pc.utf8_length(t.column("text")).to_numpy(zero_copy_only=False)
        )[pos]
        if "year" in cols:
            y = t.column("year").fill_null(0).to_numpy(zero_copy_only=False)
            year[sel] = y[pos]
    return chars, year


def ledger_tokens(prefix: str) -> int:
    """Tokens the Voyage client recorded for rows whose tag starts with `prefix` (the embed batches, not the checks)."""
    return sum(
        r["tokens"]
        for r in map(json.loads, LEDGER.read_text().splitlines())
        if r["tag"].startswith(prefix)
    )


def load_q(home: Path):
    ch, ca = [], []
    for coll in g.COLLECTIONS:
        for f in sorted((home / "scan" / coll).glob("page_*.npz")):
            z = np.load(f)
            ch.append(z["chash"])
            ca.append(z["cash"])
    return np.unique(np.concatenate(ch)), np.unique(np.concatenate(ca))


def copy_post(path: str, body: dict) -> dict:
    """Read-only POST to the copy instance (scroll and count only)."""
    if not (path.endswith("/points/scroll") or path.endswith("/points/count")):
        raise SystemExit(f"refused: {path}")
    req = urllib.request.Request(  # noqa: S310 - fixed loopback http base
        COPY + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["result"]  # noqa: S310


def scroll_chunk_ids(coll: str) -> list[str]:
    ids, off = [], None
    while True:
        body = {"limit": 2000, "with_payload": ["chunk_id"], "with_vector": False}
        if off is not None:
            body["offset"] = off
        r = copy_post(f"/collections/{coll}/points/scroll", body)
        ids += [p["payload"]["chunk_id"] for p in r["points"]]
        off = r.get("next_page_offset")
        if off is None:
            return ids


def main() -> None:
    import pyarrow.parquet as pq

    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=str(g.HOME_DEFAULT))
    ap.add_argument("--limit-files", type=int, default=0)
    a = ap.parse_args()
    home = Path(a.home)
    t0 = time.time()
    results = json.loads((home / "results.json").read_text())
    codes = json.loads((home / "parquet" / "codes.json").read_text())
    langs = json.loads((home / "parquet" / "langs.json").read_text())
    en = langs["en"]
    Q_ch, Q_ca = load_q(home)
    print(
        f"Qdrant side loaded: {len(Q_ch):,} chunk hashes, {len(Q_ca):,} case hashes ({time.time() - t0:.0f}s)",
        flush=True,
    )

    files = sorted(g.PARQUET_DIR.glob("in_*_judgments.parquet"))
    if a.limit_files:
        files = files[: a.limit_files]
    sc_idx = codes.index("INSC")
    kl_idx = codes.index("KLHC")
    acc = {k: [] for k in ("chash", "cash", "code", "chars", "year")}
    sc_only_hash: list[
        np.ndarray
    ] = []  # every English parquet-only SC chunk, whole case missing or not
    sc_rows: list[tuple[str, np.ndarray, np.ndarray]] = []
    kerala_hash = None
    for f in files:
        z = np.load(home / "parquet" / (f.stem + ".npz"))
        ch, ca, co, lg = z["chash"], z["cash"], z["code"], z["lang"]
        pf = pq.ParquetFile(f)
        if pf.metadata.num_rows != len(ch):
            raise SystemExit(
                f"{f.name}: parquet has {pf.metadata.num_rows:,} rows, the scan saved {len(ch):,}"
            )
        only_p = ~np.isin(ch, Q_ch)
        is_en = lg == en
        whole = only_p & ~np.isin(ca, Q_ca)
        cand = np.flatnonzero(whole & is_en)
        sc_mask = only_p & is_en & (co == sc_idx)
        if sc_mask.any():
            sc_only_hash.append(ch[sc_mask])
            sc_rows.append((f.name, ch[sc_mask], np.flatnonzero(sc_mask)))
        if len(cand):
            chars, year = _read_cols(pf, cand, ["text", "year"])
            acc["chash"].append(ch[cand])
            acc["cash"].append(ca[cand])
            acc["code"].append(co[cand])
            acc["chars"].append(chars)
            acc["year"].append(year)
        print(
            f"{f.name}: {len(ch):,} rows, {len(cand):,} in whole-missing English cases ({time.time() - t0:.0f}s)",
            flush=True,
        )
        if kl_idx in set(np.unique(co).tolist()):
            kerala_hash = (f, ch)
    cat = {k: np.concatenate(v) if v else np.array([]) for k, v in acc.items()}
    agg = aggregate(cat["chash"], cat["cash"], cat["code"], cat["chars"], cat["year"])
    named = {codes[k]: v for k, v in agg.items()}
    tot_cases = sum(v["cases"] for v in named.values())
    tot_chunks = sum(v["chunks"] for v in named.values())
    exp_cases = sum(c["whole_missing_english_cases"] for c in results["codes"].values())
    exp_chunks = sum(
        c["whole_missing_english_chunks"] for c in results["codes"].values()
    )
    full = not a.limit_files
    if full and (tot_cases, tot_chunks) != (exp_cases, exp_chunks):
        raise SystemExit(
            f"INTEGRITY FAILED: got {tot_cases:,} cases / {tot_chunks:,} chunks, section 19 has {exp_cases:,} / {exp_chunks:,}"
        )
    out: dict = {
        "full_run": full,
        "integrity_vs_section_19": {
            "cases": [tot_cases, exp_cases],
            "chunks": [tot_chunks, exp_chunks],
            "matches": (tot_cases, tot_chunks) == (exp_cases, exp_chunks),
        },
        "recent_from_year": RECENT_FROM_YEAR,
        "codes": named,
    }

    # --- calibration 1: the INSC embed (A129): same ids? and tokens per character ----------------------
    if sc_only_hash:
        P = np.unique(np.concatenate(sc_only_hash))
        staged = scroll_chunk_ids(SC_STAGING)
        E = np.array([g.H(c) for c in staged], dtype=np.uint64)
        both = np.intersect1d(P, E)
        # how many of the staged ids are in the serving collection now (the copy instance)
        in_serving = 0
        for i in range(0, len(staged), 500):
            in_serving += copy_post(
                f"/collections/{SERVING}/points/count",
                {
                    "exact": True,
                    "filter": {
                        "must": [
                            {"key": "chunk_id", "match": {"any": staged[i : i + 500]}}
                        ]
                    },
                },
            )["count"]
        # characters of exactly the chunks A129 embedded
        sc_chars = 0
        for name, hs, rows in sc_rows:
            pf = pq.ParquetFile(g.PARQUET_DIR / name)
            c, _ = _read_cols(pf, rows, ["text"])
            sc_chars += int(c.sum())
        tokens = ledger_tokens("sc embed batch")
        out["supreme_court_match"] = {
            "parquet_only_english_chunks": int(len(P)),
            "staged_by_a129": len(staged),
            "staged_unique": int(len(np.unique(E))),
            "same_id_in_both": int(len(both)),
            "staged_ids_now_in_serving_kanoon_v1": in_serving,
            "chars_of_those_chunks": sc_chars,
            "tokens_embedded_ledger": tokens,
            "tokens_per_char": tokens / sc_chars,
            "tokens_per_chunk": tokens / len(P),
        }

    # --- calibration 2: the Kerala re-embed: tokens per character of Kerala text --------------------------
    if full and kerala_hash and KERALA_META.exists():
        f, ch = kerala_hash
        meta = json.loads(KERALA_META.read_text())["meta"]
        want = np.array([g.H(f"{c}_{i:03d}") for c, i, _ in meta], dtype=np.uint64)
        rows = np.flatnonzero(np.isin(ch, want))
        pf = pq.ParquetFile(f)
        chars, _ = _read_cols(pf, rows, ["text"])
        tokens = ledger_tokens("kerala batch")
        out["kerala_calibration"] = {
            "reembedded_chunks": len(meta),
            "found_in_parquet": int(len(rows)),
            "chars": int(chars.sum()),
            "tokens_ledger": tokens,
            "tokens_per_char": tokens / int(chars.sum()),
            "tokens_per_chunk": tokens / len(meta),
            "chars_per_chunk": float(chars.sum() / len(rows)),
        }
    p = home / ("missing_set.json" if full else "missing_set_trial.json")
    p.write_text(json.dumps(out, indent=1))
    print(f"wrote {p} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
