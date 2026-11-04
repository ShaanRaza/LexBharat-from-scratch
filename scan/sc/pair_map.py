"""Collect the Court's own parallel citations from judgment headnotes, with which cases print each.

Plain words: a headnote lists the cases the judgment relies on, each with two citations joined by a
colon: `Brij Mohan Lal v. Union of India (2002) 5 SCC 1 : [2002] 3 SCR 810`. This script reads the first
15,000 characters of every served case, keeps each such pair whose SCR side is a held record, and records
WHICH cases printed it. A pair printed by one case may be an OCR slip or a typo; a pair printed by many
independent cases is far safer. It writes a scratch file; nothing is built from it and no collection is touched.

Output (pickle): {"scc": {key: {target_case_id: [citing_case_id, ...]}}, "air": {...}}
Usage: python scan/sc/pair_map.py SC_TEXT.db OUT.pkl
Pipeline: none of the 11 steps; offline measurement.
"""

from __future__ import annotations

import collections
import pickle
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import measure_case_law_table as t  # noqa: E402
import measure_refs  # noqa: E402


def main(db_path: str, out: str) -> None:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    by_key, _ = t.build_lookup(db)
    cases = [
        r[0] for r in db.execute("select distinct case_id from ch order by case_id")
    ]
    res: dict[str, dict] = {
        "scc": collections.defaultdict(lambda: collections.defaultdict(list)),
        "air": collections.defaultdict(lambda: collections.defaultdict(list)),
    }
    for cid in cases:
        rows = db.execute(
            "select chunk_id, idx, cs, ce, text from ch where case_id=? and idx<=?",
            (cid, t.MAX_IDX),
        ).fetchall()
        reg = re.sub(r"[ \t]+", " ", t.region_of(measure_refs.rebuild(rows)))
        for kind, okey, skey in t.pairs_in(reg):
            if kind not in res:
                continue
            _, y, supp, vol, _addl, page = skey
            if vol is None:
                continue
            tgt = by_key.get(("scr", y, supp, vol, False, page))
            if tgt and tgt != cid:  # a case's own pair says nothing independent
                res[kind][okey][tgt].append(cid)
    plain = {k: {kk: dict(v) for kk, v in d.items()} for k, d in res.items()}
    Path(out).write_bytes(pickle.dumps(plain))
    print({k: len(v) for k, v in plain.items()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
