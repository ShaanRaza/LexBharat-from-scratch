"""Known-item retrieval: can the search find a chunk we already know exists?

Observes pipeline steps 5 (Search) and, through its recall@50 number, step 6 (Re-rank),
which only ever sees what step 5 returned. Decision A100.

Plain words: take a chunk from the corpus, build a query out of the chunk's OWN text,
run the search, and see where that chunk comes back (rank 1..50, or not at all). Do this
for a few hundred chunks and report:

  recall@10   share of chunks that came back in the top 10
  recall@50   share that came back in the top 50. THE NUMBER THAT MATTERS: step 6
              re-ranks the top 50, so a chunk inside 50 loses nothing downstream
  MRR         mean of 1/rank (0 when not found): how near the top they come

It runs three ways side by side: DENSE only (the Voyage vector), SPARSE only (BM25
keywords) and HYBRID (both, merged by RRF, which is what the product uses). BM25 does
not depend on the embedding model, so sparse is the control: if dense falls and hybrid
holds, the keyword half is absorbing the damage.

No human labels and no model downstream of retrieval. It never uses the Jev gate or a
re-ranker to grade anything (that would be circular).

WHAT THIS DOES NOT MEASURE
  * Not whether an answer is correct. Only whether a document we already know is
    relevant can be found. Answer quality needs labelled questions: a separate, later
    instrument (evals/README.md).
  * Not whether a REAL question reaches the right chunk. A query copied out of the chunk
    shares its words, so it flatters the keyword half (sparse) most. The query strategy
    biases the result: always read the number WITH its strategy, and compare runs only
    under the same one.
  * Not coverage: it only samples what is in the collection.
  * Near-identical chunks (repeated passages) can push the target below its twin; they
    count as misses here. Step 5 collapses such repeats afterwards (core/dedupe.py);
    this measurement looks at the raw search result before that.

Each stage is its own function (architecture rule 7): sample chunks, build a query,
search, score. Query construction is swappable: pass any `QueryBuilder`.

    .venv/bin/python -m evals.known_item --sample                  # offline demo, fakes
    .venv/bin/python -m evals.known_item --collection NAME --n 200 \\
        --strategy middle_sentence --where court=VALUE --out evals/results/run1.json

A real run reads Qdrant and calls Voyage (costs a little, needs keys). Not verified
live: only the fakes have run.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import math
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters.qdrant import EXACT_KEYS, Hit, SearchMode, VectorStore
from core.contracts import SEARCH_TOP_K
from core.search import hit_to_passage
from core.settings import UnknownEmbeddingModel

MODES: tuple[SearchMode, ...] = ("dense", "sparse", "hybrid")
KS = (10, SEARCH_TOP_K)


# --- 1. The slice and the chunks ------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    record_id: str
    text: str  # the body, with the "Case: ..." header already dropped


@dataclass(frozen=True)
class Slice:
    """Which part of the corpus to sample. `where` is exact payload matches (for example
    court=...); the id range is inclusive and compares record ids as text."""

    collection: str
    where: dict[str, str] = field(default_factory=dict)
    id_from: str | None = None
    id_to: str | None = None

    def must(self) -> dict[str, str]:
        bad = [k for k in self.where if k in EXACT_KEYS]
        if bad:
            # these switch the store to its exact-lookup path, which skips the very
            # search being measured
            raise ValueError(f"cannot slice on {bad}: that is the exact-lookup path")
        return dict(self.where)

    def holds(self, record_id: str) -> bool:
        return (self.id_from is None or record_id >= self.id_from) and (
            self.id_to is None or record_id <= self.id_to
        )


def chunk_from_hit(h: Hit) -> Chunk:
    return Chunk(h.record_id, hit_to_passage(h).text)


async def sample_chunks(store: VectorStore, sl: Slice, n: int) -> list[Chunk]:
    """Up to n random chunks of the slice (read-only). With an id range the store is
    asked for more, then cut down, so the range does not starve the sample; if the range
    is narrow you may still get fewer than n."""
    ask = n if sl.id_from is None and sl.id_to is None else n * 5
    hits = await store.sample_chunks(sl.collection, sl.must(), ask)
    chunks = [chunk_from_hit(h) for h in hits if sl.holds(h.record_id)]
    return [c for c in chunks if c.text.strip()][:n]


async def chunks_by_id(
    store: VectorStore, collection: str, ids: Sequence[str]
) -> list[Chunk]:
    """Re-load chunks from a previous run, so two runs measure the same chunks."""
    out = []
    for rid in ids:
        rec = await store.get_record(collection, rid)
        if rec is not None:
            out.append(chunk_from_hit(Hit(rec.record_id, rec.text, 0.0, rec.payload)))
    return out


# --- 2. Query construction (swappable) ------------------------------------------------

QueryBuilder = Callable[[Chunk], "str | Awaitable[str]"]

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def first_words(n: int = 30) -> QueryBuilder:
    """The first n words of the chunk."""

    def build(chunk: Chunk) -> str:
        return " ".join(chunk.text.split()[:n])

    return build


def middle_sentence(min_words: int = 8) -> QueryBuilder:
    """The sentence in the middle of the chunk (among those with at least min_words
    words); falls back to the first 30 words when no sentence is that long."""

    def build(chunk: Chunk) -> str:
        sentences = [
            s.strip()
            for s in _SENTENCE_END.split(" ".join(chunk.text.split()))
            if len(s.split()) >= min_words
        ]
        if not sentences:
            return first_words()(chunk)
        return sentences[len(sentences) // 2]

    return build


def paraphrased(paraphrase: Callable[[str], Awaitable[str]]) -> QueryBuilder:
    """A paraphrase of the middle sentence, written by `paraphrase` (a model call the
    caller supplies, so this file imports no model). The least flattering strategy for
    the keyword half: the words no longer match."""
    base = middle_sentence()

    async def build(chunk: Chunk) -> str:
        return await paraphrase(base(chunk))  # type: ignore[arg-type]

    return build


STRATEGIES: dict[str, Callable[[], QueryBuilder]] = {
    "first_words": first_words,
    "middle_sentence": middle_sentence,
}


async def build_queries(chunks: Sequence[Chunk], build: QueryBuilder) -> list[str]:
    out = []
    for c in chunks:
        q = build(c)
        out.append(await q if inspect.isawaitable(q) else q)
    return out


# --- 3. Search ------------------------------------------------------------------------

# query, mode -> record ids, best first (at most 50). Anything with this shape will do,
# which is what lets the tests use scripted retrievers and no store.
Retriever = Callable[[str, SearchMode], Awaitable[list[str]]]


def store_retriever(
    store: VectorStore,
    embedder: Any,
    collection: str,
    must: dict[str, str] | None = None,
    limit: int = SEARCH_TOP_K,
) -> Retriever:
    """Run the real search adapter in one mode. The query vector is embedded once per
    query and shared by the dense and hybrid runs. If the embedder fails, the run FAILS
    (it does not fall back to keyword-only the way the live pipeline does, which would
    quietly turn "dense" and "hybrid" into "sparse")."""
    vectors: dict[str, list[float]] = {}

    async def retrieve(query: str, mode: SearchMode) -> list[str]:
        vec = None
        if mode != "sparse":
            if query not in vectors:
                vectors[query] = await embedder.embed(query, collection)
            vec = vectors[query]
        hits = await store.search(collection, vec, query, must or {}, limit, mode)
        return [h.record_id for h in hits]

    return retrieve


# --- 4. Scoring -----------------------------------------------------------------------


def rank_of(target: str, ranked: Sequence[str]) -> int | None:
    """1-based place of the target in the results, or None if it did not come back."""
    for i, rid in enumerate(ranked, start=1):
        if rid == target:
            return i
    return None


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a share, so a 200-chunk number is not read as exact."""
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


@dataclass(frozen=True)
class Metrics:
    n: int
    recall: dict[int, float]
    recall_ci: dict[int, tuple[float, float]]
    mrr: float
    not_found: int  # chunks that did not come back at all


def score(ranks: Sequence[int | None], ks: Sequence[int] = KS) -> Metrics:
    """recall@k = share of chunks with rank <= k; MRR = mean of 1/rank (0 if absent)."""
    n = len(ranks)
    if n == 0:
        raise ValueError("nothing to score")
    hits = {k: sum(1 for r in ranks if r is not None and r <= k) for k in ks}
    return Metrics(
        n=n,
        recall={k: hits[k] / n for k in ks},
        recall_ci={k: wilson(hits[k], n) for k in ks},
        mrr=sum(1 / r for r in ranks if r is not None) / n,
        not_found=sum(1 for r in ranks if r is None),
    )


# --- 5. Run and report ----------------------------------------------------------------


@dataclass
class ModeResult:
    mode: str
    metrics: Metrics | None = None
    ranks: dict[str, int | None] = field(default_factory=dict)  # record_id -> rank
    error: str | None = None  # the mode could not run (e.g. model not recorded)


async def run_mode(
    mode: SearchMode,
    chunks: Sequence[Chunk],
    queries: Sequence[str],
    retrieve: Retriever,
    ks: Sequence[int] = KS,
    concurrency: int = 8,
) -> ModeResult:
    gate = asyncio.Semaphore(concurrency)

    async def one(chunk: Chunk, q: str) -> int | None:
        async with gate:
            return rank_of(chunk.record_id, await retrieve(q, mode))

    ranks = await asyncio.gather(*(one(c, q) for c, q in zip(chunks, queries)))
    return ModeResult(
        mode,
        score(ranks, ks),
        {c.record_id: r for c, r in zip(chunks, ranks)},
    )


# Errors that mean "this mode cannot run here", not "the code is wrong". Matched by name
# so this file imports no vendor module.
_MODE_ERRORS = ("UnknownEmbeddingModel", "VoyageUnavailable", "VectorStoreUnavailable")


async def run_known_item(
    chunks: Sequence[Chunk],
    build: QueryBuilder,
    retrieve: Retriever,
    modes: Sequence[SearchMode] = MODES,
    ks: Sequence[int] = KS,
) -> dict[str, ModeResult]:
    """Build the queries once, then run each mode on the same chunks and queries. A mode
    that cannot run is reported with its reason; the others still run."""
    if not chunks:
        raise ValueError("no chunks to measure: the slice is empty")
    queries = await build_queries(chunks, build)
    out: dict[str, ModeResult] = {}
    for mode in modes:
        try:
            out[mode] = await run_mode(mode, chunks, queries, retrieve, ks)
        except Exception as e:
            if type(e).__name__ not in _MODE_ERRORS:
                raise
            out[mode] = ModeResult(mode, error=f"{type(e).__name__}: {e}")
    return out


def to_json(
    results: dict[str, ModeResult], meta: dict[str, Any], ks: Sequence[int] = KS
) -> dict[str, Any]:
    """Machine-readable, secret-free, and no legal text: chunk ids and numbers only."""
    modes: dict[str, Any] = {}
    for mode, r in results.items():
        if r.metrics is None:
            modes[mode] = {"error": r.error}
            continue
        m = r.metrics
        modes[mode] = {
            "n": m.n,
            "not_found": m.not_found,
            "mrr": round(m.mrr, 4),
            **{f"recall@{k}": round(m.recall[k], 4) for k in ks},
            **{f"recall@{k}_ci95": [round(x, 4) for x in m.recall_ci[k]] for k in ks},
            "ranks": r.ranks,
        }
    return {"meta": meta, "modes": modes}


def render_table(results: dict[str, ModeResult], ks: Sequence[int] = KS) -> str:
    head = (
        f"{'mode':<8}{'n':>6}"
        + "".join(f"{f'recall@{k}':>12}" for k in ks)
        + f"{f'recall@{ks[-1]} 95% CI':>20}{'MRR':>8}{'missed':>8}"
    )
    lines = [head, "-" * len(head)]
    for mode, r in results.items():
        if r.metrics is None:
            lines.append(f"{mode:<8}  could not run: {r.error}")
            continue
        m = r.metrics
        lo, hi = m.recall_ci[ks[-1]]
        lines.append(
            f"{mode:<8}{m.n:>6}"
            + "".join(f"{m.recall[k]:>12.3f}" for k in ks)
            + f"{f'{lo:.3f} - {hi:.3f}':>20}{m.mrr:>8.3f}{m.not_found:>8}"
        )
    return "\n".join(lines)


# --- Command line ---------------------------------------------------------------------


def _parse_where(items: Sequence[str]) -> dict[str, str]:
    out = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise SystemExit(f"--where wants key=value, got {item!r}")
        out[key] = value
    return out


async def _sample_deps():
    """Offline demo: the practice chunks in the fake store. The fake ranks all three
    modes the same way, so the table shows the wiring, NOT the real difference between
    dense and sparse."""
    import gzip

    from adapters.qdrant import FakeVectorStore
    from adapters.voyage import FakeEmbedder
    from core.settings import Settings

    settings = Settings(SEAL_KEY="demo-key")  # type: ignore[arg-type]
    store = FakeVectorStore(settings)
    path = Path(__file__).parents[1] / "tests/fixtures/practice/chunks.jsonl.gz"
    with gzip.open(path, "rt") as f:
        for line in f:
            c = json.loads(line)
            for k in ("char_start", "char_end"):
                if str(c.get(k, "")).isdigit():
                    c[k] = int(c[k])
            store.add_law(c.pop("chunk_id"), c.pop("text"), **c)
    return settings, store, FakeEmbedder()


async def _main(a: argparse.Namespace) -> int:
    if a.sample:
        settings, store, embedder = await _sample_deps()
        collection = settings.CORPUS_COLLECTION
    else:
        from adapters.qdrant import QdrantStore
        from adapters.voyage import VoyageClient
        from core.settings import get_settings

        settings = get_settings()
        collection = a.collection or settings.CORPUS_COLLECTION
        store, embedder = QdrantStore(settings), VoyageClient(settings)

    sl = Slice(collection, _parse_where(a.where), a.id_from, a.id_to)
    if a.replay:
        ids = list(json.loads(a.replay.read_text())["modes"].values())[0]["ranks"]
        chunks = await chunks_by_id(store, collection, list(ids))
    else:
        chunks = await sample_chunks(store, sl, a.n)

    build = STRATEGIES[a.strategy]()
    modes = tuple(m for m in MODES if m in a.modes)
    results = await run_known_item(
        chunks, build, store_retriever(store, embedder, collection, sl.must()), modes
    )
    try:
        embed_model = settings.embed_model_for(collection)
    except UnknownEmbeddingModel:
        embed_model = "not recorded"
    meta = {
        "collection": collection,
        "embed_model": embed_model,
        "where": sl.where,
        "id_from": sl.id_from,
        "id_to": sl.id_to,
        "strategy": a.strategy,
        "n_requested": a.n,
        "n_measured": len(chunks),
        "snapshot": settings.SNAPSHOT_VERSION,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "offline_demo": bool(a.sample),
        "note": "known-item retrieval: finds a known chunk from its own text. "
        "Does not measure answer correctness (evals/known_item.py).",
    }
    print(
        f"known-item retrieval | {collection} | strategy={a.strategy} | "
        f"{len(chunks)} chunks"
    )
    print(render_table(results))
    if a.sample:
        print("(offline demo: the fake ranks all three modes alike)")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(to_json(results, meta), indent=2) + "\n")
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sample", action="store_true", help="offline demo with fakes")
    ap.add_argument("--collection", help="default: CORPUS_COLLECTION from config")
    ap.add_argument("--n", type=int, default=200, help="chunks to sample")
    ap.add_argument("--strategy", choices=sorted(STRATEGIES), default="middle_sentence")
    ap.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    ap.add_argument(
        "--where", action="append", default=[], metavar="KEY=VALUE",
        help="exact payload match for the slice, repeatable (for example court=...)",
    )  # fmt: skip
    ap.add_argument("--id-from", help="inclusive lower bound on the record id")
    ap.add_argument("--id-to", help="inclusive upper bound on the record id")
    ap.add_argument(
        "--replay", type=Path, help="re-measure the chunks of an earlier run"
    )
    ap.add_argument("--out", type=Path, help="write the JSON result here")
    raise SystemExit(asyncio.run(_main(ap.parse_args())))
