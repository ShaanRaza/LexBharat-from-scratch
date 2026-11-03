"""Re-embed the dead dense vectors of Kerala chunks of `legal_corpus_v2`, into a STAGING collection.

Plain words: 217,766 Kerala chunks carry a stored dense vector that is not an embedding of their
text (`score_dense_vectors.py` found them; 45 of 45 flagged Kerala chunks were confirmed dead).
This script fetches each flagged chunk from the ORIGINAL (read-only), embeds its text again with
the model recorded for `kerala_v2_fix` in core/settings.py (`VOYAGE_EMBED_MODELS`, voyage-4), and
writes the chunk into `kerala_v2_fix` on the COPY instance (port 7333) with the new dense vector.
The payload and the sparse (BM25) vector are copied exactly as they are in the original. The
original collection is never written.

Rules enforced here
 1. The model is READ from the repo setting; any `--model` that differs, and any
    `VOYAGE_EMBED_MODELS` in the environment, is refused before a request is made.
 2. `preflight` must pass first: 5 chunks known to be live voyage-4 are re-embedded and must match
    their stored vectors at cosine >= 0.998. `run` refuses to start without a passing preflight.
 3. A chunk is written only if cosine(new vector, stored vector) < 0.5 (the stored vector really is
    unrelated to the text). Otherwise it is skipped and listed in skipped.tsv.
 4. Spend cap: every Voyage call is reserved against a token budget (ledger file) BEFORE it is
    sent; the run stops cleanly when the next batch would take the total over TOKEN_CAP.
 5. Reads of the original: whitelisted path, one request at a time, 0.25 s pause, hard stop with no
    retry on a failure or a request over 20 s. Writes: port 7333 only.

Resumable: the flagged ids are sorted and cut into fixed batches of 100. After a batch is written
(wait=true) one line goes to done_batches.log (fsync). A re-run skips batches in that log; upserts
are idempotent, so a batch that died half-way is simply redone.

  python reembed_kerala.py preflight
  python reembed_kerala.py run [--max-batches N]
The Voyage key is taken from the environment variable VOYAGE_API_KEY only and is never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from adapters.voyage import VoyageClient  # noqa: E402
from core.settings import Settings, UnknownEmbeddingModel  # noqa: E402
from pydantic import SecretStr  # noqa: E402

ORIG = "http://localhost:6333"
COPY = "http://127.0.0.1:7333"
SRC = "legal_corpus_v2"
DEST = "kerala_v2_fix"
HOME = Path.home() / "qdrant-kanoon"
FIX = HOME / "kerala_fix"
FLAGGED = HOME / "scan" / "kerala_flagged.tsv"
LEDGER = FIX / "token_ledger.jsonl"
DONE = FIX / "done_batches.log"
OLD = FIX / "old_dense.f32"
COSINES = FIX / "cosines.tsv"
SKIPPED = FIX / "skipped.tsv"
PREFLIGHT = FIX / "preflight.json"
EXPECTED = 217_766
BATCH = 100
CALL = 50  # texts per Voyage request
TOKEN_CAP = 300_000_000  # raised from 250M by the owner on 3 Nov 2026: measured 1,250 tokens per chunk, so about 269M are needed
CHARS_PER_TOKEN_LOW = 2.4  # measured 2.8 on flagged chunks; lower = safer reservation
DEAD_BELOW = 0.5
PREFLIGHT_MIN = 0.998
HARD_STOP_S = 20
PAUSE_S = 0.25
WORKERS = 6
LOCK = threading.Lock()
STOP = threading.Event()


class CapReached(Exception):
    pass


# --- the model: from the repo setting, nothing else --------------------------------------
def resolve_model(cli_model: str | None) -> str:
    if os.environ.get("VOYAGE_EMBED_MODELS"):
        sys.exit(
            "REFUSED: VOYAGE_EMBED_MODELS is set in the environment (an override)."
        )
    try:
        model = Settings(_env_file=None).embed_model_for(DEST)
    except UnknownEmbeddingModel as exc:
        sys.exit(f"REFUSED: {exc}")
    if cli_model and cli_model != model:
        sys.exit(
            f"REFUSED: --model {cli_model!r} differs from the recorded model for {DEST} "
            f"({model!r})."
        )
    if model != "voyage-4":
        sys.exit(
            f"REFUSED: recorded model is {model!r}; this script is approved for voyage-4."
        )
    return model


# --- the original: read-only -------------------------------------------------------------
ORIG_LOG: list[float] = []


def orig_retrieve(ids: list[int]) -> list[dict]:
    """Retrieve points by id from the ORIGINAL. One request, a pause, a hard stop."""
    body = {"ids": ids, "with_payload": True, "with_vector": ["dense", "sparse"]}
    req = urllib.request.Request(
        f"{ORIG}/collections/{SRC}/points",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(req, timeout=HARD_STOP_S).read()  # noqa: S310
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            f"HARD STOP reading the original: {exc}. No retry. Nothing more written."
        )
    dt = time.time() - t0
    if dt > HARD_STOP_S:
        sys.exit(f"HARD STOP: a read of the original took {dt:.1f}s. No retry.")
    ORIG_LOG.append(dt)
    time.sleep(PAUSE_S)
    return json.loads(raw)["result"]


# --- the copy: the only place anything is written ----------------------------------------
def copy_call(
    path: str, body: dict | None, method: str = "PUT", tries: int = 4
) -> dict:
    assert COPY.endswith(":7333"), "writes go to port 7333 only"
    data = json.dumps(body).encode() if body is not None else None
    for k in range(tries):
        req = urllib.request.Request(
            COPY + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            return json.load(urllib.request.urlopen(req, timeout=600))  # noqa: S310
        except Exception as exc:  # noqa: BLE001
            if k == tries - 1:
                raise RuntimeError(
                    f"copy instance {method} {path} failed: {exc}"
                ) from exc
            time.sleep(3 * (k + 1))
    raise AssertionError


def ensure_collection() -> None:
    have = {
        c["name"]
        for c in copy_call("/collections", None, "GET")["result"]["collections"]
    }
    if DEST in have:
        return
    copy_call(
        f"/collections/{DEST}",
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
    )


# --- Voyage, with a token budget -----------------------------------------------------------
class Budget:
    """Tokens already spent (from the ledger) plus tokens reserved by calls in flight."""

    def __init__(self, cap: int) -> None:
        self.cap, self.reserved = cap, 0
        self.used = (
            sum(json.loads(line)["tokens"] for line in LEDGER.open())
            if LEDGER.exists()
            else 0
        )

    def reserve(self, est: int) -> None:
        with LOCK:
            if self.used + self.reserved + est > self.cap:
                raise CapReached(
                    f"{self.used:,} used + {self.reserved:,} reserved + {est:,} next > cap {self.cap:,}"
                )
            self.reserved += est

    def settle(self, est: int, actual: int) -> None:
        with LOCK:
            self.reserved -= est
            self.used += actual


def voyage_embed(
    texts: list[str],
    collection: str,
    key: str,
    tag: str,
    settings: Settings | None = None,
) -> tuple[list[list[float]], int]:
    """Embed `texts` as DOCUMENTS, in requests of CALL texts, through adapters/voyage.py
    (A127: the only code that talks to Voyage). The model is the one recorded for
    `collection` in the settings, which refuses a collection nobody measured. Returns
    (vectors, tokens billed). Every billed request is appended to the ledger the moment
    it succeeds."""
    s = settings or Settings(_env_file=None)
    s = s.model_copy(update={"VOYAGE_API_KEY": SecretStr(key)})
    model = s.embed_model_for(collection)
    client = VoyageClient(s, timeout_s=180, max_attempts=10)
    out: list[list[float]] = []
    spent = 0
    for i in range(0, len(texts), CALL):
        batch = asyncio.run(client.embed_batch(texts[i : i + CALL], collection, "document"))
        with LOCK, LEDGER.open("a") as f:
            f.write(
                json.dumps(
                    {"t": time.time(), "model": model, "tokens": batch.total_tokens, "tag": tag}
                )
                + "\n"
            )
        out += batch.vectors
        spent += batch.total_tokens
    return out, spent


def cosine_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))


def est_tokens(texts: list[str]) -> int:
    return int(sum(len(t) for t in texts) / CHARS_PER_TOKEN_LOW) + 1


def load_ids() -> list[int]:
    ids = sorted(
        int(line.split("\t")[0]) for line in FLAGGED.read_text().splitlines()[1:]
    )
    assert len(ids) == EXPECTED == len(set(ids)), (len(ids), len(set(ids)))
    return ids


# --- preflight -----------------------------------------------------------------------------
def preflight(model: str, key: str) -> None:
    R = HOME / "reports"
    sample = [json.loads(line) for line in (R / "hc2_sample.jsonl").open()]
    res = json.load(open(R / "hc2_results.json"))
    live = [
        c["id"]
        for c in sample
        if c["coll"] == SRC
        and c["court"] == "High Court of Kerala"
        and res[c["coll"] + str(c["id"])]["voyage-4"] >= 0.998
    ]
    rnd = np.random.default_rng(20261104)
    ids = [int(x) for x in rnd.choice(live, 5, replace=False)]
    pts = orig_retrieve(ids)
    assert len(pts) == 5
    texts = [p["payload"]["text"] for p in pts]
    vecs, spent = voyage_embed(texts, DEST, key, "preflight")
    new = np.array(vecs)
    old = np.array([p["vector"]["dense"] for p in pts])
    cos = cosine_rows(new, old)
    ok = bool((cos >= PREFLIGHT_MIN).all())
    print(f"model {model} (from core/settings.py via embed_model_for({DEST!r}))")
    for p, c in zip(pts, cos):
        print(
            f"  {p['payload'].get('chunk_id')}  id {p['id']}  cosine(new, stored) = {c:.5f}"
        )
    print(
        f"PREFLIGHT {'PASSED' if ok else 'FAILED'} (need every cosine >= {PREFLIGHT_MIN}); {spent:,} tokens"
    )
    PREFLIGHT.write_text(
        json.dumps(
            {
                "passed": ok,
                "model": model,
                "ids": ids,
                "cosines": [float(c) for c in cos],
                "time": time.time(),
            }
        )
    )
    sys.exit(0 if ok else 2)


# --- the run -------------------------------------------------------------------------------
def run(model: str, key: str, max_batches: int | None) -> None:
    pf = json.loads(PREFLIGHT.read_text()) if PREFLIGHT.exists() else {}
    if not (pf.get("passed") and pf.get("model") == model):
        sys.exit("REFUSED: no passing preflight for this model. Run `preflight` first.")
    ids = load_ids()
    pos = {i: k for k, i in enumerate(ids)}
    batches = [ids[k : k + BATCH] for k in range(0, len(ids), BATCH)]
    done = set()
    if DONE.exists():
        done = {
            int(line.split("\t")[0])
            for line in DONE.read_text().splitlines()
            if line.strip()
        }
    todo = [b for b in range(len(batches)) if b not in done]
    if max_batches:
        todo = todo[:max_batches]
    ensure_collection()
    old = np.memmap(
        OLD,
        dtype=np.float32,
        mode="r+" if OLD.exists() else "w+",
        shape=(len(ids), 1024),
    )
    budget = Budget(TOKEN_CAP)
    print(
        f"model {model} | {len(done)} batches already done, {len(todo)} to do | tokens already on ledger {budget.used:,} of cap {TOKEN_CAP:,}",
        flush=True,
    )
    state = {
        "written": 0,
        "skipped": 0,
        "tokens": 0,
        "batches": 0,
        "error": None,
        "capped": None,
    }
    t0 = time.time()
    sem = threading.BoundedSemaphore(WORKERS * 2)

    def work(bi: int, pts: list[dict]) -> None:
        try:
            if STOP.is_set():
                return
            want = batches[bi]
            got = {p["id"] for p in pts}
            missing = [i for i in want if i not in got]
            if missing:
                raise RuntimeError(
                    f"batch {bi}: {len(missing)} flagged ids missing from the original, e.g. {missing[:3]}"
                )
            texts = [p["payload"].get("text") or "" for p in pts]
            if not all(texts):
                raise RuntimeError(f"batch {bi}: a chunk has no text")
            est = est_tokens(texts)
            budget.reserve(
                est
            )  # raises CapReached BEFORE any request if the cap would be passed
            spent = 0
            try:
                vecs, spent = voyage_embed(texts, DEST, key, f"kerala batch {bi}")
            finally:
                budget.settle(est, spent)
            new = np.array(vecs)
            oldv = np.array([p["vector"]["dense"] for p in pts], dtype=np.float32)
            cos = cosine_rows(new, oldv)
            keep = cos < DEAD_BELOW
            points = []
            for p, vec, k in zip(pts, new, keep):
                if not k:
                    continue
                vectors = {"dense": [float(x) for x in vec]}
                if p["vector"].get("sparse") is not None:
                    vectors["sparse"] = p["vector"]["sparse"]
                points.append(
                    {"id": p["id"], "vector": vectors, "payload": p["payload"]}
                )
            if points:
                copy_call(f"/collections/{DEST}/points?wait=true", {"points": points})
            with LOCK:
                for p, o in zip(pts, oldv):
                    old[pos[p["id"]]] = o
                old.flush()
                with COSINES.open("a") as f:
                    for p, c, k in zip(pts, cos, keep):
                        f.write(
                            f"{p['id']}\t{c:.5f}\t{'written' if k else 'skipped'}\n"
                        )
                with SKIPPED.open("a") as f:
                    for p, c, k in zip(pts, cos, keep):
                        if not k:
                            f.write(
                                f"{p['id']}\t{p['payload'].get('chunk_id')}\t{c:.5f}\n"
                            )
                nw = int(keep.sum())
                with DONE.open("a") as f:
                    f.write(f"{bi}\t{nw}\t{len(pts) - nw}\n")
                    f.flush()
                    os.fsync(f.fileno())
                state["written"] += nw
                state["skipped"] += len(pts) - nw
                state["batches"] += 1
        except CapReached as exc:
            state["capped"] = str(exc)
            STOP.set()
        except BaseException as exc:  # noqa: BLE001
            state["error"] = f"batch {bi}: {exc}"
            STOP.set()
        finally:
            sem.release()

    with ThreadPoolExecutor(WORKERS) as ex:
        for n, bi in enumerate(todo, 1):
            if STOP.is_set():
                break
            sem.acquire()
            if STOP.is_set():
                sem.release()
                break
            pts = orig_retrieve(batches[bi])
            ex.submit(work, bi, pts)
            if n % 25 == 0:
                el = time.time() - t0
                rate = state["batches"] / el if el else 0
                print(
                    f"{state['batches']:,}/{len(todo):,} batches | written {state['written']:,} skipped {state['skipped']:,} | tokens on ledger {budget.used:,} | {el / 60:.1f} min | eta {(len(todo) - state['batches']) / rate / 60 if rate else 0:.0f} min | slowest original read {max(ORIG_LOG):.2f}s",
                    flush=True,
                )
    old.flush()
    print(
        f"END: batches this run {state['batches']}, written {state['written']:,}, skipped {state['skipped']:,}, tokens on ledger {budget.used:,}, {(time.time() - t0) / 60:.1f} min, original reads {len(ORIG_LOG)} (slowest {max(ORIG_LOG) if ORIG_LOG else 0:.2f}s)"
    )
    if state["capped"]:
        print(f"STOPPED AT THE SPEND CAP: {state['capped']}")
        sys.exit(4)
    if state["error"]:
        print(f"STOPPED ON AN ERROR: {state['error']}")
        sys.exit(5)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["preflight", "run"])
    ap.add_argument(
        "--model", default=None, help="refused unless identical to the recorded model"
    )
    ap.add_argument("--max-batches", type=int, default=None)
    a = ap.parse_args()
    key = os.environ.get("VOYAGE_API_KEY") or sys.exit(
        "no VOYAGE_API_KEY in the environment"
    )
    model = resolve_model(a.model)
    FIX.mkdir(parents=True, exist_ok=True)
    if a.command == "preflight":
        preflight(model, key)
    else:
        run(model, key, a.max_batches)


if __name__ == "__main__":
    main()
