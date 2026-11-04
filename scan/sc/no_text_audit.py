#!/usr/bin/env python3
"""SC lane, Task 1: are the 4,068 "no text" SC judgments reachable by the verifier?

Plain words: the owner's gap audit lists 4,068 SC case ids tagged
`no_opening_preview_and_no_text_in_app`. DATA-GAPS section 3 warns that if any of them is a served
record, verifier check 2 (record exists) passes while check 3 (quoted words match) has nothing to match.
This reads the SERVED collection (kanoon_v1, local, read-only) and the source parquet (read-only) and puts
each id in one of three boxes, then sweeps every served SC chunk for an empty or near-empty body
(the mechanism the warning is about). It writes nothing anywhere and spends nothing.

    python scan/sc/no_text_audit.py GAPS_CSV PARQUET [QDRANT_URL]

Touches no pipeline step; it is a data audit. Does not touch any verifier check.
"""

from __future__ import annotations

import collections
import csv
import json
import re
import sys
import urllib.request

COLLECTION = "kanoon_v1"
MIN_BODY_WORDS = (
    5  # a chunk body with fewer alphabetic words than this has nothing to quote
)


def body_words(text: str) -> int:
    """Alphabetic words after the 'Case: ... Section: ...' header (the part a quote can match)."""
    body = text.split("\n\n", 1)[1] if "\n\n" in text else text
    return len(re.findall(r"[A-Za-z]{2,}", body))


def classify(case_id: str, served: set[str], parquet_english: set[str]) -> str:
    if case_id in served:
        return (
            "served_with_text_in_source"
            if case_id in parquet_english
            else "served_not_english_in_source"
        )
    return "not_served"


def _scroll(base: str, offset):
    body = {
        "limit": 5000,
        "with_payload": ["case_id", "chunk_id", "text"],
        "with_vector": False,
    }
    if offset is not None:
        body["offset"] = offset
    req = urllib.request.Request(  # noqa: S310 (operator-supplied local URL)
        f"{base}/collections/{COLLECTION}/points/scroll",
        json.dumps(body).encode(),
        {"content-type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=120))["result"]  # noqa: S310


def main(gaps_csv: str, parquet: str, base: str = "http://localhost:7333") -> None:
    import duckdb  # imported here so the pure helpers above test without it

    ids = {
        r["id"]
        for r in csv.DictReader(open(gaps_csv))
        if r["gap_type"] == "judgments_no_text_supreme_court"
    }
    served: set[str] = set()
    tiny: list[str] = []
    total = 0
    offset = None
    while True:
        page = _scroll(base, offset)
        for p in page["points"]:
            pl = p["payload"]
            cid = pl.get("case_id") or ""
            if "_INSC_" not in cid:
                continue
            total += 1
            if cid in ids:
                served.add(cid)
            if body_words(pl.get("text") or "") < MIN_BODY_WORDS:
                tiny.append(pl.get("chunk_id"))
        offset = page.get("next_page_offset")
        if offset is None:
            break
    con = duckdb.connect()
    con.execute("create table nt(id varchar)")
    con.executemany("insert into nt values (?)", [(i,) for i in ids])
    en = {
        r[0]
        for r in con.execute(
            f"select distinct case_id from read_parquet('{parquet}') "  # noqa: S608
            "where language_code='en' and case_id in (select id from nt)"
        ).fetchall()
    }
    boxes = collections.Counter(classify(i, served, en) for i in ids)
    print("ids in audit:", len(ids))
    print("served SC points scanned:", total)
    print("boxes:", dict(boxes))
    print(
        f"served SC chunks with body under {MIN_BODY_WORDS} words:",
        len(tiny),
        tiny[:10],
    )


if __name__ == "__main__":
    main(*sys.argv[1:])
