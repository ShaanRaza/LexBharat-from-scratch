"""Write `court_code` into a collection's payload, derived from the record id (CLAUDE.md section 6).

Plain words: a judgment's record id names its court; the `court` label is missing on 0.58% of
judgments and spelled another way on 0.21% (measured 3 Nov 2026), and a filter on the label
silently drops those rows. This adds `court_code` (the id prefix, INSC for the Supreme Court)
beside the label. The label is NEVER changed or removed: a few alias labels may be
historically real. A point whose id matches no prefix (an Act, say) is left alone.

Pipeline step touched: 5 (Search): adapters/qdrant.py matches a court label OR this code.
Writes go to the COPY instance only (port 7333), never to legal_corpus_v1, legal_corpus_v2 or
acts_india. Dry run by default; --apply writes. Idempotent: a point that already holds the
right code is skipped, so a rerun changes nothing.

    python data/add_court_code.py kanoon_v1            # report only
    python data/add_court_code.py kanoon_v1 --apply    # write court_code, create the index
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from core import court_id  # noqa: E402

COPY = "http://127.0.0.1:7333"
FORBIDDEN = {"legal_corpus_v1", "legal_corpus_v2", "acts_india"}  # the originals
PAGE = 5000
BATCH = 5000


@dataclass
class Plan:
    updates: dict[str, list] = field(
        default_factory=lambda: collections.defaultdict(list)
    )
    kinds: collections.Counter = field(default_factory=collections.Counter)
    codes: collections.Counter = field(default_factory=collections.Counter)
    already: int = 0
    conflicts: list = field(default_factory=list)  # (point id, chunk_id, label, code)
    scanned: int = 0

    @property
    def to_write(self) -> int:
        return sum(len(v) for v in self.updates.values())

    @property
    def label_filter_would_drop(self) -> int:
        """Points of a known court a label-only filter would not return."""
        return sum(self.kinds[k] for k in ("missing", "alias", "other_court"))


def plan(points: Iterable[dict]) -> Plan:
    """Pure: what to write, and how the stored labels relate to the ids. `points` are
    {"id", "payload": {"chunk_id", "court", "court_code"}}."""
    pl = Plan()
    for p in points:
        pl.scanned += 1
        pay = p.get("payload") or {}
        code = court_id.code_from_record_id(pay.get("chunk_id"))
        kind = court_id.classify_label(pay.get("chunk_id"), pay.get("court"))
        pl.kinds[kind] += 1
        if code is None:
            continue  # not a judgment of a known court: nothing to derive, nothing to flag
        pl.codes[code] += 1
        if kind == "other_court":
            pl.conflicts.append((p["id"], pay.get("chunk_id"), pay.get("court"), code))
        if pay.get("court_code") == code:
            pl.already += 1
        else:
            pl.updates[code].append(p["id"])
    return pl


def http(path: str, body: dict | None = None, method: str = "POST", timeout: int = 900):
    req = urllib.request.Request(
        COPY + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout))  # noqa: S310


def scan(collection: str) -> Iterable[dict]:
    off = None
    while True:
        r = http(
            f"/collections/{collection}/points/scroll",
            {
                "limit": PAGE,
                "offset": off,
                "with_payload": ["chunk_id", "court", "court_code"],
                "with_vector": False,
            },
        )["result"]
        yield from r["points"]
        off = r["next_page_offset"]
        if off is None:
            return


def apply(collection: str, pl: Plan) -> None:
    http(
        f"/collections/{collection}/index?wait=true",
        {"field_name": "court_code", "field_schema": "keyword"},
        "PUT",
    )
    for code, ids in pl.updates.items():
        for i in range(0, len(ids), BATCH):
            http(
                f"/collections/{collection}/points/payload?wait=true",
                {"payload": {"court_code": code}, "points": ids[i : i + BATCH]},
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("collection")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.collection in FORBIDDEN:
        sys.exit(
            f"REFUSED: {a.collection} is an original; this writes to the copy instance only."
        )
    names = {
        c["name"] for c in http("/collections", method="GET")["result"]["collections"]
    }
    if a.collection not in names:
        sys.exit(f"no collection {a.collection!r} on the copy instance")
    pl = plan(scan(a.collection))
    k = pl.kinds
    print(f"{a.collection}: {pl.scanned:,} points scanned")
    print(f"  id names a court: {sum(pl.codes.values()):,} points {dict(pl.codes)}")
    print(
        f"  label vs id: usual {k['usual']:,} | alias {k['alias']:,} | missing {k['missing']:,} | other court {k['other_court']:,} | id names no court (left alone) {k['unknown_id']:,}"
    )
    print(
        f"  a label-only filter would drop {pl.label_filter_would_drop:,} of those points"
    )
    print(
        f"  already carry the right court_code: {pl.already:,} | to write: {pl.to_write:,}"
    )
    if pl.conflicts:
        print(
            f"  label names ANOTHER court than the id ({len(pl.conflicts)}), first 5: {pl.conflicts[:5]}"
        )
    if not a.apply:
        print("DRY RUN: nothing written. Re-run with --apply.")
        return
    apply(a.collection, pl)
    r = http(
        f"/collections/{a.collection}/points/count",
        {"exact": True, "filter": {"must_not": [{"is_empty": {"key": "court_code"}}]}},
    )
    have = r["result"]["count"]
    expect = sum(pl.codes.values())
    print(
        f"WROTE: {a.collection} now has {have:,} points with court_code (expected {expect:,}) -> {'OK' if have == expect else 'MISMATCH'}"
    )
    sys.exit(0 if have == expect else 1)


if __name__ == "__main__":
    main()
