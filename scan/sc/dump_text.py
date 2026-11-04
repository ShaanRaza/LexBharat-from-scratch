#!/usr/bin/env python3
"""SC lane: copy the served SC chunks (read-only scroll) into a local sqlite file.

Plain words: the citation measurement needs each judgment's whole text many times over while patterns are
tuned. This reads kanoon_v1 once, one scroll at a time, and writes nothing to Qdrant. Output is scratch data,
never committed. Touches no pipeline step and no verifier check.

    python scan/sc/dump_text.py OUT.db [QDRANT_URL]
"""

from __future__ import annotations

import json
import sqlite3
import sys
import urllib.request
import zlib

from core.coverage import court_payload

FIELDS = [
    "chunk_id", "case_id", "chunk_index", "char_start", "char_end", "page_start",
    "section_type", "citation", "title", "year", "decision_date", "text",
]  # fmt: skip


def main(out: str, base: str = "http://localhost:7333") -> None:
    db = sqlite3.connect(out)
    db.execute("drop table if exists ch")
    db.execute(
        "create table ch(chunk_id text, case_id text, idx int, cs int, ce int, ps int, sect text,"
        " citation text, title text, year int, date text, text blob)"
    )
    offset = None
    total = 0
    while True:
        body = {
            "limit": 3000,
            "with_payload": FIELDS,
            "with_vector": False,
            "filter": {
                "must": [
                    {
                        "key": "court",
                        "match": {"value": court_payload("supreme_court")["court"]},
                    }
                ]
            },
        }
        if offset is not None:
            body["offset"] = offset
        req = urllib.request.Request(  # noqa: S310 (operator-supplied local URL)
            f"{base}/collections/kanoon_v1/points/scroll",
            json.dumps(body).encode(),
            {"content-type": "application/json"},
        )
        page = json.load(urllib.request.urlopen(req, timeout=120))["result"]  # noqa: S310
        rows = []
        for p in page["points"]:
            x = p["payload"]
            rows.append(
                (
                    x["chunk_id"], x["case_id"], x.get("chunk_index"), x.get("char_start"),
                    x.get("char_end"), x.get("page_start"), x.get("section_type"),
                    x.get("citation"), x.get("title"), x.get("year"), x.get("decision_date"),
                    zlib.compress((x.get("text") or "").encode()),
                )
            )  # fmt: skip
        db.executemany("insert into ch values (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        total += len(rows)
        offset = page.get("next_page_offset")
        if offset is None:
            break
    db.commit()
    print("chunks written:", total)


if __name__ == "__main__":
    main(*sys.argv[1:])
