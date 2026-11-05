"""Copy-step check for a per-court collection (A128): every court code the collection holds must be registered.

Plain words: a per-court collection is searched with one dense vector per model, each only among the
courts that model built. A point whose court code is NOT registered is reachable by keyword search
only, silently. This reads the collection's court codes (an indexed field, so one facet call) and
fails loudly if any is unregistered. Run it after copying a collection in. Copy instance only.

    python data/check_court_models.py legal_corpus_v2     # exit 1 if any code is unregistered
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from core import model_plan  # noqa: E402
from core.settings import Settings  # noqa: E402

COPY = "http://127.0.0.1:7333"


def http(path: str, body: dict | None = None, method: str = "POST"):
    req = urllib.request.Request(  # noqa: S310 - fixed loopback http base, so no file: or custom scheme
        COPY + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=300))  # noqa: S310


def present_codes(collection: str) -> dict[str, int]:
    total = http(f"/collections/{collection}/points/count", {"exact": True})["result"][
        "count"
    ]
    hits = http(
        f"/collections/{collection}/facet",
        {"key": "court_code", "limit": 200, "exact": True},
    )["result"]["hits"]
    codes = {h["value"]: h["count"] for h in hits}
    if total - sum(codes.values()):
        codes[""] = total - sum(codes.values())  # points with no court code (Acts)
    return codes


def main() -> None:
    collection = (
        sys.argv[1]
        if len(sys.argv) > 1
        else sys.exit("usage: check_court_models.py <collection>")
    )
    s = Settings(_env_file=None)
    codes = present_codes(collection)
    plan = model_plan.plan_for(s, collection)
    print(f"{collection}: court codes present {dict(sorted(codes.items()))}")
    if plan is None:
        print(
            "single-model collection (or not described per court): nothing to register"
        )
        return
    bad = model_plan.unregistered(s, collection, codes)
    print(f"model groups: {[(g.model, len(g.codes) + g.no_court) for g in plan]}")
    if bad:
        print(f"UNREGISTERED (reachable by keyword search only): {bad}")
        sys.exit(1)
    print("OK: every court code present is registered")


if __name__ == "__main__":
    main()
