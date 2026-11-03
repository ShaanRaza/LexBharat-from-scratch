"""Embed the ~10,112 English Supreme Court chunks that Qdrant lacks, into a STAGING collection (A129).

Plain words: the parquet holds 10,112 English Supreme Court chunks (749 cases, mostly recent years)
that no Qdrant collection holds, so they cannot be retrieved at all. This script embeds their text
with the model recorded for `kanoon_v1` in core/settings.py (`voyage-4-large`, `input_type: document`)
and writes them to `kanoon_sc_new_v1` on the COPY instance (port 7333), next to a BM25 sparse vector
prepared by `embed_sc_sparse.py`. Nothing is written to `kanoon_v1`, `legal_corpus_v1` or
`legal_corpus_v2`; copying the staged points into the serving collection is a separate step.

Pipeline step touched: none at runtime (data preparation for step 5, Search, in a staging collection).

Rules enforced here (A129)
 1. The model is READ from the repo setting and must be `voyage-4-large`. Any `--model` that differs,
    and any VOYAGE_EMBED_MODELS in the environment, is refused before a request is made.
 2. Count and absence: the chunk file must hold 10,112 chunks give or take 10%, unique ids, and not one
    of its chunk ids or point ids may exist in `kanoon_v1`; a sample of the cases is also checked,
    read-only, against the original. Any failure aborts.
 3. `preflight` re-embeds 20 fresh Supreme Court chunks that ARE in `kanoon_v1` (not the 2 Nov
    sample) and every cosine to the stored vector must be >= 0.998. If one is not, the run is
    refused and the owner is told; the old 20-of-20 is not relied on.
 4. Spend ceiling: every request is reserved against RUN_TOKEN_CAP BEFORE it is sent, and the run
    also stops if the running dollar figure passes DOLLAR_CAP or the request count passes
    MAX_REQUESTS. It stops loudly (exit 4); it never continues past a ceiling.
 5. Writes: port 7333 only, staging collection only. `verify` then checks the output, runs the
    dead-vector detector over every vector and reports tokens and cost against the estimate.

  python embed_sc.py preflight
  python embed_sc.py run
  python embed_sc.py verify
The Voyage key is read from VOYAGE_API_KEY (or that one line of the repo .env) and is never printed.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from core.settings import Settings, UnknownEmbeddingModel  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "reembed_kerala", REPO / "data" / "dead_vectors" / "reembed_kerala.py"
)
rk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rk)  # the Kerala fix's own Voyage call, so the two runs share one path

ORIG = "http://localhost:6333"
COPY = "http://127.0.0.1:7333"
SERVING = "kanoon_v1"
STAGING = "kanoon_sc_new_v1"
HOME = Path.home() / "qdrant-kanoon"
CHUNKS = HOME / "reports" / "part7_new_chunks.jsonl"
WORK = HOME / "sc_new"
SPARSE = WORK / "sparse.jsonl"
DONE = WORK / "done_batches.log"
PREFLIGHT = WORK / "preflight.json"
VERIFY = WORK / "verify.json"
NOV2_LOG = HOME / "reports" / "part7_diag.log"
DIRECTION = REPO / "data" / "dead_vectors" / "legal_direction.npy"

MODEL_REQUIRED = "voyage-4-large"
EXPECTED = 10_112
TOLERANCE = 0.10
CALL = 32  # texts per Voyage request
RUN_TOKEN_CAP = 20_000_000  # about 2x the estimate; a loop bug at corpus scale would be ~$2,400
DOLLAR_CAP = 3.00
MAX_REQUESTS = 400  # 316 are needed
PRICE_PER_MTOK = 0.12  # list price of voyage-4-large
ESTIMATE_USD = 1.13
CHARS_PER_TOKEN_LOW = 2.4  # Kerala measured 2.8; lower = a larger, safer reservation
PREFLIGHT_MIN = 0.998
DETERMINISM_MIN = 0.9999
DEAD_BELOW = 0.10
ORIG_SAMPLE_CASES = 30
HARD_STOP_S = 60  # the owner's raised limit on reads of the originals; no retry
PAUSE_S = 0.25


class Ceiling(Exception):
    """A spend ceiling was reached. The run stops; nothing works around it."""


# --- plumbing ----------------------------------------------------------------------------
def http(path: str, body: dict | None = None, method: str = "POST", timeout: int = 900):
    assert COPY.endswith(":7333")  # writes go to the copy instance only
    req = urllib.request.Request(
        COPY + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout))  # noqa: S310


def orig_scroll(case_id: str) -> list[str]:
    """READ-ONLY: the chunk ids of one case in the original. One request, 0.25 s pause, hard stop."""
    body = {
        "filter": {"must": [{"key": "case_id", "match": {"value": case_id}}]},
        "limit": 500,
        "with_payload": ["chunk_id"],
        "with_vector": False,
    }
    req = urllib.request.Request(
        ORIG + "/collections/legal_corpus_v2/points/scroll",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(req, timeout=HARD_STOP_S).read()  # noqa: S310
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"HARD STOP reading the original after {time.time() - t0:.1f}s: {exc}")
    time.sleep(PAUSE_S)
    return [p["payload"]["chunk_id"] for p in json.loads(raw)["result"]["points"]]


def voyage_key() -> str:
    key = os.environ.get("VOYAGE_API_KEY")
    if not key:  # only that one line of the repo .env is ever read
        for line in (REPO / ".env").open():
            if line.startswith("VOYAGE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    return key or sys.exit("no VOYAGE_API_KEY")


def resolve_model(cli_model: str | None) -> str:
    if os.environ.get("VOYAGE_EMBED_MODELS"):
        sys.exit("REFUSED: VOYAGE_EMBED_MODELS is set in the environment (an override).")
    try:
        model = Settings(_env_file=None).embed_model_for(SERVING)
    except UnknownEmbeddingModel as exc:
        sys.exit(f"REFUSED: {exc}")
    if cli_model and cli_model != model:
        sys.exit(f"REFUSED: --model {cli_model!r} differs from the recorded {model!r}.")
    if model != MODEL_REQUIRED:
        sys.exit(f"REFUSED: recorded model is {model!r}; A129 approves {MODEL_REQUIRED!r}.")
    return model


def load_chunks() -> list[dict]:
    chunks = [json.loads(line) for line in CHUNKS.open()]
    lo, hi = int(EXPECTED * (1 - TOLERANCE)), int(EXPECTED * (1 + TOLERANCE))
    if not lo <= len(chunks) <= hi:
        sys.exit(f"ABORT: {len(chunks):,} chunks; expected {EXPECTED:,} within 10% ({lo:,} to {hi:,}).")
    ids = {int(c["id"]) for c in chunks}
    cids = {c["payload"]["chunk_id"] for c in chunks}
    if len(ids) != len(chunks) or len(cids) != len(chunks):
        sys.exit("ABORT: duplicate point ids or chunk ids inside the chunk file.")
    if not all(c["payload"].get("text") for c in chunks):
        sys.exit("ABORT: a chunk has no text.")
    return chunks


def scan_serving() -> dict:
    """Every point of the serving collection: ids, chunk ids, Supreme Court points, pdf urls."""
    ids, cids, sc, pdf, off = set(), set(), [], {}, None
    while True:
        r = http(
            f"/collections/{SERVING}/points/scroll",
            {
                "limit": 5000,
                "offset": off,
                "with_payload": ["chunk_id", "case_id", "court", "pdf_url", "pdf_urls"],
                "with_vector": False,
            },
        )["result"]
        for p in r["points"]:
            pl = p["payload"]
            ids.add(p["id"])
            cids.add(pl.get("chunk_id"))
            if pl.get("court") == "Supreme Court of India":
                sc.append((p["id"], pl.get("chunk_id")))
                if pl.get("pdf_url") and pl.get("case_id") not in pdf:
                    pdf[pl["case_id"]] = {"pdf_url": pl["pdf_url"], "pdf_urls": pl.get("pdf_urls")}
        off = r["next_page_offset"]
        if off is None:
            break
    return {"ids": ids, "cids": cids, "sc": sc, "pdf": pdf}


def guards(chunks: list[dict], serving: dict) -> dict:
    """Count (already asserted in load_chunks) and absence. Aborts on any failure."""
    present = [c["payload"]["chunk_id"] for c in chunks if c["payload"]["chunk_id"] in serving["cids"]]
    clash = [c["id"] for c in chunks if int(c["id"]) in serving["ids"]]
    if present or clash:
        sys.exit(f"ABORT: {len(present)} chunk ids and {len(clash)} point ids already exist in {SERVING}.")
    cases = sorted({c["payload"]["case_id"] for c in chunks})
    ours = {c["payload"]["chunk_id"] for c in chunks}
    found = 0
    for case in random.Random(5).sample(cases, min(ORIG_SAMPLE_CASES, len(cases))):
        found += len(ours & set(orig_scroll(case)))
    if found:
        sys.exit(f"ABORT: {found} of our chunk ids already exist in the original for {ORIG_SAMPLE_CASES} sampled cases.")
    return {
        "chunks": len(chunks),
        "cases": len(cases),
        "serving_points": http(f"/collections/{SERVING}", method="GET")["result"]["points_count"],
        "serving_sc_points": len(serving["sc"]),
        "original_cases_sampled": min(ORIG_SAMPLE_CASES, len(cases)),
    }


def cosine_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))


def nov2_ids() -> set[str]:
    return set(re.findall(r"^\s*\d+\.\s+(\S+)\s+year", NOV2_LOG.read_text(), flags=re.M)) if NOV2_LOG.exists() else set()


# --- preflight ---------------------------------------------------------------------------
def preflight(model: str, key: str) -> None:
    chunks = load_chunks()
    serving = scan_serving()
    info = guards(chunks, serving)
    print(f"model {model} (from core/settings.py via embed_model_for({SERVING!r}))")
    print(
        f"GUARDS PASSED: {info['chunks']:,} chunks in {info['cases']} cases (expected {EXPECTED:,}), none present in {SERVING} "
        f"({info['serving_points']:,} points, {info['serving_sc_points']:,} Supreme Court); "
        f"{info['original_cases_sampled']} sampled cases also absent from the original"
    )
    excl = nov2_ids()
    pool = [(i, c) for i, c in serving["sc"] if c not in excl]
    pick = random.Random(20261103).sample(pool, 20)
    pts = http(
        f"/collections/{SERVING}/points",
        {"ids": [i for i, _ in pick], "with_payload": ["text", "chunk_id"], "with_vector": ["dense"]},
    )["result"]
    pts.sort(key=lambda p: p["id"])
    vecs, spent = rk.voyage_embed([p["payload"]["text"] for p in pts], SERVING, key, "sc preflight 20 fresh")
    cos = cosine_rows(np.array(vecs), np.array([p["vector"]["dense"] for p in pts]))
    for p, c in zip(pts, cos):
        print(f"  {p['payload']['chunk_id']:24} cosine(new, stored) = {c:.5f}")
    ok = bool((cos >= PREFLIGHT_MIN).all())
    print(f"PREFLIGHT {'PASSED' if ok else 'FAILED'} (need every cosine >= {PREFLIGHT_MIN}); min {cos.min():.5f}, "
          f"median {np.median(cos):.5f}; {spent:,} tokens (about ${spent / 1e6 * PRICE_PER_MTOK:.4f}); "
          f"{len(excl)} of the 2 Nov chunks excluded from the draw")
    WORK.mkdir(parents=True, exist_ok=True)
    PREFLIGHT.write_text(
        json.dumps(
            {"passed": ok, "model": model, "time": time.time(), "cosines": [float(c) for c in cos], **info}
        )
    )
    sys.exit(0 if ok else 2)


# --- the run -----------------------------------------------------------------------------
def ensure_staging() -> None:
    names = {c["name"] for c in http("/collections", method="GET")["result"]["collections"]}
    if STAGING in names:
        return
    http(
        f"/collections/{STAGING}",
        {
            "vectors": {
                "dense": {
                    "size": 1024,
                    "distance": "Cosine",
                    "on_disk": True,
                    "quantization_config": {"scalar": {"type": "int8", "quantile": 0.99, "always_ram": False}},
                }
            },
            "sparse_vectors": {"sparse": {"index": {"full_scan_threshold": 5000, "on_disk": True}, "modifier": "idf"}},
            "shard_number": 1,
            "on_disk_payload": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
        },
        "PUT",
    )
    for field in ("court", "chunk_id"):
        http(f"/collections/{STAGING}/index?wait=true", {"field_name": field, "field_schema": "keyword"}, "PUT")


def run(model: str, key: str) -> None:
    pf = json.loads(PREFLIGHT.read_text()) if PREFLIGHT.exists() else {}
    if not pf.get("passed") or pf.get("model") != model or time.time() - pf.get("time", 0) > 12 * 3600:
        sys.exit("REFUSED: no passing preflight for this model in the last 12 hours. Run `preflight` first.")
    chunks = load_chunks()
    serving = scan_serving()
    guards(chunks, serving)  # re-asserted immediately before the spend
    sparse = {}
    for line in SPARSE.open():
        d = json.loads(line)
        sparse[d["id"]] = d
    if set(sparse) != {int(c["id"]) for c in chunks}:
        sys.exit("ABORT: sparse.jsonl does not cover exactly the chunk file (run embed_sc_sparse.py).")
    ensure_staging()
    done = {int(x) for x in DONE.read_text().split()} if DONE.exists() else set()
    batches = [chunks[i : i + CALL] for i in range(0, len(chunks), CALL)]
    today = datetime.date.today().isoformat()
    # the ceilings are cumulative across resumes: tokens already billed to this job, and batches already done
    used = sum(
        json.loads(line)["tokens"]
        for line in rk.LEDGER.open()
        if json.loads(line).get("tag", "").startswith("sc embed batch")
    )
    reserved_max = 0
    requests = len(done)
    print(f"model {model} | {len(batches)} batches of {CALL}, {len(done)} already done | ceilings: {RUN_TOKEN_CAP:,} tokens, ${DOLLAR_CAP:.2f}, {MAX_REQUESTS} requests", flush=True)
    for bi, batch in enumerate(batches):
        if bi in done:
            continue
        texts = [c["payload"]["text"] for c in batch]
        est = int(sum(len(t) for t in texts) / CHARS_PER_TOKEN_LOW)
        if used + est > RUN_TOKEN_CAP:
            raise Ceiling(f"{used:,} used + {est:,} next > RUN_TOKEN_CAP {RUN_TOKEN_CAP:,}")
        if (used + est) / 1e6 * PRICE_PER_MTOK > DOLLAR_CAP:
            raise Ceiling(f"projected ${(used + est) / 1e6 * PRICE_PER_MTOK:.2f} > DOLLAR_CAP ${DOLLAR_CAP:.2f}")
        requests += 1
        if requests > MAX_REQUESTS:
            raise Ceiling(f"{requests} requests > MAX_REQUESTS {MAX_REQUESTS}")
        vecs, tok = rk.voyage_embed(texts, SERVING, key, f"sc embed batch {bi}")
        used += tok
        reserved_max = max(reserved_max, est)
        if tok > 1.5 * est:
            raise Ceiling(f"batch {bi} billed {tok:,} tokens against an estimate of {est:,}: the estimate is wrong, stopping")
        points = []
        for c, v in zip(batch, vecs):
            pid = int(c["id"])
            payload = dict(c["payload"])
            inherit = serving["pdf"].get(payload.get("case_id"))
            if inherit:  # only from a sibling chunk of the same case already in the serving collection
                payload["pdf_url"] = inherit["pdf_url"]
                if inherit.get("pdf_urls"):
                    payload["pdf_urls"] = inherit["pdf_urls"]
            payload["locally_embedded"] = {"model": model, "date": today}
            points.append(
                {
                    "id": pid,
                    "vector": {"dense": v, "sparse": {"indices": sparse[pid]["indices"], "values": sparse[pid]["values"]}},
                    "payload": payload,
                }
            )
        http(f"/collections/{STAGING}/points?wait=true", {"points": points}, "PUT")
        with DONE.open("a") as f:
            f.write(f"{bi}\n")
            f.flush()
            os.fsync(f.fileno())
        if (bi + 1) % 20 == 0 or bi == len(batches) - 1:
            print(f"  batch {bi + 1}/{len(batches)}: {used:,} tokens so far (${used / 1e6 * PRICE_PER_MTOK:.3f}); projected total {used / (bi + 1) * len(batches):,.0f}", flush=True)
    print(f"RUN COMPLETE: {used:,} tokens this run (${used / 1e6 * PRICE_PER_MTOK:.3f} at list price) against an estimate of ${ESTIMATE_USD}; {requests} requests")


# --- verification ------------------------------------------------------------------------
def verify(model: str, key: str) -> None:
    chunks = load_chunks()
    pf = json.loads(PREFLIGHT.read_text())
    cnt = http(f"/collections/{STAGING}/points/count", {"exact": True})["result"]["count"]
    serving = http(f"/collections/{SERVING}", method="GET")["result"]["points_count"]
    sc_count = http(
        f"/collections/{SERVING}/points/count",
        {"exact": True, "filter": {"must": [{"key": "court", "match": {"value": "Supreme Court of India"}}]}},
    )["result"]["count"]
    print(f"staging points {cnt:,} (expected {len(chunks):,}) | {SERVING} points {serving:,} (before: {pf['serving_points']:,}), Supreme Court {sc_count:,} (before: {pf['serving_sc_points']:,})")
    mu = np.load(DIRECTION).astype(np.float64)
    ids, dense, scores, no_sparse, bad_norm, off = [], [], [], 0, 0, None
    while True:
        r = http(
            f"/collections/{STAGING}/points/scroll",
            {"limit": 1000, "offset": off, "with_payload": ["chunk_id"], "with_vector": True},
        )["result"]
        for p in r["points"]:
            v = np.array(p["vector"]["dense"], dtype=np.float64)
            sp = p["vector"].get("sparse")
            no_sparse += not (sp and sp["indices"])
            bad_norm += abs(np.linalg.norm(v) - 1) > 1e-3 or len(v) != 1024
            ids.append(p["id"])
            dense.append(v)
            scores.append(float(v @ mu / np.linalg.norm(v)))
        off = r["next_page_offset"]
        if off is None:
            break
    s = np.array(scores)
    q = np.percentile(s, [0, 1, 5, 25, 50, 75, 95, 100])
    dead = int((s < DEAD_BELOW).sum())
    print(f"DETECTOR over all {len(s):,} staged vectors (cosine with the legal direction; healthy 0.56 to 0.63, dead below {DEAD_BELOW}):")
    print(f"  min {q[0]:.3f} | p1 {q[1]:.3f} | p5 {q[2]:.3f} | p25 {q[3]:.3f} | median {q[4]:.3f} | p75 {q[5]:.3f} | p95 {q[6]:.3f} | max {q[7]:.3f} | mean {s.mean():.3f}")
    print(f"  below {DEAD_BELOW} (dead): {dead} | below 0.30: {(s < 0.30).sum()} | vectors without a sparse part: {no_sparse} | bad norm or size: {bad_norm}")
    rnd = random.Random(99)
    pick = rnd.sample(range(len(ids)), 20)
    text_of = {int(c["id"]): c["payload"]["text"] for c in chunks}
    texts = [text_of[ids[i]] for i in pick]
    stored = np.array([dense[i] for i in pick])
    large, t1 = rk.voyage_embed(texts, SERVING, key, "sc verify 20 under voyage-4-large")
    c_large = cosine_rows(np.array(large), stored)
    control = Settings(_env_file=None, VOYAGE_EMBED_MODELS={"negative_control": "voyage-4"})  # a model the adapter is told about, not a backdoor
    small, t2 = rk.voyage_embed(texts, "negative_control", key, "sc verify 20 under voyage-4 (negative control)", control)
    c_small = cosine_rows(np.array(small), stored)
    print(f"RE-EMBED 20 staged chunks: under {model} cosine to written vector min {c_large.min():.6f} (need >= {DETERMINISM_MIN}); under voyage-4 (must NOT match) max {c_small.max():.4f}, min {c_small.min():.4f}")
    run_tok = sum(
        json.loads(line)["tokens"]
        for line in rk.LEDGER.open()
        if json.loads(line).get("tag", "").startswith("sc embed batch")
    )
    pre_tok = sum(json.loads(line)["tokens"] for line in rk.LEDGER.open() if json.loads(line).get("tag", "").startswith(("sc preflight", "sc verify")))
    cost = run_tok / 1e6 * PRICE_PER_MTOK
    print(f"SPEND: embed {run_tok:,} tokens = ${cost:.3f} at the ${PRICE_PER_MTOK}/M list price (estimate ${ESTIMATE_USD}); preflight + verify {pre_tok:,} tokens; per chunk {run_tok / max(len(chunks), 1):,.0f} tokens")
    out = {
        "staging_points": cnt, "serving_points": serving, "serving_sc_points": sc_count, "detector_quantiles": [float(x) for x in q], "detector_mean": float(s.mean()),
        "dead": dead, "no_sparse": no_sparse, "bad_norm": bad_norm, "determinism_min": float(c_large.min()), "voyage4_max": float(c_small.max()),
        "embed_tokens": run_tok, "embed_cost_usd": cost, "other_tokens": pre_tok,
    }
    VERIFY.write_text(json.dumps(out))
    ok = cnt == len(chunks) and dead == 0 and no_sparse == 0 and bad_norm == 0 and c_large.min() >= DETERMINISM_MIN and c_small.max() < PREFLIGHT_MIN
    print("VERIFY", "PASSED" if ok else "FAILED")
    sys.exit(0 if ok else 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["preflight", "run", "verify"])
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    model = resolve_model(a.model)
    key = voyage_key()
    try:
        {"preflight": preflight, "run": run, "verify": verify}[a.cmd](model, key)
    except Ceiling as exc:
        print(f"\nSTOP (spend ceiling): {exc}")
        sys.exit(4)


if __name__ == "__main__":
    main()
