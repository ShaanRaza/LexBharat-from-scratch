"""Copy the non-central Acts out of acts_india with their BM25 sparse vectors REPAIRED (DATA-GAPS section 9).

Plain words: about half of the Acts' keyword (BM25) vectors are wrong: they hold raw term counts where
BM25 weights belong (49.4% of a 10,000-point sample, measured 2 Nov 2026). For such a point keyword
search found NOTHING in a test (0 of 39 before the repair, 39 of 39 after). The 19,830 Central Act
points already in kanoon_v1 were repaired by data/sparse_fix.py. The rest (state and regulatory Acts,
about 1.02M points, of which an estimated 504,600 are broken) sit in the original `acts_india`.

This script does NOT touch the original. It reads the non-central Acts from the original
(read-only: one request at a time, a 0.25 s pause, a hard stop with no retry on a failure or a request
over 60 s) and writes them into a STAGING collection on the COPY instance (port 7333) with each broken
sparse vector re-encoded by FastEmbed `Qdrant/bm25` (document side, embed(), as the 20-of-20 check
against stored healthy vectors confirmed). The dense vector and the payload are copied unchanged, and a
repaired point carries `locally_repaired = {"sparse": "bm25-document", "date": ...}`. A point counts as
broken if its index set differs from the re-encoding OR any value differs by more than 1e-4 (stricter
than sparse_fix.py, which compared indices only: raw counts could share indices with correct vectors).

Pipeline step touched: step 5 (Search): the keyword half of hybrid search. Nothing is promoted into
kanoon_v1 (that is a separate decision, as with A123 and A129); the destination may not be kanoon_v1.

Run with an interpreter that has fastembed (it is not in the repo venv):
  fe_venv/bin/python data/repair_act_sparse.py plan --limit 20000
  fe_venv/bin/python data/repair_act_sparse.py copy --dest acts_noncentral_v1 --limit 5000     # rehearsal
  fe_venv/bin/python data/repair_act_sparse.py copy --dest acts_noncentral_v1                   # the rest; resumable
  fe_venv/bin/python data/repair_act_sparse.py verify --dest acts_noncentral_v1
"""

from __future__ import annotations

import argparse
import datetime
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

ORIG = "http://localhost:6333"
COPY = "http://127.0.0.1:7333"
SOURCE = "acts_india"
FORBIDDEN_DEST = {"legal_corpus_v1", "legal_corpus_v2", "acts_india", "kanoon_v1"}
NOT_CENTRAL = {"must_not": [{"key": "jurisdiction", "match": {"value": "central"}}]}
PAGE = 1000
HARD_STOP_S = 60
PAUSE_S = 0.25
TOL = 1e-4
STATE = Path.home() / "qdrant-kanoon" / "acts_repair"
INDEXES = ("jurisdiction", "section_number", "act_status", "language_code", "act_id")


# --- the original: read only, hard stop -----------------------------------------------------------
def orig_scroll(offset, limit: int, with_vector: bool) -> dict:
    body = {
        "filter": NOT_CENTRAL,
        "limit": limit,
        "offset": offset,
        "with_payload": True,
        "with_vector": ["dense", "sparse"] if with_vector else ["sparse"],
    }
    req = urllib.request.Request(
        ORIG + f"/collections/{SOURCE}/points/scroll",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(req, timeout=HARD_STOP_S).read()  # noqa: S310
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            f"HARD STOP reading the original after {time.time() - t0:.1f}s: {exc}\nNo retry. The checkpoint is kept; re-run to resume."
        )
    if time.time() - t0 > HARD_STOP_S:
        sys.exit(f"HARD STOP: a read took {time.time() - t0:.1f}s")
    time.sleep(PAUSE_S)
    return json.loads(raw)["result"]


def orig_retrieve(ids: list) -> list:
    req = urllib.request.Request(
        ORIG + f"/collections/{SOURCE}/points",
        data=json.dumps(
            {"ids": ids, "with_payload": False, "with_vector": ["dense", "sparse"]}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=HARD_STOP_S).read()  # noqa: S310
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"HARD STOP reading the original: {exc}")
    time.sleep(PAUSE_S)
    return json.loads(raw)["result"]


# --- the copy instance ------------------------------------------------------------------------------
def copy_http(
    path: str, body: dict | None = None, method: str = "POST", timeout: int = 900
):
    assert COPY.endswith(":7333")  # writes go to the copy instance only
    req = urllib.request.Request(
        COPY + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout))  # noqa: S310


def encoder():
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(model_name="Qdrant/bm25")


def encode_many(enc, texts: list[str]) -> list[dict]:
    """Document-side BM25, as the stored healthy vectors were built."""
    return [
        {"indices": [int(i) for i in e.indices], "values": [float(v) for v in e.values]}
        for e in enc.embed(texts)
    ]


def differs(stored: dict, new: dict) -> bool:
    """Broken = a different index set, or any value more than TOL away."""
    a, b = (
        dict(zip(stored["indices"], stored["values"])),
        dict(zip(new["indices"], new["values"])),
    )
    return set(a) != set(b) or any(abs(a[k] - b[k]) > TOL for k in a)


def only_indices_differ(stored: dict, new: dict) -> bool:
    return set(stored["indices"]) != set(new["indices"])


# --- modes ---------------------------------------------------------------------------------------------
def plan(a) -> None:
    enc = encoder()
    off, n, broken, idx_broken, empty = None, 0, 0, 0, 0
    while n < a.limit:
        r = orig_scroll(off, min(PAGE, a.limit - n), with_vector=False)
        texts = [(p["payload"].get("text") or "") for p in r["points"]]
        news = encode_many(enc, [t or " " for t in texts])
        for p, t, new in zip(r["points"], texts, news):
            n += 1
            if not t:
                empty += 1
                continue
            sp = p["vector"]["sparse"]
            broken += differs(sp, new)
            idx_broken += only_indices_differ(sp, new)
        off = r["next_page_offset"]
        if off is None:
            break
    print(
        f"READ-ONLY plan over the first {n:,} non-central Act points of {SOURCE} (empty text {empty}):"
    )
    print(
        f"  broken (indices OR values): {broken:,} = {broken / max(n - empty, 1) * 100:.1f}%  | by index set alone (sparse_fix.py's test): {idx_broken:,} = {idx_broken / max(n - empty, 1) * 100:.1f}%"
    )
    print(
        f"  against the 49.4% of section 9's 10,000-point sample; of 1,024,068 points that is about {broken / max(n - empty, 1) * 1_024_068:,.0f}"
    )


def ensure_dest(dest: str) -> None:
    names = {
        c["name"]
        for c in copy_http("/collections", method="GET")["result"]["collections"]
    }
    if dest in names:
        return
    copy_http(
        f"/collections/{dest}",
        {
            "vectors": {
                "dense": {
                    "size": 1024,
                    "distance": "Cosine",
                    "on_disk": True,
                    "quantization_config": {
                        "scalar": {
                            "type": "int8",
                            "quantile": 0.99,
                            "always_ram": False,
                        }
                    },
                }
            },
            "sparse_vectors": {
                "sparse": {
                    "index": {"full_scan_threshold": 5000, "on_disk": True},
                    "modifier": "idf",
                }
            },
            "shard_number": 1,
            "on_disk_payload": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
        },
        "PUT",
    )
    for f in INDEXES:
        copy_http(
            f"/collections/{dest}/index?wait=true",
            {"field_name": f, "field_schema": "keyword"},
            "PUT",
        )


def copy(a) -> None:
    if a.dest in FORBIDDEN_DEST:
        sys.exit(
            f"REFUSED: {a.dest} may not be the destination (an original, or the serving collection: promotion is a separate decision)."
        )
    STATE.mkdir(parents=True, exist_ok=True)
    sf = STATE / f"{a.dest}.state.json"
    st = (
        json.loads(sf.read_text())
        if sf.exists()
        else {
            "offset": None,
            "read": 0,
            "written": 0,
            "repaired": 0,
            "empty": 0,
            "done": False,
        }
    )
    if st["done"]:
        print("already complete:", st)
        return
    ensure_dest(a.dest)
    enc = encoder()
    today = datetime.date.today().isoformat()
    t0, start_read = time.time(), st["read"]
    while True:
        want = PAGE if a.limit is None else min(PAGE, a.limit - st["read"])
        if want <= 0:
            break
        r = orig_scroll(st["offset"], want, with_vector=True)
        pts = r["points"]
        texts = [(p["payload"].get("text") or "") for p in pts]
        news = encode_many(enc, [t or " " for t in texts])
        out = []
        for p, t, new in zip(pts, texts, news):
            vec = {"dense": p["vector"]["dense"], "sparse": p["vector"]["sparse"]}
            payload = dict(p["payload"])
            if not t:
                st["empty"] += 1  # nothing to encode: left as stored
            elif differs(vec["sparse"], new):
                vec["sparse"] = new
                payload["locally_repaired"] = {"sparse": "bm25-document", "date": today}
                st["repaired"] += 1
            out.append({"id": p["id"], "vector": vec, "payload": payload})
        copy_http(f"/collections/{a.dest}/points?wait=true", {"points": out}, "PUT")
        st["read"] += len(pts)
        st["written"] += len(out)
        st["offset"] = r["next_page_offset"]
        sf.write_text(json.dumps(st))
        rate = (st["read"] - start_read) / max(time.time() - t0, 1e-9)
        print(
            f"  read {st['read']:,} | repaired {st['repaired']:,} ({st['repaired'] / max(st['read'], 1) * 100:.1f}%) | {rate:,.0f} points/s",
            flush=True,
        )
        if st["offset"] is None:
            st["done"] = True
            sf.write_text(json.dumps(st))
            break
    print(
        ("COMPLETE" if st["done"] else "STOPPED at the limit (resumable)") + f": {st}"
    )


def verify(a) -> None:
    enc = encoder()
    n = copy_http(f"/collections/{a.dest}/points/count", {"exact": True})["result"][
        "count"
    ]
    rep = copy_http(
        f"/collections/{a.dest}/points/count",
        {
            "exact": True,
            "filter": {"must_not": [{"is_empty": {"key": "locally_repaired"}}]},
        },
    )["result"]["count"]
    state = json.loads((STATE / f"{a.dest}.state.json").read_text())
    print(
        f"{a.dest}: {n:,} points (state says written {state['written']:,}), {rep:,} marked locally_repaired (state says {state['repaired']:,}) -> {'OK' if (n, rep) == (state['written'], state['repaired']) else 'MISMATCH'}"
    )
    ids, off = [], None
    while len(ids) < a.sample * 3:
        r = copy_http(
            f"/collections/{a.dest}/points/scroll",
            {"limit": 2000, "offset": off, "with_payload": False, "with_vector": False},
        )["result"]
        ids += [p["id"] for p in r["points"]]
        off = r["next_page_offset"]
        if off is None:
            break
    pick = random.Random(5).sample(ids, min(a.sample, len(ids)))
    bad_sparse = no_text = 0
    for i in range(0, len(pick), 500):
        for p in copy_http(
            f"/collections/{a.dest}/points",
            {
                "ids": pick[i : i + 500],
                "with_payload": ["text"],
                "with_vector": ["sparse"],
            },
        )["result"]:
            t = p["payload"].get("text") or ""
            if not t:
                no_text += 1
                continue
            bad_sparse += differs(p["vector"]["sparse"], encode_many(enc, [t])[0])
    print(
        f"  sparse check on {len(pick):,} random points: {bad_sparse} differ from a fresh BM25 encoding (must be 0), {no_text} with no text"
    )
    sub = pick[: min(len(pick), 1000)]
    src = {p["id"]: p for p in orig_retrieve_batches(sub)}
    bad_dense = same_sparse_unrepaired = 0
    for i in range(0, len(sub), 500):
        for p in copy_http(
            f"/collections/{a.dest}/points",
            {
                "ids": sub[i : i + 500],
                "with_payload": ["locally_repaired"],
                "with_vector": ["dense", "sparse"],
            },
        )["result"]:
            s = src[p["id"]]
            bad_dense += (
                max(
                    abs(x - y)
                    for x, y in zip(p["vector"]["dense"], s["vector"]["dense"])
                )
                > 1e-6
            )
            if not (p["payload"] or {}).get("locally_repaired"):
                same_sparse_unrepaired += p["vector"]["sparse"] != s["vector"]["sparse"]
    print(
        f"  against the ORIGINAL on {len(sub):,} points: dense differs on {bad_dense} (must be 0); an UNrepaired point whose sparse differs from the original: {same_sparse_unrepaired} (must be 0)"
    )
    ok = (
        bad_sparse == 0
        and bad_dense == 0
        and same_sparse_unrepaired == 0
        and (n, rep) == (state["written"], state["repaired"])
    )
    print("VERIFY", "PASSED" if ok else "FAILED")
    sys.exit(0 if ok else 1)


def orig_retrieve_batches(ids: list) -> list:
    out = []
    for i in range(0, len(ids), 100):
        out += orig_retrieve(ids[i : i + 100])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--limit", type=int, default=20000)
    c = sub.add_parser("copy")
    c.add_argument("--dest", required=True)
    c.add_argument("--limit", type=int, default=None)
    v = sub.add_parser("verify")
    v.add_argument("--dest", required=True)
    v.add_argument("--sample", type=int, default=5000)
    a = ap.parse_args()
    {"plan": plan, "copy": copy, "verify": verify}[a.mode](a)


if __name__ == "__main__":
    main()
