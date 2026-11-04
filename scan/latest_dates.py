"""Latest content held in the SERVED collection, per kind (A148). Read-only.

Plain words: the data-as-of line must describe the content a page shows, so this finds the
newest judgment `decision_date` and the newest Act `year` in `kanoon_v1`. Measured 4 Nov 2026:
newest judgment 2025-11-06 (35,688 cases, every date parsed); newest Act year 2025 (an Act carries
a year, and only 600 of 1,568 carry an enactment_date). The numbers go into
data/coverage_report.py (DATA_AS_OF), which writes core/coverage.json.

    .venv/bin/python -m scan.latest_dates            # prints the two values

Reads the copy instance only (port 7333); refuses the original (CLAUDE.md section 6)."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime

from core.coverage import court_payload

URL = "http://127.0.0.1:7333"
COLLECTION = "kanoon_v1"


def _scroll(flt: dict, fields: list[str]):
    if ":6333" in URL:
        raise SystemExit("refusing the original instance (port 6333)")
    offset = None
    while True:
        body = {
            "limit": 5000,
            "with_payload": {"include": fields},
            "with_vector": False,
            "filter": flt,
        }
        if offset:
            body["offset"] = offset
        req = urllib.request.Request(  # noqa: S310 - fixed loopback http base
            f"{URL}/collections/{COLLECTION}/points/scroll",
            json.dumps(body).encode(),
            {"content-type": "application/json"},
        )
        res = json.load(urllib.request.urlopen(req, timeout=60))["result"]  # noqa: S310
        yield from (p["payload"] for p in res["points"])
        offset = res.get("next_page_offset")
        if not offset:
            return
        time.sleep(0.2)


def latest_judgment() -> str:
    flt = {
        "must": [
            {
                "key": "court",
                "match": {"value": court_payload("supreme_court")["court"]},
            }
        ]
    }
    days = [
        datetime.strptime(p["decision_date"], "%d-%m-%Y").date()
        for p in _scroll(flt, ["decision_date"])
    ]
    return max(days).isoformat()


def latest_act_year() -> str:
    flt = {"must": [{"key": "jurisdiction", "match": {"value": "central"}}]}
    years = [
        int(p["year"])
        for p in _scroll(flt, ["year"])
        if str(p.get("year") or "").isdigit()
    ]
    return str(max(years))


if __name__ == "__main__":
    print(json.dumps({"judgments": latest_judgment(), "acts": latest_act_year()}))
    sys.exit(0)
