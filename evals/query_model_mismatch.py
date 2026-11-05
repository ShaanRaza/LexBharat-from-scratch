# ruff: noqa: E501, S310, E731
"""How big is the query/document model mismatch? (A186). READ ONLY on port 7333; the only vendor call is
embedding ~40 short questions twice (voyage-4 and voyage-4-large, input_type=query). No re-embedding.

For 20 questions about a replaced Act or the Constitution it compares each question's cosine to the BEST
chunk carrying the section's text in (a) research_v3 (supplement chunk, stored voyage-4 document vector)
and (b) kanoon_v1 (the old chunk, stored vector, mostly voyage-4-large). For 20 case-law questions
it measures how the two query models rank research_v3. Hand-written questions: evals/query_model_questions.json.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import sys
import urllib.request

sys.path.insert(0, ".")
from adapters.voyage import VoyageClient  # noqa: E402
from core.settings import Settings  # noqa: E402

BASE = "http://localhost:7333"


def post(path, body):
    req = urllib.request.Request(
        BASE + path, json.dumps(body).encode(), {"content-type": "application/json"}
    )
    return json.load(urllib.request.urlopen(req, timeout=120))["result"]


N = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())  # noqa: E731
cos = lambda a, b: (
    sum(x * y for x, y in zip(a, b))
    / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))
)  # noqa: E731


def act_points(coll, act):
    out, off = [], None
    while True:
        b = {
            "limit": 500,
            "with_payload": ["chunk_id", "text"],
            "with_vector": ["dense"],
            "filter": {"must": [{"key": "act_id", "match": {"value": act}}]},
        }
        if off is not None:
            b["offset"] = off
        r = post(f"/collections/{coll}/points/scroll", b)
        out += r["points"]
        off = r["next_page_offset"]
        if off is None:
            return out


def holding(points, phrase):
    ph = N(phrase)
    hit = [p for p in points if ph in N(p["payload"]["text"])]
    if (
        not hit
    ):  # the phrase straddles two parts: take chunks containing its first 50 characters
        hit = [p for p in points if ph[:50] in N(p["payload"]["text"])]
    return hit


def vec(p):
    return p["vector"]["dense"] if isinstance(p["vector"], dict) else p["vector"]


def main():
    qs = json.load(open("evals/query_model_questions.json"))
    s = Settings(VOYAGE_EMBED_MODELS={"v4": "voyage-4", "large": "voyage-4-large"})
    c = VoyageClient(s, timeout_s=90, max_attempts=3)
    texts = [q["q"] for q in qs]
    tok = 0
    V = {}
    for m in ("v4", "large"):
        r = asyncio.run(c.embed_batch(texts, m, "query"))
        V[m] = r.vectors
        tok += r.total_tokens
    cache = {}
    rows = []
    for i, q in enumerate(qs):
        row = {"i": i, "kind": q["kind"], "q": q["q"]}
        if q["kind"] == "act":
            nk, ok = ("n", q["new_act"]), ("o", q["old_act"])
            new = cache.setdefault(nk, act_points("research_v3", q["new_act"]))
            new_h = holding(new, q["phrase"])
            old_h = (
                holding(
                    cache.setdefault(ok, act_points("kanoon_v1", q["old_act"])),
                    q["phrase"],
                )
                if q["old_act"]
                else []
            )
            for m in ("v4", "large"):
                a = max((cos(V[m][i], vec(p)) for p in new_h), default=None)
                b = max((cos(V[m][i], vec(p)) for p in old_h), default=None)
                row[m] = {
                    "new": a,
                    "old": b,
                    "gap": (a - b) if a is not None and b is not None else None,
                }
            row["new_chunks"], row["old_chunks"] = len(new_h), len(old_h)
        for m in ("v4", "large"):
            top = post(
                "/collections/research_v3/points/query",
                {
                    "query": V[m][i],
                    "using": "dense",
                    "limit": 5,
                    "with_payload": ["chunk_id", "source_kind"],
                },
            )["points"]
            row.setdefault(m, {})["top5"] = [p["payload"]["chunk_id"] for p in top]
            row[m]["top1_score"] = top[0]["score"]
            row[m]["supp_in_top5"] = sum(
                1 for p in top if p["payload"]["source_kind"] == "supplement_indiacode"
            )
        rows.append(row)
    json.dump({"query_tokens": tok, "rows": rows}, open(sys.argv[1], "w"), indent=1)
    print("query tokens billed:", tok)


if __name__ == "__main__":
    main()
