import asyncio
import json

import numpy as np

from adapters.qdrant import QdrantStore
from core.settings import Settings
from evals.a136.paths import DATA as S

C = "a128_multicourt"
settings = Settings(_env_file=None, QDRANT_URL="http://127.0.0.1:7333")
Q = json.load(open(f"{S}/c_queries.json"))
QV = np.load(f"{S}/c_qvec.npy")
sparse = {k: tuple(v) for k, v in json.load(open(f"{S}/c_sparse.json")).items()}
T = {t["id"]: t for t in json.load(open(f"{S}/c_targets.json"))["targets"]}
store = QdrantStore(settings, sparse_encoder=lambda t: sparse[t])
reg = settings.VOYAGE_COURT_MODELS["legal_corpus_v2"]


async def rank(vec, text, mode, target):
    ids = [h.record_id for h in await store.search(C, vec, text, {}, 50, mode=mode)]
    return ids.index(target) + 1 if target in ids else 51


async def main():
    rows = []
    for qi, q in enumerate(Q):
        tgt = T[q["id"]]["chunk_id"]
        r = {
            "id": q["id"],
            "code": q["code"],
            "style": q["style"],
            "model": reg[q["code"]],
        }
        for mode in ("dense", "hybrid"):
            r[f"a_{mode}"] = await rank(QV[qi, 0].tolist(), q["text"], mode, tgt)
            r[f"L_{mode}"] = await rank(QV[qi, 1].tolist(), q["text"], mode, tgt)
        rows.append(r)
    json.dump(rows, open(f"{S}/c_results.json", "w"))
    print("done", len(rows))


asyncio.run(main())
