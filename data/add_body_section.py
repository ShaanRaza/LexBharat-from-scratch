#!/usr/bin/env python3
"""Add `body_section`, `body_kind`, `series_section`, `series_inherited` to the Act chunks of a copy
collection (A186). PAYLOAD ONLY: no vector is read or written, nothing is embedded. Guard as in
data/sparse_fix.py: --target is required, the four originals and port 6333 are refused.

  body_section / body_kind   read from the chunk's own first heading (data/body_section.py); None when
                             the body does not start with a heading (a continuation).
  series_section             body_section, or for a continuation the body_section of the nearest
                             PRECEDING chunk of the same Act (by chunk_index) with the same stored
                             label; None if there is none. series_inherited says which.
  Supplement chunks (source_kind supplement_indiacode) have no heading line in their text, so their
  body_section is the Act's own printed number already stored in section_number / section_type.

    .venv/bin/python data/add_body_section.py --target research_v3 --dry-run     # counts only
    .venv/bin/python data/add_body_section.py --target research_v3
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.body_section import all_headings, parse_body_section  # noqa: E402
from data.build_promoted_collection import call  # noqa: E402
from data.build_research_v3 import heading_section  # noqa: E402
from data.sparse_fix import check_target  # noqa: E402

FIELDS = (
    "body_section",
    "body_kind",
    "body_headings",
    "series_section",
    "series_inherited",
)


def supplement_fields(pl: dict) -> dict:
    kind = pl.get("section_type")
    hs = heading_section(pl)
    bk = {"section": "section", "article": "section", "rule": "order_rule"}.get(
        kind,
        "schedule" if kind in ("schedule", "schedule_article", "appendix") else "none",
    )
    bs = hs if bk in ("section", "order_rule", "schedule") and hs else None
    return {
        "body_section": bs,
        "body_kind": bk,
        "body_headings": [bs] if bs else [],
        "series_section": bs,
        "series_inherited": False,
    }


def compute(points: list[dict]) -> dict[int, dict]:
    """point id -> new payload fields, for every Act chunk in `points` (those with section_number)."""
    out: dict[int, dict] = {}
    by_act = collections.defaultdict(list)
    for p in points:
        pl = p["payload"]
        if "section_number" not in pl:
            continue  # a judgment
        if pl.get("source_kind") == "supplement_indiacode":
            out[p["id"]] = supplement_fields(pl)
        else:
            by_act[pl["act_id"]].append(p)
    for ps in by_act.values():
        ps.sort(key=lambda p: int(p["payload"].get("chunk_index") or 0))
        prev = None
        for p in ps:
            pl = p["payload"]
            bs, bk = parse_body_section(pl.get("text", ""), pl.get("section_type"))
            f = {
                "body_section": bs,
                "body_kind": bk,
                "body_headings": all_headings(
                    pl.get("text", ""), bs if bk == "section" else None
                ),
                "series_section": bs,
                "series_inherited": False,
            }
            if (
                bs is None
                and prev is not None
                and (prev["payload"].get("section_number") or "")
                == (pl.get("section_number") or "")
            ):
                f["series_section"] = out[prev["id"]]["body_section"]
                f["series_inherited"] = f["series_section"] is not None
            out[p["id"]] = f
            if bs is not None:
                prev = p
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--target", default=None)
    ap.add_argument("--url", default="http://localhost:7333")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    target, base = check_target(a.target, a.url)
    if target == "kanoon_v1":
        sys.exit("ABORT: kanoon_v1 is the source, not a target.")
    pts, off = [], None
    flt = {"must": [{"key": "doc_type", "match": {"value": "legislation"}}]}
    while True:
        body = {
            "limit": 2000,
            "with_vector": False,
            "filter": flt,
            "with_payload": [
                "act_id",
                "section_number",
                "section_type",
                "chunk_index",
                "text",
                "source_kind",
                "order_number",
                "order_variant",
                "heading_section",
            ],
        }
        if off is not None:
            body["offset"] = off
        r = call(base, "POST", f"/collections/{target}/points/scroll", body)
        pts += r["points"]
        off = r.get("next_page_offset")
        if off is None:
            break
    fields = compute(pts)
    print(
        f"{len(pts):,} Act chunks read; fields computed for {len(fields):,}", flush=True
    )
    if a.dry_run:
        return 0
    ids = list(fields)
    for i in range(0, len(ids), 500):
        ops = [
            {"set_payload": {"payload": fields[k], "points": [k]}}
            for k in ids[i : i + 500]
        ]
        call(
            base,
            "POST",
            f"/collections/{target}/points/batch?wait=true",
            {"operations": ops},
        )
        if (i // 500) % 20 == 0:
            print(f"  {i + len(ops):,} written", flush=True)
    for f in ("body_section", "series_section", "body_headings"):
        call(
            base,
            "PUT",
            f"/collections/{target}/index?wait=true",
            {"field_name": f, "field_schema": "keyword"},
        )
    print("done; indexes body_section, series_section created")
    json.dump({"written": len(ids)}, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
