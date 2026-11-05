"""Which document model for a backfill: voyage-4-lite, voyage-4 or voyage-4-large, on OUR matching task (A141).

Pipeline step 5 (Search) measurement; nothing here changes behaviour. Voyage publishes no quality numbers for these three
models and ours are about matching a query to a chunk, so this measures it on the A136 known-item harness.

Corpus: the 250 A136 target chunks plus 1,750 random other chunks of the A128 evaluation corpus (24 courts), 2,000 in all.
Every chunk is embedded three times, once per model, through `adapters/voyage.py` (the one Voyage call site, A127) with
`input_type: "document"` and `output_dimension: 1024`. Three scratch collections on the COPY instance (127.0.0.1:7333) hold
identical ids, payload and BM25 vectors and differ only in the dense vector. The same 1,161 A136 queries run against each
with the SAME `voyage-4` query vector (the production setting, A136; stored in `c_qvec.npy`, so no query spend).

Stages (the spend is only in `embed`, and it needs --go):
  python -m evals.a141.model_choice prepare   # pick chunks, read their text (read only on the original), project the cost
  python -m evals.a141.model_choice embed --go
  python -m evals.a141.model_choice build
  python -m evals.a141.model_choice run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.request
from pathlib import Path

import numpy as np

from evals.a136 import orig_ro as o
from evals.a136.paths import DATA, REPO
from evals.a141.stats import K_LIST, diff_ci, recall

COPY = "http://127.0.0.1:7333"
SOURCE = "a128_multicourt"
COLL = {
    "voyage-4-lite": "a141m_lite",
    "voyage-4": "a141m_v4",
    "voyage-4-large": "a141m_large",
}
REP = {"voyage-4-lite": "APHC", "voyage-4": "KLHC", "voyage-4-large": "INSC"}
PRICE = {
    "voyage-4-lite": 0.02,
    "voyage-4": 0.06,
    "voyage-4-large": 0.12,
}  # per 1M tokens, vendor page 4 Nov 2026
N_OTHER = 1750
SEED = 5150
BATCH = 48
TOKENS_PER_CHAR = (
    0.30,
    0.34,
)  # PROVISIONAL bracket for the projection only (Kerala ~1,240 tokens per ~3,800-char chunk); the real count comes from the API
SPEND_CAP_USD = 0.60  # list price, all three models; the run stops loudly past it
CORPUS = DATA / "a141m_corpus.json"
LEDGER = Path.home() / "qdrant-kanoon" / "kerala_fix" / "token_ledger.jsonl"


def vec_path(model: str) -> Path:
    return DATA / f"a141m_dense_{model}.npy"


def prepare() -> None:
    meta = json.loads((DATA / "a128_corpus_meta.json").read_text())
    tg = json.loads((DATA / "c_targets.json").read_text())
    targets = {t["id"]: t for t in tg["targets"]}
    text = {int(k): v for k, v in tg["text"].items()}
    pool = sorted(int(p) for p in meta if int(p) not in targets)
    other = sorted(
        np.random.default_rng(SEED).choice(pool, size=N_OTHER, replace=False).tolist()
    )
    for i in range(0, len(other), 20):
        got = o.q(
            "/collections/legal_corpus_v2/points",
            {"ids": other[i : i + 20], "with_payload": ["text"], "with_vector": False},
            f"txt {i}",
        )
        for p in got:
            text[p["id"]] = p["payload"]["text"]
    ids = sorted(targets) + other
    missing = [i for i in ids if not text.get(i)]
    if missing:
        raise SystemExit(f"no text for {len(missing)} chunks; not continuing")
    rows = [
        {
            "id": i,
            "chunk_id": meta[str(i)]["chunk_id"],
            "code": meta[str(i)]["court_code"],
            "text": text[i],
            "target": i in targets,
        }
        for i in ids
    ]
    CORPUS.write_text(json.dumps(rows))
    chars = sum(len(r["text"]) for r in rows)
    lo, hi = (chars * t for t in TOKENS_PER_CHAR)
    print(
        f"{len(rows)} chunks ({len(targets)} targets + {len(other)} others), {chars:,} characters, {chars / len(rows):,.0f} per chunk"
    )
    for m, p in PRICE.items():
        print(
            f"  {m:15} projected {lo / 1e6:.2f}-{hi / 1e6:.2f}M tokens = ${lo * p / 1e6:.3f}-${hi * p / 1e6:.3f} at list"
        )
    tot = sum(PRICE.values())
    print(
        f"  all three: ${lo * tot / 1e6:.2f}-${hi * tot / 1e6:.2f} at list (the brief said about $0.40); cap ${SPEND_CAP_USD}"
    )
    print(
        f"requests: {-(-len(rows) // BATCH) * 3} ({BATCH} chunks each); read-only calls on the original: {len(o.LOG)}"
    )


async def embed() -> None:
    from adapters.voyage import VoyageClient
    from core.settings import Settings

    key = next(
        (
            line.split("=", 1)[1].strip().strip("'\"")
            for line in open(REPO / ".env")
            if line.startswith("VOYAGE_API_KEY=")
        ),
        None,
    ) or raise_("no VOYAGE_API_KEY line in the repo .env")  # the key is never printed
    s = Settings(_env_file=None, VOYAGE_API_KEY=key)
    for m, code in REP.items():
        if s.embed_model_for("legal_corpus_v2", code) != m:
            raise SystemExit(
                f"the registry does not map {code} to {m}; stopping before any call"
            )
        if vec_path(m).exists():
            raise SystemExit(f"{vec_path(m).name} exists: refusing to spend twice")
    c = VoyageClient(s, timeout_s=120, max_attempts=6)
    rows = json.loads(CORPUS.read_text())
    texts = [r["text"] for r in rows]
    spent = 0.0
    result: dict = {}
    for m, code in REP.items():
        out = np.zeros((len(texts), 1024), dtype=np.float32)
        tok = 0
        t0 = time.time()
        for i in range(0, len(texts), BATCH):
            b = await c.embed_batch(
                texts[i : i + BATCH], "legal_corpus_v2", "document", court_code=code
            )
            out[i : i + BATCH] = np.array(b.vectors)
            tok += b.total_tokens
            spent += b.total_tokens * PRICE[m] / 1e6
            with open(LEDGER, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "t": time.time(),
                            "model": m,
                            "tokens": b.total_tokens,
                            "tag": f"model-choice {m} batch {i // BATCH}",
                        }
                    )
                    + "\n"
                )
            if spent > SPEND_CAP_USD:
                raise SystemExit(
                    f"STOP: list-price spend ${spent:.3f} passed the ${SPEND_CAP_USD} cap at {m} batch {i // BATCH}"
                )
        np.save(vec_path(m), out)
        result[m] = {
            "tokens": tok,
            "usd_list": tok * PRICE[m] / 1e6,
            "seconds": time.time() - t0,
        }
        print(m, result[m], flush=True)
    result["total_tokens"] = sum(v["tokens"] for v in result.values())
    result["total_usd_list"] = sum(
        v["usd_list"] for k, v in result.items() if k in PRICE
    )
    (DATA / "a141m_spend.json").write_text(json.dumps(result, indent=1))
    print(
        f"TOTAL {result['total_tokens']:,} tokens, ${result['total_usd_list']:.4f} at list price"
    )


def raise_(msg: str):
    raise SystemExit(msg)


def call(method: str, path: str, body: dict | None = None) -> dict:
    """The copy instance only; the only writes are to the three scratch collections."""
    if method != "GET" and not (
        any(path.startswith(f"/collections/{c}") for c in COLL.values())
        or (method == "POST" and path.startswith(f"/collections/{SOURCE}/points"))
    ):
        raise SystemExit(f"refused: {method} {path}")
    req = urllib.request.Request(  # noqa: S310 - fixed loopback http base
        COPY + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["result"]  # noqa: S310


def build() -> None:
    rows = json.loads(CORPUS.read_text())
    ids = [r["id"] for r in rows]
    sparse: dict[int, dict] = {}
    for i in range(0, len(ids), 200):
        for p in call(
            "POST",
            f"/collections/{SOURCE}/points",
            {"ids": ids[i : i + 200], "with_vector": ["sparse"], "with_payload": False},
        ):
            sparse[p["id"]] = p["vector"]["sparse"]
    if len(sparse) != len(ids):
        raise SystemExit(
            f"{len(ids) - len(sparse)} chunks have no stored BM25 vector in {SOURCE}"
        )
    cfg = call("GET", f"/collections/{SOURCE}")["config"]["params"]
    have = [c["name"] for c in call("GET", "/collections")["collections"]]
    for m, name in COLL.items():
        if name in have:
            raise SystemExit(f"{name} exists; refusing to mix runs")
        dense = np.load(vec_path(m))
        call(
            "PUT",
            f"/collections/{name}",
            {
                "vectors": cfg["vectors"],
                "sparse_vectors": cfg["sparse_vectors"],
                "on_disk_payload": True,
            },
        )
        for i in range(0, len(rows), 100):
            pts = [
                {
                    "id": r["id"],
                    "vector": {
                        "dense": dense[i + j].tolist(),
                        "sparse": sparse[r["id"]],
                    },
                    "payload": {"chunk_id": r["chunk_id"], "court_code": r["code"]},
                }
                for j, r in enumerate(rows[i : i + 100])
            ]
            call("PUT", f"/collections/{name}/points?wait=true", {"points": pts})
        n = call("POST", f"/collections/{name}/points/count", {"exact": True})["count"]
        print(f"{name}: {n:,} points ({m})")


async def run_queries() -> list[dict]:
    from adapters.qdrant import QdrantStore
    from core.settings import Settings

    queries = json.loads((DATA / "c_queries.json").read_text())
    qv = np.load(DATA / "c_qvec.npy")  # [:, 0] is the voyage-4 query vector
    sparse = {
        k: tuple(v) for k, v in json.loads((DATA / "c_sparse.json").read_text()).items()
    }
    tgt = {
        t["id"]: t["chunk_id"]
        for t in json.loads((DATA / "c_targets.json").read_text())["targets"]
    }
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
        r = {"id": q["id"], "style": q["style"]}
        for m, name in COLL.items():
            for mode in ("dense", "hybrid"):
                r[f"{m}|{mode}"] = await rank(
                    name, qv[i, 0].tolist(), q["text"], mode, tgt[q["id"]]
                )
        rows.append(r)
    return rows


def run() -> None:
    rows = asyncio.run(run_queries())
    rng = np.random.default_rng(13)
    out: dict = {"queries": len(rows), "styles": {}}
    for style in ("sentence", "paraphrase", None):
        sub = [r for r in rows if style is None or r["style"] == style]
        res: dict = {"queries": len(sub), "targets": len({r["id"] for r in sub})}
        for mode in ("dense", "hybrid"):
            for k in K_LIST:
                key = f"{mode}@{k}"
                res[key] = {"recall": {m: recall(sub, f"{m}|{mode}", k) for m in COLL}}
                res[key]["diff_vs_voyage-4"] = {
                    m: diff_ci(sub, "voyage-4|" + mode, f"{m}|{mode}", k, rng)
                    for m in ("voyage-4-lite", "voyage-4-large")
                }
        out["styles"][style or "both"] = res
    (DATA / "a141m_results.json").write_text(json.dumps({**out, "rows": rows}))
    for name, res in out["styles"].items():
        print(f"\n== {name}: {res['queries']} queries, {res['targets']} targets")
        for mode in ("dense", "hybrid"):
            for k in K_LIST:
                r = res[f"{mode}@{k}"]
                print(
                    f"  {mode:6}@{k:<3} recall "
                    + "  ".join(f"{m} {v:5.1f}" for m, v in r["recall"].items())
                )
                for m, (pt, lo, hi, g, lost) in r["diff_vs_voyage-4"].items():
                    print(
                        f"           {m} minus voyage-4: {pt:+5.1f} [{lo:+5.1f},{hi:+5.1f}] gained/lost {g}/{lost}"
                    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prepare", "embed", "build", "run"])
    ap.add_argument(
        "--go",
        action="store_true",
        help="required for `embed`: this is the only stage that spends",
    )
    a = ap.parse_args()
    if a.stage == "prepare":
        prepare()
    elif a.stage == "embed":
        if not a.go:
            raise SystemExit(
                "embed spends Voyage tokens (about $0.5 at list); pass --go"
            )
        asyncio.run(embed())
    elif a.stage == "build":
        build()
    else:
        run()


if __name__ == "__main__":
    main()
