"""Shared READ-ONLY client for the ORIGINAL Qdrant (6333). Whitelisted paths, one request at a time, 0.25 s pause,
HARD STOP (no retry) on any failure or > 60 s (raised from 20 s on 3 Nov 2026 at the owner's instruction). Nothing is ever written."""

import json
import re
import sys
import time
import urllib.request

SRC = "http://localhost:6333"
HARD = 60
PAUSE = 0.25
LOG = []
OK_RE = re.compile(
    r"^/collections/(legal_corpus_v1|legal_corpus_v2|acts_india)(/points(/count|/scroll|/query)?|/facet)$"
)


def q(path, body, tag):
    if not OK_RE.match(path):
        sys.exit(f"refused non-whitelisted path {path}")
    t0 = time.time()
    req = urllib.request.Request(
        SRC + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=HARD).read()
    except Exception as e:  # noqa: BLE001  any failure is a hard stop, never a retry
        print(
            f"\nHARD STOP at [{tag}] after {time.time() - t0:.1f}s: {e}\nNo retry. Nothing written."
        )
        sys.exit(3)
    dt = time.time() - t0
    LOG.append((tag, round(dt, 3)))
    if dt > HARD:
        print(f"\nHARD STOP [{tag}] took {dt:.1f}s")
        sys.exit(3)
    time.sleep(PAUSE)
    return json.loads(raw)["result"]


def count(c, flt, tag):
    return q(
        f"/collections/{c}/points/count",
        {"exact": True, **({"filter": flt} if flt else {})},
        tag,
    )["count"]


def facet(c, key, tag, flt=None, limit=1000):
    r = q(
        f"/collections/{c}/facet",
        {"key": key, "limit": limit, "exact": True, **({"filter": flt} if flt else {})},
        tag,
    )
    return [(h["value"], h["count"]) for h in r["hits"]]


def M(k, v):
    return {"must": [{"key": k, "match": {"value": v}}]}
