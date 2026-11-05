#!/usr/bin/env python3
"""Build a NEW serving-candidate collection beside the live one (A146; CLAUDE.md section 6).

Plain words: copies every point, vectors and payload exactly as stored, from the source
collections into a new collection on the COPY instance (port 7333). Sources are only read.
Nothing is embedded or re-encoded, so there is no Voyage spend. The target must not be one of
the four protected originals and must not exist yet (or must be empty / resumed from its state
file). Switching which collection serves users is a separate config change (CORPUS_COLLECTION)
that this script never makes.

  .venv/bin/python data/build_promoted_collection.py --target research_v2 \\
      --source kanoon_v1 --source acts_noncentral_v1 --state DIR/research_v2.state.json

Pipeline step touched: step 5 (Search): the collection searched, once the owner switches to it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.sparse_fix import check_target  # noqa: E402

BATCH = 256
TEMPLATE = (
    "kanoon_v1"  # the config and payload indexes are copied from the live collection
)


def call(base, method, path, body=None, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(  # noqa: S310 (operator-supplied localhost URL)
                base + path,
                data=None if body is None else json.dumps(body).encode(),
                method=method,
                headers={"Content-Type": "application/json"},
            )
            return json.load(urllib.request.urlopen(req, timeout=600))["result"]  # noqa: S310
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                sys.exit(f"ABORT: {method} {path} failed after {retries} tries: {exc}")
            time.sleep(3 * (attempt + 1))


def create_like(base, target, template):
    info = call(base, "GET", f"/collections/{template}")
    params = info["config"]["params"]
    call(
        base,
        "PUT",
        f"/collections/{target}",
        {
            "vectors": params["vectors"],
            "sparse_vectors": params["sparse_vectors"],
            "on_disk_payload": params["on_disk_payload"],
            "hnsw_config": {
                k: info["config"]["hnsw_config"][k] for k in ("m", "ef_construct")
            },
        },
    )
    for field, spec in info["payload_schema"].items():
        call(
            base,
            "PUT",
            f"/collections/{target}/index?wait=true",
            {"field_name": field, "field_schema": spec["data_type"]},
        )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--source", action="append", required=True)
    ap.add_argument("--state", required=True, help="resume file (JSON)")
    ap.add_argument("--url", default="http://localhost:7333")
    a = ap.parse_args(argv)
    target, base = check_target(
        a.target, a.url
    )  # refuses originals and the 6333 instance
    for s in a.source:
        if s == target:
            sys.exit("ABORT: a source cannot be the target.")
    state = (
        json.load(open(a.state))
        if os.path.exists(a.state)
        else {"done": {}, "offset": {}}
    )
    existing = {c["name"] for c in call(base, "GET", "/collections")["collections"]}
    if target not in existing:
        create_like(base, target, TEMPLATE)
        print(f"created {target} like {TEMPLATE}", flush=True)
    elif not state["offset"] and not state["done"]:
        sys.exit(
            f"ABORT: {target} already exists and there is no state file; refusing to mix."
        )
    for src in a.source:
        if state["done"].get(src):
            print(f"{src}: already copied ({state['done'][src]:,})", flush=True)
            continue
        off, n, t0 = (
            state["offset"].get(src),
            state["done"].get(src + "#n", 0),
            time.time(),
        )
        while True:
            body = {"limit": BATCH, "with_payload": True, "with_vector": True}
            if off is not None:
                body["offset"] = off
            res = call(base, "POST", f"/collections/{src}/points/scroll", body)
            pts = [
                {"id": p["id"], "vector": p["vector"], "payload": p["payload"]}
                for p in res["points"]
            ]
            if pts:
                call(
                    base,
                    "PUT",
                    f"/collections/{target}/points?wait=true",
                    {"points": pts},
                )
            n += len(pts)
            off = res.get("next_page_offset")
            state["offset"][src], state["done"][src + "#n"] = off, n
            json.dump(state, open(a.state, "w"))
            if n % (BATCH * 40) < BATCH:
                print(
                    f"  {src}: {n:,} copied, {n / max(time.time() - t0, 1):.0f}/s",
                    flush=True,
                )
            if off is None:
                break
        state["done"][src] = n
        json.dump(state, open(a.state, "w"))
        print(f"{src}: copied {n:,}", flush=True)
    total = call(base, "POST", f"/collections/{target}/points/count", {"exact": True})[
        "count"
    ]
    want = sum(
        call(base, "POST", f"/collections/{s}/points/count", {"exact": True})["count"]
        for s in a.source
    )
    print(
        f"target {total:,} points, sources {want:,}: {'MATCH' if total == want else 'MISMATCH'}"
    )
    return 0 if total == want else 1


if __name__ == "__main__":
    raise SystemExit(main())
