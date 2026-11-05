"""Score stored dense vectors with the dead-vector detector. READ-ONLY.

Plain words: a few chunks in the corpus (about 7% of Kerala's High Court chunks in
`legal_corpus_v2`) carry a stored dense vector that is not an embedding of their text. Such
a chunk can never be found by dense search. The detector is one number per chunk:

    score = cosine(stored dense vector, legal_direction)

where `legal_direction.npy` is the mean direction of known-good chunks of other courts
(sources in `legal_direction_sources.json`). A real legal-text vector scores about 0.2 to
0.7; a dead one scores about 0 (measured on 450 Kerala chunks: dead at most +0.046, good at
least +0.159). A score below THRESHOLD (0.10) is flagged.

This script reads vectors from a Qdrant server with filtered scrolls, one request at a time,
a pause after each, and a hard stop (no retry) if a request fails or takes over 20 seconds.
It never writes to Qdrant. It appends one tab-separated line per chunk to --out and can be
re-run to resume a full scan.

  # every chunk of one court (resumable)
  python data/dead_vectors/score_dense_vectors.py --collection legal_corpus_v2 \
      --court "High Court of Kerala" --out kerala.tsv
  # the points that have no court value
  python data/dead_vectors/score_dense_vectors.py --collection legal_corpus_v2 \
      --no-court --out nocourt.tsv
  # about 5,000 chunks of one court from random places (for a prevalence check)
  python data/dead_vectors/score_dense_vectors.py --collection legal_corpus_v1 \
      --court "Bombay High Court" --sample 5000 --out bombay.tsv
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
THRESHOLD = 0.10
PAUSE_S = 0.25
HARD_STOP_S = 20
PAGE = 200
FIELDS = ["chunk_id", "char_start", "char_end", "chunk_index"]


def load_direction(path: Path = HERE / "legal_direction.npy") -> np.ndarray:
    d = np.load(path).astype(np.float64)
    return d / np.linalg.norm(d)


def score(vectors: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Cosine of each row of `vectors` with `direction`."""
    v = np.asarray(vectors, dtype=np.float64)
    return (v @ direction) / np.linalg.norm(v, axis=1)


def scroll(base: str, collection: str, body: dict) -> dict:
    """One read-only scroll request. Any failure or a slow answer stops the run."""
    req = urllib.request.Request(  # noqa: S310 (a URL the operator passes, http only)
        f"{base}/collections/{collection}/points/scroll",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(req, timeout=HARD_STOP_S).read()  # noqa: S310
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            f"HARD STOP: request failed or exceeded {HARD_STOP_S}s ({exc}). No retry."
        )
    if time.time() - t0 > HARD_STOP_S:
        sys.exit("HARD STOP: a request took longer than the limit. No retry.")
    time.sleep(PAUSE_S)
    return json.loads(raw)["result"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--collection", required=True)
    ap.add_argument("--court", help="exact court value (indexed `court` field)")
    ap.add_argument(
        "--no-court", action="store_true", help="points whose court is empty"
    )
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample", type=int, help="random-offset sample of about N chunks")
    ap.add_argument("--seed", type=int, default=20261103)
    ap.add_argument("--url", default="http://localhost:6333")
    a = ap.parse_args()
    if bool(a.court) == a.no_court:
        sys.exit("give exactly one of --court or --no-court")
    flt = (
        {"must": [{"key": "court", "match": {"value": a.court}}]}
        if a.court
        else {"must": [{"is_empty": {"key": "court"}}]}
    )
    direction = load_direction()
    state_path = Path(a.out + ".state")
    rnd = random.Random(a.seed)  # noqa: S311 (sampling, not security)
    state = {"offset": None, "n": 0, "pages": 0, "done": False}
    if a.sample is None and state_path.exists():
        state.update(json.loads(state_path.read_text()))
        keep = Path(a.out).read_text().splitlines(keepends=True)[: state["n"]]
        Path(a.out).write_text("".join(keep))  # drop a partly written page
    elif a.sample is None and Path(a.out).exists():
        Path(a.out).unlink()
    mode = "a" if a.sample is None and state["n"] else "w"
    t0, seen = time.time(), set()
    with open(a.out, mode) as out:
        while not state["done"] and (a.sample is None or state["n"] < a.sample):
            body = {
                "limit": PAGE,
                "filter": flt,
                "with_payload": FIELDS,
                "with_vector": ["dense"],
            }
            if a.sample:
                off = rnd.randrange(1 << 63)  # noqa: S311 (sampling, not security)
            else:
                off = state["offset"]
            if off is not None:
                body["offset"] = off
            res = scroll(a.url, a.collection, body)
            pts = [p for p in res["points"] if p["id"] not in seen]
            if pts:
                s = score(np.array([p["vector"]["dense"] for p in pts]), direction)
                for p, sc in zip(pts, s):
                    pl = p["payload"]
                    ln = (pl.get("char_end") or 0) - (pl.get("char_start") or 0)
                    seen.add(p["id"])
                    out.write(
                        f"{p['id']}\t{pl.get('chunk_id')}\t{sc:.5f}\t{ln}\t{pl.get('chunk_index')}\n"
                    )
                state["n"] += len(pts)
            state["pages"] += 1
            if a.sample is None:
                state["offset"] = res.get("next_page_offset")
                state["done"] = state["offset"] is None
                if state["pages"] % 50 == 0 or state["done"]:
                    out.flush()
                    os.fsync(out.fileno())
                    state_path.write_text(json.dumps(state))
            elif not pts and state["pages"] > 20 * (a.sample // PAGE + 5):
                break  # a small court: random offsets keep landing past its last point
            if state["pages"] % 100 == 0:
                print(
                    f"{state['n']:,} chunks, {(time.time() - t0) / 60:.1f} min",
                    flush=True,
                )
    if a.sample is None:
        state_path.write_text(json.dumps(state))
    print(
        f"DONE {state['n']:,} chunks scored -> {a.out} ({(time.time() - t0) / 60:.1f} min)"
    )


if __name__ == "__main__":
    main()
