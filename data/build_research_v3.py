#!/usr/bin/env python3
"""Build the serving-candidate collection `research_v3` beside the live one (A183, A184).

Plain words. Writes ONLY to a new collection on the COPY instance (port 7333). Reads `kanoon_v1`.
  copy    kanoon_v1's points, EXCEPT the eight replaced Acts, with their stored dense + sparse vectors
          (no re-embedding), each given `heading_section` and `source_kind = dataset`.
  embed   the supplement chunks, dense with voyage-4 (input_type=document; the model that reproduces
          the gate chunks at 1.0000, A184). Billed tokens are summed from Voyage's own usage and the run
          STOPS before a request that could pass --token-cap. Vectors are cached on disk, so a restart
          never pays twice. Sparse: document-side BM25 (data/bm25_encode.py).
  load    upsert the new points.
  verify  counts, removed ids gone, no duplicate ids.
Switching which collection serves users is a config change (CORPUS_COLLECTION) this script never makes.
The guard is data/sparse_fix.py's: --target required, originals and port 6333 refused.

    .venv/bin/python data/build_research_v3.py copy   --target research_v3 --state DIR
    .venv/bin/python data/build_research_v3.py embed  --target research_v3 --state DIR --chunks F --token-cap N
    .venv/bin/python data/build_research_v3.py load   --target research_v3 --state DIR --chunks F
    .venv/bin/python data/build_research_v3.py verify --target research_v3 --state DIR --chunks F
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.build_promoted_collection import TEMPLATE, call, create_like  # noqa: E402
from data.build_serving_collection_v3 import REPLACES  # noqa: E402
from data.sparse_fix import check_target  # noqa: E402

BATCH = 256
EMBED_MODEL = "voyage-4"
EMBED_BATCH = 32
HEADING_RX = re.compile(r"(?:^|\| )(Section|Article)\s+(\d+[A-Z]{0,3}):", re.M)


def heading_section(p: dict) -> str:
    """The section a chunk is ABOUT, read from the chunk's own heading (never from section_number).
    Supplement chunks: the Act's own number, with Orders kept apart from sections ("Order VII Rule 11").
    kanoon_v1 chunks: the "Section N:" / "Article N:" in the first three lines of the text. '' if none
    (a judgment, a preamble, a schedule)."""
    if p.get("source_kind") == "supplement_indiacode":
        kind, lab = p.get("section_type"), str(p.get("section_number", ""))
        if kind in ("section", "article"):
            return lab
        if kind == "rule":
            v = (
                f" (variant {p['order_variant']})"
                if p.get("order_variant", 1) > 1
                else ""
            )
            return f"Order {p.get('order_number')} Rule {lab}{v}"
        if kind == "schedule_article":
            return f"Schedule Article {lab}"
        return lab  # a Schedule, an Appendix, the Preamble: by name
    head = "\n".join(str(p.get("text", "")).split("\n")[:3])
    m = HEADING_RX.search(head)
    return m.group(2) if m else ""


def point_id(chunk_id: str) -> int:
    return int.from_bytes(
        hashlib.blake2b(chunk_id.encode(), digest_size=8).digest(), "big"
    ) & (2**63 - 1)


def load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(path: Path, st: dict) -> None:
    path.write_text(json.dumps(st))


# ------------------------------------------------------------------------------------ copy
def cmd_copy(a, base, target, sdir: Path):
    sf = sdir / "copy.state.json"
    st = load_state(sf)
    existing = {c["name"] for c in call(base, "GET", "/collections")["collections"]}
    if target not in existing:
        create_like(base, target, TEMPLATE)
        call(
            base,
            "PUT",
            f"/collections/{target}/index?wait=true",
            {"field_name": "heading_section", "field_schema": "keyword"},
        )
        print(f"created {target} like {TEMPLATE} (+ heading_section index)", flush=True)
    elif not st:
        sys.exit(f"ABORT: {target} exists and there is no state file; refusing to mix.")
    flt = {"must_not": [{"key": "act_id", "match": {"any": list(REPLACES)}}]}
    off, n, t0 = st.get("offset"), st.get("n", 0), time.time()
    no_head = st.get("no_head", {"act_chunks": 0, "other": 0})
    while not st.get("done"):
        body = {
            "limit": BATCH,
            "with_payload": True,
            "with_vector": True,
            "filter": flt,
        }
        if off is not None:
            body["offset"] = off
        res = call(base, "POST", "/collections/kanoon_v1/points/scroll", body)
        pts = []
        for p in res["points"]:
            pl = dict(p["payload"])
            pl["heading_section"] = heading_section(pl)
            pl["source_kind"] = "dataset"
            if not pl["heading_section"]:
                no_head["act_chunks" if "section_number" in pl else "other"] += 1
            pts.append({"id": p["id"], "vector": p["vector"], "payload": pl})
        if pts:
            call(
                base, "PUT", f"/collections/{target}/points?wait=true", {"points": pts}
            )
        n += len(pts)
        off = res.get("next_page_offset")
        st.update(offset=off, n=n, no_head=no_head, done=off is None)
        save_state(sf, st)
        if n % (BATCH * 40) < BATCH:
            print(f"  {n:,} copied, {n / max(time.time() - t0, 1):.0f}/s", flush=True)
    print(f"copied {n:,}; no parseable heading: {no_head}", flush=True)


# ------------------------------------------------------------------------------------ embed
def read_chunks(path: Path) -> list[dict]:
    return [
        json.loads(ln)
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


def cmd_embed(a, base, target, sdir: Path):
    chunks = read_chunks(Path(a.chunks))
    cache = sdir / "dense.jsonl"
    done = {}
    if cache.exists():
        for ln in cache.read_text().splitlines():
            r = json.loads(ln)
            done[r["chunk_id"]] = r["dense"]
    ledger = sdir / "tokens.json"
    spent = json.loads(ledger.read_text())["billed"] if ledger.exists() else 0
    from adapters.voyage import VoyageClient
    from core.settings import Settings

    client = VoyageClient(
        Settings(VOYAGE_EMBED_MODELS={target: EMBED_MODEL}),
        timeout_s=120,
        max_attempts=4,
    )
    todo = [c for c in chunks if c["chunk_id"] not in done]
    print(
        f"{len(done)} cached, {len(todo)} to embed, model {EMBED_MODEL}, billed so far {spent:,}, cap {a.token_cap:,}",
        flush=True,
    )

    async def run():
        nonlocal spent
        for i in range(0, len(todo), EMBED_BATCH):
            part = todo[i : i + EMBED_BATCH]
            # a worst-case guard before sending: stop if even the exact local count could pass the cap
            if spent + a.reserve_per_batch > a.token_cap:
                sys.exit(
                    f"ABORT: {spent:,} billed + a batch could pass the cap of {a.token_cap:,}."
                )
            r = await client.embed_batch([c["text"] for c in part], target, "document")
            spent += r.total_tokens
            with cache.open("a") as fh:
                for c, v in zip(part, r.vectors, strict=True):
                    fh.write(json.dumps({"chunk_id": c["chunk_id"], "dense": v}) + "\n")
            ledger.write_text(json.dumps({"billed": spent, "model": EMBED_MODEL}))
            if spent > a.token_cap:
                sys.exit(
                    f"ABORT: billed {spent:,} tokens, over the cap of {a.token_cap:,}."
                )
        return spent

    spent = asyncio.run(run()) if todo else spent
    print(f"embedded; billed tokens in this ledger: {spent:,}", flush=True)


# ------------------------------------------------------------------------------------ load
def sparse_for(chunks: list[dict], interp: str) -> dict:
    inp = "\n".join(
        json.dumps({"id": c["chunk_id"], "text": c["text"]}) for c in chunks
    )
    out = subprocess.run(  # noqa: S603
        [interp, "data/bm25_encode.py"],
        input=inp,
        capture_output=True,
        text=True,
        check=True,
    )  # noqa: S603
    return {
        r["id"]: {"indices": r["indices"], "values": r["values"]}
        for r in map(json.loads, out.stdout.splitlines())
    }


def cmd_load(a, base, target, sdir: Path):
    chunks = read_chunks(Path(a.chunks))
    dense = {}
    for ln in (sdir / "dense.jsonl").read_text().splitlines():
        r = json.loads(ln)
        dense[r["chunk_id"]] = r["dense"]
    missing = [c["chunk_id"] for c in chunks if c["chunk_id"] not in dense]
    if missing:
        sys.exit(
            f"ABORT: {len(missing)} chunks have no dense vector yet; run embed first."
        )
    sparse = sparse_for(chunks, a.fastembed_python)
    pts = []
    for c in chunks:
        pl = dict(c)
        pl["source_kind"] = "supplement_indiacode"
        pl["heading_section"] = heading_section(pl)
        pts.append(
            {
                "id": point_id(c["chunk_id"]),
                "vector": {
                    "dense": dense[c["chunk_id"]],
                    "sparse": sparse[c["chunk_id"]],
                },
                "payload": pl,
            }
        )
    for i in range(0, len(pts), 64):
        call(
            base,
            "PUT",
            f"/collections/{target}/points?wait=true",
            {"points": pts[i : i + 64]},
        )
    print(f"loaded {len(pts):,} supplement points", flush=True)


# ------------------------------------------------------------------------------------ verify
def cmd_verify(a, base, target, sdir: Path):
    chunks = read_chunks(Path(a.chunks))
    count = call(base, "POST", f"/collections/{target}/points/count", {"exact": True})[
        "count"
    ]
    want = call(base, "POST", "/collections/kanoon_v1/points/count", {"exact": True})[
        "count"
    ]
    removed = call(
        base,
        "POST",
        "/collections/kanoon_v1/points/count",
        {
            "exact": True,
            "filter": {"must": [{"key": "act_id", "match": {"any": list(REPLACES)}}]},
        },
    )["count"]
    expect = want - removed + len(chunks)
    left = call(
        base,
        "POST",
        f"/collections/{target}/points/count",
        {
            "exact": True,
            "filter": {"must": [{"key": "act_id", "match": {"any": list(REPLACES)}}]},
        },
    )["count"]
    ids = [point_id(c["chunk_id"]) for c in chunks]
    print(
        json.dumps(
            {
                "target_count": count,
                "expected": expect,
                "match": count == expect,
                "replaced_act_points_left_in_target": left,
                "duplicate_new_point_ids": len(ids) - len(set(ids)),
                "duplicate_new_chunk_ids": len(chunks)
                - len({c["chunk_id"] for c in chunks}),
            }
        )
    )
    return 0 if count == expect and left == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["copy", "embed", "load", "verify"])
    ap.add_argument("--target", default=None)
    ap.add_argument("--url", default="http://localhost:7333")
    ap.add_argument("--state", required=True, type=Path)
    ap.add_argument("--chunks")
    ap.add_argument("--token-cap", type=int, default=700_000)
    ap.add_argument("--reserve-per-batch", type=int, default=12_000)
    ap.add_argument("--fastembed-python", default=None)
    a = ap.parse_args(argv)
    target, base = check_target(a.target, a.url)
    if target == "kanoon_v1":
        sys.exit("ABORT: the target cannot be the source.")
    a.state.mkdir(parents=True, exist_ok=True)
    return {
        "copy": cmd_copy,
        "embed": cmd_embed,
        "load": cmd_load,
        "verify": cmd_verify,
    }[a.cmd](a, base, target, a.state) or 0


if __name__ == "__main__":
    raise SystemExit(main())
