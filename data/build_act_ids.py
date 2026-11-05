"""Build core/act_ids.json: every Act in the SERVED collection, by id, title, year and status (A144, pipeline step 5).

Plain words: step 5 scopes a section number to its Act (core/search.py), which needs the Act's id from its name
(core/act_ids.py). This reads the served collection once, read-only, and writes the list. It lists what is stored, it does not
claim what the product covers (core/coverage.json is the only source for that).

Reads the copy instance (127.0.0.1:7333), collection `research_v3` by default (`--collection` names another), the points
that carry an `act_id`. Read-only: it only scrolls. Re-run it after the
served collection changes (for example when state Acts are promoted into it).

    python data/build_act_ids.py            # writes core/act_ids.json
    python data/build_act_ids.py --check    # exits 1 if the file is not what the collection holds
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "core" / "act_ids.json"
COPY = "http://127.0.0.1:7333"
COLLECTION = "research_v3"  # the collection that will serve (A185); --collection reads another, read-only
FIELDS = ["act_id", "title", "year", "act_status"]


def _scroll(collection: str, body: dict) -> dict:
    req = urllib.request.Request(  # noqa: S310 - a fixed loopback http base
        f"{COPY}/collections/{collection}/points/scroll",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        out = json.load(r)["result"]
    time.sleep(0.1)
    return out


def build(collection: str = COLLECTION) -> dict:
    acts: dict[str, list] = {}
    off = None
    while True:
        body = {"limit": 2000, "with_payload": FIELDS, "with_vector": False}
        if off is not None:
            body["offset"] = off
        res = _scroll(collection, body)
        for p in res["points"]:
            pl = p["payload"]
            aid = pl.get("act_id")
            if aid and aid not in acts:
                acts[aid] = [
                    aid,
                    pl.get("title"),
                    str(pl.get("year") or ""),
                    pl.get("act_status") or "",
                ]
        off = res.get("next_page_offset")
        if off is None:
            break
    return {
        "_note": "Built by data/build_act_ids.py from the served collection; lists what is stored, not what the product covers.",
        "collection": collection,
        "acts": sorted(acts.values()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--collection", default=COLLECTION)
    a = ap.parse_args()
    built = build(a.collection)
    if a.check:
        have = json.loads(OUT.read_text())
        if have.get("acts") != built["acts"]:
            sys.exit("core/act_ids.json is out of date: re-run data/build_act_ids.py")
        print(f"core/act_ids.json is current ({len(built['acts'])} Acts)")
        return
    OUT.write_text(json.dumps(built, indent=0, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({len(built['acts'])} Acts)")


if __name__ == "__main__":
    main()
