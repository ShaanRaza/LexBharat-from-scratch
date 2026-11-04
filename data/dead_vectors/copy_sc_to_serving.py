"""Copy the 10,112 staged Supreme Court points into the serving collection `kanoon_v1` (A129).

Plain words: `embed_sc.py` wrote 10,112 points to the staging collection `kanoon_sc_new_v1`. This
copies them, dense and sparse vectors and payload exactly as staged, into `kanoon_v1`, both on the
COPY instance (port 7333). The originals are never touched. Nothing is rolled back automatically: if a
guard fails the script stops and prints the rollback of A129 (delete by `locally_embedded.model`).

Pipeline step touched: step 5 (Search) once copied in; the serving collection gains 10,112 points.

Guards (A129)
  before: `kanoon_v1` holds 445,643 points, 371,159 Supreme Court, none carrying `locally_embedded`;
          staging holds 10,112; none of the staged point ids or chunk ids is in `kanoon_v1`.
  after:  455,755 points, 381,271 Supreme Court; none of the 10,112 chunk ids on more than one point,
          and the number of duplicated chunk ids in `kanoon_v1` unchanged (it already held duplicates
          from loading, DATA-GAPS section 8, so "zero" cannot be the target); every copied point's
          dense AND sparse vector equal to the staged one; 10 copied points re-embedded under
          `voyage-4-large` reproduce at cosine 0.998 or more.
"""

from __future__ import annotations

import collections
import importlib.util
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
_spec = importlib.util.spec_from_file_location(
    "embed_sc", REPO / "data" / "dead_vectors" / "embed_sc.py"
)
esc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(esc)

SERVING, STAGING, http = esc.SERVING, esc.STAGING, esc.http
BEFORE_TOTAL, BEFORE_SC, N = 445_643, 371_159, 10_112
SC_FLT = {"must": [{"key": "court", "match": {"value": "Supreme Court of India"}}]}
ROLLBACK = (
    "ROLLBACK (A129): curl -s -X POST 'localhost:7333/collections/kanoon_v1/points/delete?wait=true' "
    '-H \'Content-Type: application/json\' -d \'{"filter":{"must":[{"key":"locally_embedded.model",'
    '"match":{"value":"voyage-4-large"}}]}}\'  then confirm 445,643 points and 371,159 Supreme Court.'
)


def fail(msg: str) -> None:
    sys.exit(f"\nSTOP: {msg}\n{ROLLBACK}\nNothing was rolled back automatically.")


def count(coll: str, flt: dict | None = None) -> int:
    body = {"exact": True, **({"filter": flt} if flt else {})}
    return http(f"/collections/{coll}/points/count", body)["result"]["count"]


def chunk_id_counts() -> collections.Counter:
    c, off = collections.Counter(), None
    while True:
        r = http(
            f"/collections/{SERVING}/points/scroll",
            {
                "limit": 5000,
                "offset": off,
                "with_payload": ["chunk_id"],
                "with_vector": False,
            },
        )["result"]
        c.update(p["payload"].get("chunk_id") for p in r["points"])
        off = r["next_page_offset"]
        if off is None:
            return c


def staged(with_vector: bool):
    off = None
    while True:
        r = http(
            f"/collections/{STAGING}/points/scroll",
            {
                "limit": 250,
                "offset": off,
                "with_payload": True,
                "with_vector": with_vector,
            },
        )["result"]
        yield from r["points"]
        off = r["next_page_offset"]
        if off is None:
            return


def main() -> None:
    model = esc.resolve_model(None)
    key = esc.voyage_key()
    # --- before ------------------------------------------------------------------------
    tot, sc = (
        http(f"/collections/{SERVING}", method="GET")["result"]["points_count"],
        count(SERVING, SC_FLT),
    )
    marked = count(SERVING, {"must_not": [{"is_empty": {"key": "locally_embedded"}}]})
    stg = count(STAGING)
    print(
        f"BEFORE: {SERVING} {tot:,} points, {sc:,} Supreme Court, {marked} with locally_embedded | staging {stg:,}"
    )
    if (tot, sc, marked, stg) != (BEFORE_TOTAL, BEFORE_SC, 0, N):
        fail("starting counts are not the expected 445,643 / 371,159 / 0 / 10,112")
    ids, cids = [], []
    for p in staged(False):
        ids.append(p["id"])
        cids.append(p["payload"]["chunk_id"])
    if len(set(ids)) != N or len(set(cids)) != N:
        fail("staged ids or chunk ids are not unique")
    before_dups = chunk_id_counts()
    dup_before = sum(1 for v in before_dups.values() if v > 1)
    if any(c in before_dups for c in cids):
        fail("a staged chunk id already exists in the serving collection")
    present = http(
        f"/collections/{SERVING}/points",
        {"ids": ids[:5000], "with_payload": False, "with_vector": False},
    )["result"]
    present += http(
        f"/collections/{SERVING}/points",
        {"ids": ids[5000:], "with_payload": False, "with_vector": False},
    )["result"]
    if present:
        fail(f"{len(present)} staged point ids already exist in the serving collection")
    print(
        f"  serving holds {dup_before:,} duplicated chunk ids already (from loading); none of the staged ids or chunk ids is present"
    )
    # --- copy --------------------------------------------------------------------------
    n, batch = 0, []
    for p in staged(True):
        batch.append({"id": p["id"], "vector": p["vector"], "payload": p["payload"]})
        if len(batch) == 250:
            http(f"/collections/{SERVING}/points?wait=true", {"points": batch}, "PUT")
            n += len(batch)
            batch = []
    if batch:
        http(f"/collections/{SERVING}/points?wait=true", {"points": batch}, "PUT")
        n += len(batch)
    print(f"COPIED {n:,} points")
    while True:
        r = http(f"/collections/{SERVING}", method="GET")["result"]
        if r["status"] == "green" and r["optimizer_status"] == "ok":
            break
        time.sleep(3)
    # --- after -------------------------------------------------------------------------
    tot2, sc2 = (
        http(f"/collections/{SERVING}", method="GET")["result"]["points_count"],
        count(SERVING, SC_FLT),
    )
    marked2 = count(
        SERVING,
        {"must": [{"key": "locally_embedded.model", "match": {"value": model}}]},
    )
    print(
        f"AFTER: {tot2:,} points (expected {BEFORE_TOTAL + N:,}), {sc2:,} Supreme Court (expected {BEFORE_SC + N:,}), {marked2:,} carry locally_embedded.model={model}"
    )
    if (tot2, sc2, marked2) != (BEFORE_TOTAL + N, BEFORE_SC + N, N):
        fail("counts after the copy are not as expected")
    after = chunk_id_counts()
    dup_after = sum(1 for v in after.values() if v > 1)
    multi = [c for c in cids if after[c] != 1]
    print(
        f"duplicated chunk ids: before {dup_before:,}, after {dup_after:,}; of the 10,112 copied chunk ids, on more than one point: {len(multi)}"
    )
    if dup_after != dup_before or multi:
        fail(
            "the copy changed the number of duplicated chunk ids, or a copied chunk id sits on two points"
        )
    # every copied point: dense and sparse equal to the staged ones
    bad_dense = bad_sparse = checked = 0
    stg_vec = {}
    for p in staged(True):
        stg_vec[p["id"]] = p["vector"]
    for i in range(0, N, 250):
        got = http(
            f"/collections/{SERVING}/points",
            {"ids": ids[i : i + 250], "with_payload": False, "with_vector": True},
        )["result"]
        for p in got:
            s, v = stg_vec[p["id"]], p["vector"]
            checked += 1
            bad_dense += not np.allclose(
                np.array(s["dense"]), np.array(v["dense"]), atol=1e-6
            )
            sp, vp = s["sparse"], v.get("sparse") or {"indices": [], "values": []}
            ok = sorted(sp["indices"]) == sorted(vp["indices"]) and vp["indices"] != []
            if ok:
                a, b = (
                    dict(zip(sp["indices"], sp["values"])),
                    dict(zip(vp["indices"], vp["values"])),
                )
                ok = all(abs(a[k] - b[k]) < 1e-6 for k in a)
            bad_sparse += not ok
    print(
        f"vectors compared on {checked:,} copied points: dense mismatches {bad_dense}, sparse missing or different {bad_sparse}"
    )
    if checked != N or bad_dense or bad_sparse:
        fail("a copied point's dense or sparse vector differs from the staged one")
    # spot check: 10 copied points reproduce under the serving model
    pick = random.Random(77).sample(ids, 10)  # noqa: S311 - seeded, reproducible verification sample, not a secret
    pts = http(
        f"/collections/{SERVING}/points",
        {"ids": pick, "with_payload": ["text", "chunk_id"], "with_vector": ["dense"]},
    )["result"]
    pts.sort(key=lambda p: p["id"])
    vecs, tok = esc.rk.voyage_embed(
        [p["payload"]["text"] for p in pts], SERVING, key, "sc copy spot-check 10"
    )
    cos = esc.cosine_rows(np.array(vecs), np.array([p["vector"]["dense"] for p in pts]))
    print(
        f"SPOT-CHECK 10 copied points under {model}: cosine min {cos.min():.6f}, max {cos.max():.6f} (need >= 0.998); {tok:,} tokens"
    )
    if cos.min() < 0.998:
        fail("a copied point does not reproduce under the serving model")
    print("COPY COMPLETE: all guards passed")


if __name__ == "__main__":
    main()
