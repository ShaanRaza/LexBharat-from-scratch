"""Exact-section lookup before/after (A184). READ ONLY: scrolls and queries two collections on the copy
instance (port 7333); the only vendor call is embedding ~40 short questions with the live query model
(voyage-4, A126). Mirrors the layers of core/search.py `_law_hits`:

  kanoon_v1  : resolve_act + plain_section -> hard filter (act_id, section_number); an unresolved Act
               (the Constitution) falls to the 'section signal' layer: unfiltered top 10 + the best
               2 chunks that carry that section number in ANY Act.
  new        : hard filter (act_id, heading_section) -- the proposed lookup. For an Act the new
               collection does not carry under a new id the id is the same.

For each pair the question is "What does Section N of the <Act> say?". PASS@cand: the phrase is in the
text of the filter's candidate set. PASS@5: it is in one of the top 5 candidates ranked by the dense query
vector. Phrases are hand-written from the PDFs (evals/section_lookup_set.jsonl).

    .venv/bin/python -m evals.section_lookup --out results.json
"""

# ruff: noqa: E501, S310
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import urllib.request

sys.path.insert(0, ".")
from adapters.voyage import VoyageClient  # noqa: E402
from core.act_ids import plain_section, resolve_act  # noqa: E402
from core.settings import Settings  # noqa: E402

BASE = "http://localhost:7333"


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path, json.dumps(body).encode(), {"content-type": "application/json"}
    )  # noqa: S310
    return json.load(urllib.request.urlopen(req, timeout=120))["result"]  # noqa: S310


def N(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())


def body(p: dict) -> str:
    """The whole stored text, header included: a phrase may be the section's own heading."""
    return p["text"]


def candidates(coll: str, must: list[dict]) -> list[dict]:
    out, off = [], None
    while True:
        b = {
            "limit": 200,
            "with_payload": True,
            "with_vector": False,
            "filter": {"must": must},
        }
        if off is not None:
            b["offset"] = off
        r = post(f"/collections/{coll}/points/scroll", b)
        out += [p["payload"] for p in r["points"]]
        off = r["next_page_offset"]
        if off is None or len(out) >= 400:
            return out


def ranked(coll: str, vec: list[float], must: list[dict], k: int) -> list[dict]:
    b = {
        "query": vec,
        "using": "dense",
        "limit": k,
        "with_payload": True,
        "filter": {"must": must} if must else None,
    }
    return [
        p["payload"] for p in post(f"/collections/{coll}/points/query", b)["points"]
    ]


def ordered_blob(cands: list[dict]) -> str:
    cands = sorted(
        cands,
        key=lambda p: (
            p.get("parent_id") or p["chunk_id"],
            p.get("part_number", 0),
            int(p.get("chunk_index") or 0),
        ),
    )
    return N(
        "".join(
            p["text"].split("\n", 2)[-1] if p.get("part_number", 1) > 1 else p["text"]
            for p in cands
        )
    )


def lookup_kanoon(q: dict, vec) -> tuple[list[dict], list[dict], str]:
    ids = list(resolve_act(q["act"]))
    sec = plain_section(q["section"])
    if ids and sec:
        must = [
            {"key": "act_id", "match": {"any": ids}},
            {"key": "section_number", "match": {"value": sec}},
        ]
        c = candidates("kanoon_v1", must)
        if c:
            return c, ranked("kanoon_v1", vec, must, 5), "act+section"
    if ids:
        must = [{"key": "act_id", "match": {"any": ids}}]
        return (
            candidates("kanoon_v1", must)[:0] or ranked("kanoon_v1", vec, must, 50),
            ranked("kanoon_v1", vec, must, 5),
            "act only (no plain section)",
        )
    top = ranked("kanoon_v1", vec, [], 10)
    by_sec = ranked(
        "kanoon_v1",
        vec,
        [
            {
                "key": "section_number",
                "match": {"value": plain_section(q["section"]) or q["section"]},
            }
        ],
        2,
    )
    return top + by_sec, (by_sec + top)[:5], "Act unresolved: section signal"


def lookup_new(q: dict, vec) -> tuple[list[dict], list[dict], str]:
    must = [
        {"key": "act_id", "match": {"value": q["new_act_id"]}},
        {"key": "heading_section", "match": {"value": q["section_h"]}},
    ]
    c = candidates("research_v3", must)
    if c:
        return c, ranked("research_v3", vec, must, 5), "act+heading_section"
    act = [
        {"key": "act_id", "match": {"value": q["new_act_id"]}}
    ]  # same fallback layer as production
    return (
        ranked("research_v3", vec, act, 50),
        ranked("research_v3", vec, act, 5),
        "act only (section label not found)",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="evals/section_lookup_set.jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    qs = [json.loads(ln) for ln in open(a.set) if ln.strip()]
    for q in qs:  # how the new collection spells the section
        s = q["section"]
        m = re.match(r"ORDER (\w+) RULE (\w+)", s, re.I)
        q["section_h"] = (
            f"Order {m.group(1).upper()} Rule {m.group(2)}"
            if m
            else (plain_section(s) or s)
        )
    texts = [
        f"What does {'Article' if q['act'].startswith('Constitution') else 'Section'} {q['section'].title() if not q['section'].isdigit() else q['section']} of the {q['act']} say?"
        for q in qs
    ]
    s = Settings(
        VOYAGE_EMBED_MODELS={"kanoon_v1": "voyage-4"}
    )  # the live QUERY model (A126)
    r = asyncio.run(
        VoyageClient(s, timeout_s=60, max_attempts=3).embed_batch(
            texts, "kanoon_v1", "query"
        )
    )
    rows = []
    for q, vec in zip(qs, r.vectors, strict=True):
        ph = N(q["phrase"])
        row = {
            "id": q["id"],
            "act": q["act"],
            "section": q["section"],
            "fixed": q["fixed_by_supplement"],
        }
        for tag, fn in (("before", lookup_kanoon), ("after", lookup_new)):
            cand, top5, path = fn(q, vec)
            row[tag] = {
                "path": path,
                "n_candidates": len(cand),
                "cand": ph in ordered_blob(cand),
                "top5": any(ph in N(body(p)) for p in top5),
                "first": (top5[0]["chunk_id"] if top5 else None),
            }
        rows.append(row)
    json.dump(
        {"query_tokens": r.total_tokens, "rows": rows}, open(a.out, "w"), indent=1
    )
    for row in rows:
        b, af = row["before"], row["after"]
        print(
            f"{row['id']} {row['act'][:24]:24s} {row['section']:18s} before cand={int(b['cand'])} top5={int(b['top5'])} n={b['n_candidates']:3d} | after cand={int(af['cand'])} top5={int(af['top5'])} n={af['n_candidates']:3d}"
        )
    for lab, sel in (
        ("all", rows),
        ("fixed Acts", [x for x in rows if x["fixed"]]),
        ("unfixed Acts", [x for x in rows if not x["fixed"]]),
    ):
        print(
            f"{lab:13s} n={len(sel):2d}  before top5 {sum(x['before']['top5'] for x in sel)}  after top5 {sum(x['after']['top5'] for x in sel)} | before cand {sum(x['before']['cand'] for x in sel)}  after cand {sum(x['after']['cand'] for x in sel)}"
        )
    print("query-embedding billed tokens:", r.total_tokens)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
