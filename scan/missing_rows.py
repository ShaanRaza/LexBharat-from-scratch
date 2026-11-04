"""Cache WHERE the whole-missing English chunks sit in the parquet files (A141), so later samplers need no rescan.

For each judgments parquet file this writes `<home>/missing_rows/<stem>.npy`: the row positions of the chunks that are in
whole-missing English cases (the set DATA-GAPS section 19 counted; `scan/missing_set.py` checks the totals). It is the
same test `scan/missing_set.py` applies, saved instead of aggregated. Read only, local, no Qdrant call, no cost.

  python -m scan.missing_rows
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from scan import coverage_gap as g
from scan import missing_set as ms


def load_rows(home: Path, stem: str) -> np.ndarray:
    return np.load(home / "missing_rows" / f"{stem}.npy")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=str(g.HOME_DEFAULT))
    a = ap.parse_args()
    home = Path(a.home)
    out = home / "missing_rows"
    out.mkdir(exist_ok=True)
    en = json.loads((home / "parquet" / "langs.json").read_text())["en"]
    q_ch, q_ca = ms.load_q(home)
    t0 = time.time()
    total = 0
    for f in sorted(g.PARQUET_DIR.glob("in_*_judgments.parquet")):
        dst = out / f"{f.stem}.npy"
        if dst.exists():
            total += len(np.load(dst))
            continue
        z = np.load(home / "parquet" / f"{f.stem}.npz")
        ch, ca, lg = z["chash"], z["cash"], z["lang"]
        rows = np.flatnonzero(~np.isin(ch, q_ch) & (lg == en) & ~np.isin(ca, q_ca))
        np.save(dst, rows)
        total += len(rows)
        print(f"{f.name}: {len(rows):,} ({time.time() - t0:.0f}s)", flush=True)
    expect = json.loads((home / "missing_set.json").read_text())[
        "integrity_vs_section_19"
    ]["chunks"][1]
    # rows are chunk ROWS; section 19 counts distinct chunk ids, so a repeated id would make this larger, never smaller
    print(f"{total:,} rows cached (section 19: {expect:,} distinct chunks)")
    if total < expect:
        raise SystemExit("fewer rows than section 19 counts; the cache is wrong")


if __name__ == "__main__":
    main()
