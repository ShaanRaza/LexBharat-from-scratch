"""Embed every query under the THREE models (voyage-4, -lite, -large) through the real adapter, as the per-court search does (one embedding per model). Key: VOYAGE_API_KEY line only, never printed. Spend logged."""

import asyncio
import json
import os
import sys
import time

import numpy as np

from adapters.voyage import VoyageClient
from core.settings import Settings
from evals.a136.paths import DATA as S
from evals.a136.paths import REPO

key = next(
    (
        line.split("=", 1)[1].strip().strip("'\"")
        for line in open(f"{REPO}/.env")
        if line.startswith("VOYAGE_API_KEY=")
    ),
    None,
) or sys.exit("no key")
s = Settings(_env_file=None, VOYAGE_API_KEY=key)
c = VoyageClient(s, timeout_s=120, max_attempts=6)
Q = json.load(open(f"{S}/c_queries.json"))
texts = [q["text"] for q in Q]
REP = {"voyage-4": "KLHC", "voyage-4-large": "INSC"}
assert all(s.embed_model_for("legal_corpus_v2", code) == m for m, code in REP.items())


async def main():
    out = np.zeros((len(texts), 2, 1024), dtype=np.float32)
    tok = {}
    for mi, (m, code) in enumerate(REP.items()):
        for i in range(0, len(texts), 64):
            b = await c.embed_batch(
                texts[i : i + 64], "legal_corpus_v2", "query", court_code=code
            )
            out[i : i + 64, mi] = np.array(b.vectors)
            tok[m] = tok.get(m, 0) + b.total_tokens
    np.save(f"{S}/c_qvec.npy", out)
    L = os.path.expanduser("~/qdrant-kanoon/kerala_fix/token_ledger.jsonl")
    for m, t in tok.items():
        open(L, "a").write(
            json.dumps(
                {
                    "t": time.time(),
                    "model": m,
                    "tokens": t,
                    "tag": "a128 confirmation run queries",
                }
            )
            + "\n"
        )
    price = {"voyage-4": 0.06, "voyage-4-lite": 0.02, "voyage-4-large": 0.12}
    print(
        len(texts),
        "queries x 3 models; tokens",
        tok,
        f"~Rs {sum(t / 1e6 * price[m] for m, t in tok.items()) * 85:.2f}",
    )


asyncio.run(main())
