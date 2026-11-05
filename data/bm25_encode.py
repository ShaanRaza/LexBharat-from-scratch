#!/usr/bin/env python3
"""Document-side BM25 sparse vectors, made the way data/repair_act_sparse.py made the repaired ones
(FastEmbed `Qdrant/bm25`, embed()). stdin: JSON lines {"id", "text"}; stdout: {"id", "indices", "values"}.
Needs fastembed, which the repo venv does not have; run it with an interpreter that does.
No network call to a vendor; fastembed reads its model from the local cache."""

import json
import sys

from fastembed import SparseTextEmbedding

rows = [json.loads(ln) for ln in sys.stdin if ln.strip()]
enc = SparseTextEmbedding(model_name="Qdrant/bm25")
for r, e in zip(rows, enc.embed([r["text"] for r in rows]), strict=True):
    print(
        json.dumps(
            {
                "id": r["id"],
                "indices": [int(i) for i in e.indices],
                "values": [float(v) for v in e.values],
            }
        )
    )
