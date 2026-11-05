"""The three-model document comparison again, on chunks drawn from the MISSING SET itself (A141, A143).

`model_choice.py` used the A136 evaluation corpus: chunks of 3,260 characters on average. The chunks a backfill would buy
embeddings for are 93.8% single-chunk cases averaging 2,299 characters, many far shorter, and model behaviour on short
documents was unmeasured. This repeats the method on a corpus of 2,000 chunks drawn UNIFORMLY from the whole-missing
English chunks (DATA-GAPS section 19; row positions cached by `scan/missing_rows.py`).

Same method as `model_choice.py`: each chunk embedded under `voyage-4-lite`, `voyage-4` and `voyage-4-large` (1,024
dimensions, `input_type: "document"`, through `adapters/voyage.py`); three scratch collections on the COPY instance with
identical ids, payload and BM25 vectors that differ only in the dense vector; one `voyage-4` query vector throughout (the
production setting, A136); both query styles; cluster bootstrap over targets; dense and hybrid reported together.

What is different, on purpose:
  * the corpus is the missing set, so its length distribution is the one being bought;
  * 250 TARGETS are drawn among chunks that can yield a query. A136 required three sentences and 700 characters, which
    would silently exclude the short orders this run is about; here a target needs ONE sentence of 40-260 characters with
    at least 6 words, and the chunk at least 300 characters. The share of the corpus that qualifies is printed;
  * the exact Voyage token count of the corpus is computed locally BEFORE any spend (data/voyage_token_count.py);
  * results are also split at the median target length, because short text is the question.

Stages (the first two need `pyarrow`, `tokenizers`, `fastembed`: see evals/a141/README.md; the rest run in the repo .venv):
  sample    draw the corpus and the targets, count tokens exactly, BM25 vectors, sentence queries, paraphrase input files
  validate  read the paraphrases the writers returned, apply the A136 validator, BM25 vectors for every query
  queries --go   embed the queries with voyage-4 (the only query spend)
  embed --go     embed the corpus under the three models (the document spend)
  build / run
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import re
import time
import urllib.request
from pathlib import Path

import numpy as np

from evals.a136.paths import DATA, REPO
from evals.a141.stats import K_LIST, diff_ci, recall

COPY = "http://127.0.0.1:7333"
SOURCE = "a128_multicourt"
TAG = "a141x"
COLL = {
    "voyage-4-lite": f"{TAG}_lite",
    "voyage-4": f"{TAG}_v4",
    "voyage-4-large": f"{TAG}_large",
}
REP = {
    "voyage-4-lite": "APHC",
    "voyage-4": "KLHC",
    "voyage-4-large": "INSC",
}  # court codes the registry maps to each model
PRICE = {"voyage-4-lite": 0.02, "voyage-4": 0.06, "voyage-4-large": 0.12}
N_CHUNKS = 2000
N_TARGETS = 250
SEED = 41130
BATCH = 48
SPEND_CAP_USD = 0.45  # list price, documents plus queries; stops loudly past it
HOME = Path.home() / "qdrant-kanoon" / "coverage_gap"
LEDGER = Path.home() / "qdrant-kanoon" / "kerala_fix" / "token_ledger.jsonl"
CORPUS = DATA / f"{TAG}_corpus.json"
QUERIES = DATA / f"{TAG}_queries.json"
QGEN = DATA / f"{TAG}_qgen"
QVEC = DATA / f"{TAG}_qvec.npy"


def vec_path(m: str) -> Path:
    return DATA / f"{TAG}_dense_{m}.npy"


# --- query construction (A136's recipe with the eligibility floor lowered, see the module docstring) -------------------
def body_of(t: str) -> str:
    return t.split("\n\n", 1)[1] if "\n\n" in t else t


def sentences(t: str) -> list[str]:
    ss = [s.strip() for s in re.split(r"(?<=[.;])\s+", re.sub(r"\s+", " ", body_of(t)))]
    ok = [
        s
        for s in ss
        if 40 <= len(s) <= 260 and len(re.findall(r"[A-Za-z]{3,}", s)) >= 6
    ]
    return sorted(ok, key=len, reverse=True)


def strip(s: str) -> str:
    return " ".join(
        x for x in s.split() if not re.search(r"\d", x) and not x[:1].isupper()
    )


def sentence_queries(text: str) -> list[str]:
    ss = sentences(text)
    out = [ss[0]]
    if len(ss) >= 2 and ss[len(ss) // 2] != ss[0]:
        out.append(ss[len(ss) // 2])
    b = strip(ss[0])
    if len(b.split()) >= 8:
        out.append(b)
    return list(dict.fromkeys(out))


OK_WORDS = {
    "court", "act", "article", "constitution", "india", "indian", "high", "supreme", "section", "code", "state",
    "government", "what", "when", "whether", "how", "why", "can", "does", "is", "are", "who", "which", "under", "in",
    "if", "may", "must", "should", "do", "did", "will", "would", "a", "an", "the", "i",
}  # fmt: skip


def leaks(q: str, chunk: str) -> list[str]:
    """The A136 validator: no digit, no reused capitalised name, no 4-word run from the chunk, 8-40 words ending '?'."""
    r = []
    if re.search(r"\d", q):
        r.append("digits")
    cc = set(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", chunk))
    if [
        t
        for t in re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", q)[1:]
        if t in cc and t.lower() not in OK_WORDS
    ]:
        r.append("names")
    words = lambda s: re.findall(r"[a-z0-9]+", s.lower())  # noqa: E731
    cw, qw = words(chunk), words(q)
    g4 = {tuple(cw[i : i + 4]) for i in range(len(cw) - 3)}
    if any(tuple(qw[i : i + 4]) in g4 for i in range(len(qw) - 3)):
        r.append("4gram")
    if not (8 <= len(qw) <= 40) or not q.strip().endswith("?"):
        r.append("format")
    return r


# --- stage: sample -----------------------------------------------------------------------------------------------------
def sample() -> None:
    import pyarrow.parquet as pq
    from fastembed import SparseTextEmbedding

    from data import voyage_token_count as vtc
    from scan import coverage_gap as g
    from scan.missing_rows import load_rows

    files = sorted(g.PARQUET_DIR.glob("in_*_judgments.parquet"))
    rows = {
        f.stem: load_rows(HOME, f.stem)
        for f in files
        if (HOME / "missing_rows" / f"{f.stem}.npy").exists()
    }
    if len(rows) != len(files):
        raise SystemExit(
            "scan/missing_rows.py has not finished: not all files are cached"
        )
    stems = list(rows)
    bounds = np.cumsum([0] + [len(rows[s]) for s in stems])
    total = int(bounds[-1])
    rng = np.random.default_rng(SEED)
    draw = np.sort(rng.choice(total, size=int(N_CHUNKS * 1.15), replace=False))
    picked: list[dict] = []
    for fi, stem in enumerate(stems):
        sel = draw[(draw >= bounds[fi]) & (draw < bounds[fi + 1])] - bounds[fi]
        if not len(sel):
            continue
        pf = pq.ParquetFile(g.PARQUET_DIR / f"{stem}.parquet")
        starts = np.cumsum(
            [0]
            + [
                pf.metadata.row_group(i).num_rows
                for i in range(pf.metadata.num_row_groups)
            ]
        )
        pos = rows[stem][sel]
        grp = np.searchsorted(starts, pos, side="right") - 1
        for rg in np.unique(grp):
            t = pf.read_row_group(
                int(rg), columns=["chunk_id", "case_id", "court_code", "year", "text"]
            )
            take = (pos[grp == rg] - starts[rg]).tolist()
            picked += t.take(take).to_pylist()
    seen_cases: set[str] = set()
    corpus: list[dict] = []
    for r in sorted(
        picked, key=lambda r: g.H(r["chunk_id"])
    ):  # a fixed order that does not favour any court
        if r["case_id"] in seen_cases or not r["text"]:
            continue
        seen_cases.add(r["case_id"])
        corpus.append(
            {
                "id": g.H(r["chunk_id"]),
                "chunk_id": r["chunk_id"],
                "code": g.code_of(
                    r["chunk_id"]
                ),  # from the record id, never the numeric parquet `court_code` (CLAUDE.md section 6)
                "year": r["year"],
                "text": r["text"],
            }
        )
        if len(corpus) == N_CHUNKS:
            break
    if len(corpus) < N_CHUNKS:
        raise SystemExit(f"only {len(corpus)} usable chunks drawn")
    tokens = vtc.billed_tokens([c["text"] for c in corpus])
    for c, n in zip(corpus, tokens):
        c["tokens"] = n
        c["chars"] = len(c["text"])
    enc = SparseTextEmbedding(model_name="Qdrant/bm25")
    for c, e in zip(corpus, enc.embed([c["text"] for c in corpus])):
        c["sparse"] = {"indices": e.indices.tolist(), "values": e.values.tolist()}
    eligible = [
        i for i, c in enumerate(corpus) if c["chars"] >= 300 and sentences(c["text"])
    ]
    tgt = set(
        np.random.default_rng(SEED + 1)
        .choice(eligible, size=N_TARGETS, replace=False)
        .tolist()
    )
    for i, c in enumerate(corpus):
        c["target"] = i in tgt
    queries = [
        {"id": c["id"], "code": c["code"], "style": "sentence", "text": q}
        for c in corpus
        if c["target"]
        for q in sentence_queries(c["text"])
    ]
    QGEN.mkdir(exist_ok=True)
    ids = [c for c in corpus if c["target"]]
    for k in range(4):
        part = [
            {"id": str(c["id"]), "passage": body_of(c["text"])[:2200]}
            for c in ids[k::4]
        ]
        (QGEN / f"in_{k}.json").write_text(json.dumps(part, ensure_ascii=False))
    CORPUS.write_text(json.dumps(corpus))
    QUERIES.write_text(json.dumps(queries))
    toks = np.array(tokens)
    tt = np.array([c["tokens"] for c in corpus if c["target"]])
    tot = int(toks.sum())
    print(
        f"{len(corpus)} chunks drawn uniformly from {total:,} missing-set rows; {len(eligible)} ({len(eligible) / len(corpus):.0%}) can yield a query"
    )
    print(
        f"tokens per chunk: mean {toks.mean():.0f}, median {np.median(toks):.0f}, p10 {np.percentile(toks, 10):.0f}, p90 {np.percentile(toks, 90):.0f}; chars mean {np.mean([c['chars'] for c in corpus]):,.0f}"
    )
    print(
        f"targets: {len(tt)}, tokens median {np.median(tt):.0f} (corpus median {np.median(toks):.0f}); {len(queries)} sentence-style queries"
    )
    print(
        "courts:", dict(collections.Counter(c["code"] for c in corpus).most_common(8))
    )
    print(
        f"EXACT document tokens: {tot:,} per model; list price lite ${tot * 0.02 / 1e6:.4f}  voyage-4 ${tot * 0.06 / 1e6:.4f}  large ${tot * 0.12 / 1e6:.4f}  all three ${tot * 0.2 / 1e6:.4f}"
    )


# --- stage: validate ---------------------------------------------------------------------------------------------------
def validate() -> None:
    from fastembed import SparseTextEmbedding

    corpus = json.loads(CORPUS.read_text())
    queries = json.loads(QUERIES.read_text())
    text = {c["id"]: c["text"] for c in corpus}
    code = {c["id"]: c["code"] for c in corpus if c["target"]}
    cand: dict[int, list[str]] = collections.defaultdict(list)
    for f in sorted(QGEN.glob("out_*.json")):
        for k, qs in json.loads(f.read_text()).items():
            cand[int(k)] += [q for q in qs if isinstance(q, str)]
    total = rej = 0
    reasons: collections.Counter = collections.Counter()
    per: collections.Counter = collections.Counter()
    for tid, c in code.items():
        good: list[str] = []
        for q in cand.get(tid, []):
            total += 1
            r = leaks(q, body_of(text[tid]))
            if r:
                rej += 1
                reasons.update(r)
            elif q not in good and len(good) < 2:
                good.append(q)
        per[len(good)] += 1
        queries += [
            {"id": tid, "code": c, "style": "paraphrase", "text": q} for q in good
        ]
    enc = SparseTextEmbedding(model_name="Qdrant/bm25")
    sparse = {}
    for q in queries:
        if q["text"] not in sparse:
            e = next(iter(enc.query_embed([q["text"]])))
            sparse[q["text"]] = (
                [int(i) for i in e.indices],
                [float(v) for v in e.values],
            )
    QUERIES.write_text(json.dumps(queries))
    (DATA / f"{TAG}_sparse.json").write_text(json.dumps(sparse))
    print(
        f"paraphrases received {total}; rejected {rej} ({rej / max(total, 1):.1%}) {dict(reasons)}; targets with 2 valid {per[2]}, 1 valid {per[1]}, 0 valid {per[0]} of {len(code)}"
    )
    print(
        "queries:",
        dict(collections.Counter(q["style"] for q in queries)),
        f"; {len(sparse)} sparse query vectors",
    )


# --- stages that talk to Voyage (repo .venv) -----------------------------------------------------------------------------
def _client():
    from adapters.voyage import VoyageClient
    from core.settings import Settings

    key = next(
        (
            line.split("=", 1)[1].strip().strip("'\"")
            for line in open(REPO / ".env")
            if line.startswith("VOYAGE_API_KEY=")
        ),
        None,
    )
    if not key:
        raise SystemExit(
            "no VOYAGE_API_KEY line in the repo .env"
        )  # the key is never printed
    s = Settings(_env_file=None, VOYAGE_API_KEY=key)
    for m, code in REP.items():
        if s.embed_model_for("legal_corpus_v2", code) != m:
            raise SystemExit(
                f"the registry does not map {code} to {m}; stopping before any call"
            )
    return VoyageClient(s, timeout_s=120, max_attempts=6)


def _ledger(model: str, tag: str, tokens: int) -> None:
    with open(LEDGER, "a") as f:
        f.write(
            json.dumps({"t": time.time(), "model": model, "tokens": tokens, "tag": tag})
            + "\n"
        )


async def embed_queries() -> None:
    if QVEC.exists():
        raise SystemExit(f"{QVEC.name} exists: refusing to spend twice")
    c = _client()
    queries = json.loads(QUERIES.read_text())
    texts = [q["text"] for q in queries]
    out = np.zeros((len(texts), 1024), dtype=np.float32)
    tok = 0
    for i in range(0, len(texts), 64):
        b = await c.embed_batch(
            texts[i : i + 64], "legal_corpus_v2", "query", court_code=REP["voyage-4"]
        )
        out[i : i + 64] = np.array(b.vectors)
        tok += b.total_tokens
        _ledger("voyage-4", f"a141x query batch {i // 64}", b.total_tokens)
    np.save(QVEC, out)
    print(
        f"{len(texts)} queries embedded with voyage-4: {tok:,} tokens, ${tok * PRICE['voyage-4'] / 1e6:.5f} at list"
    )


async def embed_docs() -> None:
    for m in REP:
        if vec_path(m).exists():
            raise SystemExit(f"{vec_path(m).name} exists: refusing to spend twice")
    c = _client()
    corpus = json.loads(CORPUS.read_text())
    texts = [r["text"] for r in corpus]
    expected = sum(r["tokens"] for r in corpus)
    spent = 0.0
    result: dict = {"expected_tokens_each_model": expected}
    for m, code in REP.items():
        out = np.zeros((len(texts), 1024), dtype=np.float32)
        tok = 0
        for i in range(0, len(texts), BATCH):
            b = await c.embed_batch(
                texts[i : i + BATCH], "legal_corpus_v2", "document", court_code=code
            )
            out[i : i + BATCH] = np.array(b.vectors)
            tok += b.total_tokens
            spent += b.total_tokens * PRICE[m] / 1e6
            _ledger(m, f"a141x model-choice {m} batch {i // BATCH}", b.total_tokens)
            if spent > SPEND_CAP_USD:
                raise SystemExit(
                    f"STOP: list-price spend ${spent:.3f} passed the ${SPEND_CAP_USD} cap at {m}"
                )
        np.save(vec_path(m), out)
        result[m] = {"tokens": tok, "usd_list": tok * PRICE[m] / 1e6}
        print(
            m,
            result[m],
            f"(local count {expected:,}, difference {tok - expected:+,})",
            flush=True,
        )
    result["total_tokens"] = sum(result[m]["tokens"] for m in REP)
    result["total_usd_list"] = sum(result[m]["usd_list"] for m in REP)
    (DATA / f"{TAG}_spend.json").write_text(json.dumps(result, indent=1))
    print(
        f"TOTAL {result['total_tokens']:,} tokens, ${result['total_usd_list']:.4f} at list price"
    )


# --- stages on the copy instance ---------------------------------------------------------------------------------------
def call(method: str, path: str, body: dict | None = None) -> dict:
    """The copy instance only; the only writes are to the three scratch collections."""
    if method != "GET" and not any(
        path.startswith(f"/collections/{c}") for c in COLL.values()
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
    corpus = json.loads(CORPUS.read_text())
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
        for i in range(0, len(corpus), 100):
            pts = [
                {
                    "id": r["id"],
                    "vector": {"dense": dense[i + j].tolist(), "sparse": r["sparse"]},
                    "payload": {"chunk_id": r["chunk_id"], "court_code": r["code"]},
                }
                for j, r in enumerate(corpus[i : i + 100])
            ]
            call("PUT", f"/collections/{name}/points?wait=true", {"points": pts})
        n = call("POST", f"/collections/{name}/points/count", {"exact": True})["count"]
        print(f"{name}: {n:,} points ({m})")


async def run_queries(queries, qv, sparse, tgt) -> list[dict]:
    from adapters.qdrant import QdrantStore
    from core.settings import Settings

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
                    name, qv[i].tolist(), q["text"], mode, tgt[q["id"]]
                )
        rows.append(r)
    return rows


def run() -> None:
    corpus = json.loads(CORPUS.read_text())
    queries = json.loads(QUERIES.read_text())
    qv = np.load(QVEC)
    sparse = {
        k: tuple(v)
        for k, v in json.loads((DATA / f"{TAG}_sparse.json").read_text()).items()
    }
    tgt = {c["id"]: c["chunk_id"] for c in corpus if c["target"]}
    toks = {c["id"]: c["tokens"] for c in corpus if c["target"]}
    median = float(np.median(list(toks.values())))
    rows = asyncio.run(run_queries(queries, qv, sparse, tgt))
    for r in rows:
        r["short"] = toks[r["id"]] <= median
    rng = np.random.default_rng(13)
    out: dict = {"queries": len(rows), "median_target_tokens": median, "slices": {}}
    slices = {
        "both styles": rows,
        "sentence": [r for r in rows if r["style"] == "sentence"],
        "paraphrase": [r for r in rows if r["style"] == "paraphrase"],
        f"shorter half of targets (<= {median:.0f} tokens), both styles": [
            r for r in rows if r["short"]
        ],
        f"longer half of targets (> {median:.0f} tokens), both styles": [
            r for r in rows if not r["short"]
        ],
    }
    for name, sub in slices.items():
        res: dict = {"queries": len(sub), "targets": len({r["id"] for r in sub})}
        for mode in ("dense", "hybrid"):
            for k in K_LIST:
                key = f"{mode}@{k}"
                res[key] = {"recall": {m: recall(sub, f"{m}|{mode}", k) for m in COLL}}
                res[key]["diff_vs_voyage-4"] = {
                    m: diff_ci(sub, "voyage-4|" + mode, f"{m}|{mode}", k, rng)
                    for m in ("voyage-4-lite", "voyage-4-large")
                }
        out["slices"][name] = res
    (DATA / f"{TAG}_results.json").write_text(json.dumps({**out, "rows": rows}))
    for name, res in out["slices"].items():
        print(f"\n== {name}: {res['queries']} queries, {res['targets']} targets")
        for mode in ("dense", "hybrid"):
            for k in K_LIST:
                r = res[f"{mode}@{k}"]
                print(
                    f"  {mode:6}@{k:<3} recall "
                    + "  ".join(f"{m} {v:5.1f}" for m, v in r["recall"].items())
                )
                for m, (pt, lo, hi, gn, lost) in r["diff_vs_voyage-4"].items():
                    print(
                        f"           {m} minus voyage-4: {pt:+5.1f} [{lo:+5.1f},{hi:+5.1f}] gained/lost {gn}/{lost}"
                    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "stage", choices=["sample", "validate", "queries", "embed", "build", "run"]
    )
    ap.add_argument(
        "--go",
        action="store_true",
        help="required for `queries` and `embed`, the stages that spend",
    )
    a = ap.parse_args()
    if a.stage in ("queries", "embed") and not a.go:
        raise SystemExit(f"{a.stage} spends Voyage tokens; pass --go")
    {
        "sample": sample,
        "validate": validate,
        "queries": lambda: asyncio.run(embed_queries()),
        "embed": lambda: asyncio.run(embed_docs()),
        "build": build,
        "run": run,
    }[a.stage]()


if __name__ == "__main__":
    main()
