"""What a chunk that has a BM25 vector but no dense vector gets back, on the known-item harness (A141 cost picture).

Pipeline step 5 (Search) measurement; nothing here changes behaviour, and no Voyage call is made (the query vectors
are the stored A136 ones, `c_qvec.npy`).

Setup, all on the COPY instance (127.0.0.1:7333), never the original:
  1. copy the 18,399-chunk A128 evaluation corpus (`a128_multicourt`) into a scratch collection;
  2. delete the dense vector of the 250 TARGET chunks only, so each target is a sparse-only chunk competing with
     ordinary dense+sparse chunks, which is exactly what the backfilled cases would be next to the rest of the corpus;
  3. run the same 1,161 queries as A136 and rank the target.

Conditions (all `voyage-4` query vector, the production setting):
  hybrid_both    target has dense and sparse (the ordinary chunk; `a128_multicourt`)
  hybrid_sparse  target has sparse only (the scratch collection)
  sparse_leg     the keyword half alone, which is what finds a sparse-only chunk at all
  dense_leg      the dense half alone, for reference

  .venv/bin/python -m evals.a141.sparse_only_sim            # build the scratch collection if absent, then run
  .venv/bin/python -m evals.a141.sparse_only_sim --run-only # reuse it
"""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.request

import numpy as np

from adapters.qdrant import QdrantStore
from core.settings import Settings
from evals.a136.paths import DATA
from evals.a141.stats import K_LIST, diff_ci, recall

COPY = "http://127.0.0.1:7333"
SOURCE = "a128_multicourt"
SCRATCH = "a141_sparse_only_sim"


def call(method: str, path: str, body: dict | None = None) -> dict:
    """The copy instance only. The scratch collection is the only thing this writes to."""
    if method != "GET" and not (
        path.startswith(f"/collections/{SCRATCH}") or path == f"/collections/{SCRATCH}"
    ):
        if not (
            method == "POST" and path.startswith(f"/collections/{SOURCE}/points/scroll")
        ):
            raise SystemExit(f"refused: {method} {path}")
    req = urllib.request.Request(  # noqa: S310 - fixed loopback http base
        COPY + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["result"]  # noqa: S310


def build(targets: list[int]) -> None:
    exists = [c["name"] for c in call("GET", "/collections")["collections"]]
    if SCRATCH in exists:
        print(f"{SCRATCH} already exists: reused, not rebuilt")
        return
    cfg = call("GET", f"/collections/{SOURCE}")["config"]["params"]
    call(
        "PUT",
        f"/collections/{SCRATCH}",
        {
            "vectors": cfg["vectors"],
            "sparse_vectors": cfg["sparse_vectors"],
            "on_disk_payload": True,
        },
    )
    off, n = None, 0
    while True:
        body = {"limit": 500, "with_payload": True, "with_vector": True}
        if off is not None:
            body["offset"] = off
        r = call("POST", f"/collections/{SOURCE}/points/scroll", body)
        pts = [
            {"id": p["id"], "vector": p["vector"], "payload": p["payload"]}
            for p in r["points"]
        ]
        call("PUT", f"/collections/{SCRATCH}/points?wait=true", {"points": pts})
        n += len(pts)
        off = r.get("next_page_offset")
        if off is None:
            break
    call(
        "POST",
        f"/collections/{SCRATCH}/points/vectors/delete?wait=true",
        {"points": targets, "vector": ["dense"]},
    )
    print(
        f"copied {n:,} points into {SCRATCH}; dense vector removed from {len(targets)} targets"
    )


def check(targets: list[int]) -> dict:
    """The simulation is only valid if the targets really lack a dense vector and everything else has one."""
    got = call(
        "POST",
        f"/collections/{SCRATCH}/points",
        {"ids": targets[:50], "with_vector": True, "with_payload": False},
    )
    no_dense = sum(1 for p in got if "dense" not in p["vector"])
    has_sparse = sum(1 for p in got if "sparse" in p["vector"])
    total = call("POST", f"/collections/{SCRATCH}/points/count", {"exact": True})[
        "count"
    ]
    other = call(
        "POST",
        "/collections/" + SCRATCH + "/points/scroll",
        {"limit": 5, "with_vector": True, "with_payload": False},
    )["points"]
    return {
        "scratch_points": total,
        "first_50_targets_without_dense": no_dense,
        "first_50_targets_with_sparse": has_sparse,
        "sample_non_target_has_dense": all(
            "dense" in p["vector"] for p in other if p["id"] not in set(targets)
        ),
    }


async def run(queries, qv, sparse, tgt) -> list[dict]:
    store = QdrantStore(
        Settings(_env_file=None, QDRANT_URL=COPY), sparse_encoder=lambda t: sparse[t]
    )

    async def rank(coll, vec, text, mode, target):
        ids = [
            h.record_id for h in await store.search(coll, vec, text, {}, 50, mode=mode)
        ]
        return ids.index(target) + 1 if target in ids else 51

    rows = []
    for i, q in enumerate(queries):
        t = tgt[q["id"]]
        v = qv[i, 0].tolist()
        rows.append(
            {
                "id": q["id"],
                "style": q["style"],
                "hybrid_both": await rank(SOURCE, v, q["text"], "hybrid", t),
                "hybrid_sparse": await rank(SCRATCH, v, q["text"], "hybrid", t),
                "sparse_leg": await rank(SOURCE, v, q["text"], "sparse", t),
                "dense_leg": await rank(SOURCE, v, q["text"], "dense", t),
            }
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-only", action="store_true")
    a = ap.parse_args()
    queries = json.load(open(DATA / "c_queries.json"))
    qv = np.load(DATA / "c_qvec.npy")
    sparse = {k: tuple(v) for k, v in json.load(open(DATA / "c_sparse.json")).items()}
    tg = json.load(open(DATA / "c_targets.json"))["targets"]
    tgt = {t["id"]: t["chunk_id"] for t in tg}
    targets = [t["id"] for t in tg]
    if not a.run_only:
        build(targets)
    ck = check(targets)
    print("check:", ck)
    if (
        ck["first_50_targets_without_dense"] != 50
        or not ck["sample_non_target_has_dense"]
    ):
        raise SystemExit(
            "the scratch collection is not in the intended state; not running"
        )
    rows = asyncio.run(run(queries, qv, sparse, tgt))
    rng = np.random.default_rng(13)
    out: dict = {
        "check": ck,
        "queries": len(rows),
        "targets": len(targets),
        "styles": {},
    }
    for style in ("sentence", "paraphrase", None):
        sub = [r for r in rows if style is None or r["style"] == style]
        res = {"queries": len(sub), "recall": {}, "diff": {}}
        for k in K_LIST:
            res["recall"][f"@{k}"] = {
                c: recall(sub, c, k)
                for c in ("hybrid_both", "hybrid_sparse", "sparse_leg", "dense_leg")
            }
            res["diff"][f"@{k}"] = {
                "hybrid_sparse_minus_hybrid_both": diff_ci(
                    sub, "hybrid_both", "hybrid_sparse", k, rng
                ),
                "sparse_leg_minus_hybrid_both": diff_ci(
                    sub, "hybrid_both", "sparse_leg", k, rng
                ),
            }
        out["styles"][style or "both"] = res
    (DATA / "a141_sparse_only_results.json").write_text(
        json.dumps({**out, "rows": rows})
    )
    for name, res in out["styles"].items():
        print(f"\n== {name}: {res['queries']} queries")
        for k in K_LIST:
            print(
                f"  @{k}: "
                + "  ".join(f"{c} {v:5.1f}" for c, v in res["recall"][f"@{k}"].items())
            )
            for lab, (pt, lo, hi, g, lo_) in res["diff"][f"@{k}"].items():
                print(
                    f"       {lab}: {pt:+5.1f} [{lo:+5.1f},{hi:+5.1f}] gained/lost {g}/{lo_}"
                )


if __name__ == "__main__":
    main()
