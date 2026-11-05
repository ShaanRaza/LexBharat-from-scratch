"""Step 1 of the Supreme Court embed (A129): the BM25 sparse vectors, NO API call.

Pipeline step touched: none at runtime (data preparation for step 5, Search, in a staging
collection). Run with an interpreter that has `fastembed` (it is not in the repo venv):

    ~/<scratch>/fe_venv/bin/python data/dead_vectors/embed_sc_sparse.py

Reads ~/qdrant-kanoon/reports/part7_new_chunks.jsonl (the 10,112 English Supreme Court chunks the
parquet holds and Qdrant lacks). Writes ~/qdrant-kanoon/sc_new/sparse.jsonl, one line per chunk.
Self-check first: 20 stored Supreme Court points in `kanoon_v1` (copy instance, port 7333, read only)
must be reproduced by this encoder (same indices, values within 1e-4), or nothing is written.
"""

import json
import os
import random
import sys
import urllib.request

HOME = os.path.expanduser("~/qdrant-kanoon")
CHUNKS = f"{HOME}/reports/part7_new_chunks.jsonl"
WORK = f"{HOME}/sc_new"
COPY = "http://127.0.0.1:7333"  # the copy instance; never the original on 6333


def http(path: str, body: dict) -> dict:
    assert COPY.endswith(":7333")
    req = urllib.request.Request(  # noqa: S310 - fixed loopback http base, so no file: or custom scheme
        COPY + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=300))  # noqa: S310


def main() -> None:
    from fastembed import SparseTextEmbedding

    enc = SparseTextEmbedding(model_name="Qdrant/bm25")

    # --- self-check: the encoder reproduces the sparse vectors already stored for SC chunks
    flt = {"must": [{"key": "court", "match": {"value": "Supreme Court of India"}}]}
    pts, off = [], None
    while len(pts) < 400:
        r = http(
            "/collections/kanoon_v1/points/scroll",
            {
                "limit": 200,
                "offset": off,
                "filter": flt,
                "with_payload": ["text"],
                "with_vector": ["sparse"],
            },
        )["result"]
        pts += r["points"]
        off = r["next_page_offset"]
        if off is None:
            break
    pick = random.Random(11).sample(pts, 20)  # noqa: S311 - seeded, reproducible verification sample, not a secret
    bad = 0
    for p, s in zip(pick, enc.embed([p["payload"]["text"] for p in pick])):
        st = p["vector"]["sparse"]
        same_idx = sorted(s.indices.tolist()) == sorted(st["indices"])
        a = dict(zip(s.indices.tolist(), s.values.tolist()))
        b = dict(zip(st["indices"], st["values"]))
        close = same_idx and all(abs(a[i] - b[i]) < 1e-4 for i in b)
        bad += not close
    print(f"sparse self-check: {20 - bad} of 20 stored SC points reproduced")
    if bad:
        sys.exit("STOP: the BM25 encoder does not reproduce the stored sparse vectors")

    # --- the new chunks
    chunks = [json.loads(line) for line in open(CHUNKS)]
    os.makedirs(WORK, exist_ok=True)
    texts = [c["payload"]["text"] for c in chunks]
    n = 0
    with open(f"{WORK}/sparse.jsonl", "w") as out:
        for i in range(0, len(texts), 256):
            for c, s in zip(chunks[i : i + 256], enc.embed(texts[i : i + 256])):
                out.write(
                    json.dumps(
                        {
                            "id": int(c["id"]),
                            "indices": s.indices.tolist(),
                            "values": s.values.tolist(),
                        }
                    )
                    + "\n"
                )
                n += 1
    print(f"wrote {n:,} sparse vectors to {WORK}/sparse.jsonl")


if __name__ == "__main__":
    main()
