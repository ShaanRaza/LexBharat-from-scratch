"""Run the 100 stub questions through the REAL pipeline, to build the labelling pack (A141 follow-up).

Pipeline steps 2-11 all run, with the real vendors: Voyage (query embedding and rerank), Qdrant (the copy instance on
127.0.0.1:7333, collection `kanoon_v1`, the collection the product is configured to serve), and Gemini for rewrite, scope,
safety, gate, answer and claim check (Jev's switches stay at their shipped default, off, so the Gemini decider decides, as
in production today). Only the parts that are not vendors are in-memory stand-ins: the cache, the usage meter, the
conversation store and the citation log, the same ones `evals/real_run.py` uses.

`evals/real_run.py` is different: it fakes the vendors and does NOT run the answerable stubs. This is the first time they run.

Keys. Gemini uses the EVALUATION key, `EVAL_GEMINI_API_KEY` in `vaquill-local/.env.local`, never the live key (standing rule).
Voyage uses the `VOYAGE_API_KEY` line of the repo `.env`. Neither is ever printed.

Spend and limits (the owner's standing rule on the paid Gemini key, 5 Nov 2026). Every model call is counted. The run
stops loudly at CALL_CAP (2,500) with `CapReached`, and at ANY 429 or spending-cap error, or once spend passes the
estimate by 20%, with `SpendStop`; both are BaseExceptions so nothing in the pipeline can swallow them. A 429 is never
retried and never moved to another key. Every response is cached on disk by model + prompt + schema, so a repeat costs
nothing and a crash resumes for free. A run needs `--budget-inr` and `--decision` (what the result decides), and more
than 10 questions needs a pilot of at most 10 first. The summary reports actual tokens and rupees. Voyage cost is small (a query embedding and a rerank of up to 50
passages per question) and is reported from the answers' own token counts where the API returns them.

Results are written to a JSONL file OUTSIDE the repo (answers quote judgments and name parties). Re-running resumes: ids
already in the file are skipped.

  .venv/bin/python -m evals.labelling.run_real --limit 3        # a first look, 3 questions
  .venv/bin/python -m evals.labelling.run_real                  # all 100 stubs
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import dataclasses
import hashlib
import json
import logging
import time
from pathlib import Path

from pydantic import SecretStr

import core.pipeline as _pipeline
from adapters.cache import FakeCache
from adapters.decisions import (
    DecisionUnavailable,
    FallbackDecisions,
    GeminiDecider,
    JevClient,
)
from adapters.jev import begin_run
from adapters.llm import LiteLLMClient, LLMResult, LLMUnavailable
from adapters.memory import FakeCitationLog, FakeStore, FakeUsageMeter
from adapters.qdrant import QdrantStore
from adapters.voyage import VoyageClient
from core.contracts import Deps, PipelineRequest
from core.gate import gate as real_gate
from core.pipeline import run_pipeline
from core.search import search as real_search
from core.verify import verify as real_verify
from evals.real_run import eval_seal_key, run_settings

REPO = Path(__file__).resolve().parents[2]
EVAL_ENV = (
    Path.home() / "Documents" / "Claude Code Folder" / "vaquill-local" / ".env.local"
)
OUT_DEFAULT = Path.home() / "qdrant-kanoon" / "labelling" / "pipeline_answers.jsonl"
COPY_QDRANT = "http://127.0.0.1:7333"
CALL_CAP = 2500
LLM_CACHE = Path.home() / "qdrant-kanoon" / "labelling" / "llm_cache"
# gemini-3.5-flash-lite list price, USD per million tokens. Secondhand (third-party price pages, 5 Nov 2026): confirm on
# ai.google.dev/gemini-api/docs/pricing. Rupees at the COSTS.md rate of 85 to the dollar.
USD_PER_M_IN, USD_PER_M_OUT, INR_PER_USD = 0.30, 2.50, 85.0
OVERSPEND = 1.2  # abort once spend passes the estimate by 20%
PILOT_MAX = 10


def inr(tokens_in: int, tokens_out: int) -> float:
    """What the tokens cost in rupees at the list price above."""
    usd = tokens_in / 1e6 * USD_PER_M_IN + tokens_out / 1e6 * USD_PER_M_OUT
    return usd * INR_PER_USD


RPM = 14  # the evaluation key is on the Gemini FREE tier: 15 requests a minute for this model (measured 4 Nov 2026)
PAUSE_S = 0.5
MAX_ATTEMPTS = 6


class QuotaExhausted(BaseException):
    """A per-DAY quota is used up: retrying cannot help. The run stops; re-running resumes from the checkpoint."""


class SpendStop(BaseException):
    """A 429 or spending-cap error, or spend past the estimate by 20%. The run ends; nothing is retried, and no other key
    or tier is tried. A BaseException so no `except Exception` in the pipeline can swallow it."""


class CapReached(BaseException):
    """The model-call cap was hit. A BaseException on purpose: no `except Exception` in the pipeline may swallow it."""


def _line(path: Path, name: str) -> str:
    for line in path.read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit(f"{name} is not in {path.name}")  # the value is never printed


def _is_rate_limit(msg: str) -> bool:
    m = msg.lower()
    return any(
        t in m
        for t in (
            "429",
            "rate limit",
            "ratelimit",
            "quota",
            "resource_exhausted",
            "too many requests",
        )
    )


class CountingLLM:
    """Wraps the real client: counts every call, retries rate limits with backoff, stops at the cap."""

    def __init__(
        self,
        inner,
        cap: int = CALL_CAP,
        budget_inr: float | None = None,
        cache_dir: Path | None = None,
    ):
        self.inner, self.cap = inner, cap
        self.budget_inr, self.cache_dir = budget_inr, cache_dir
        self.tokens_in = self.tokens_out = self.cache_hits = 0
        self.calls = 0
        self.rate_limit_hits = 0
        self.other_errors = 0
        self.sleep_s = 0.0
        self.first_rate_limit_message = ""
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def _pace(self) -> None:
        """Start calls no faster than RPM a minute, however many the pipeline fires at once."""
        async with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            self._next = max(now, self._next) + 60.0 / RPM
        if wait:
            self.sleep_s += wait
            await asyncio.sleep(wait)

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str,
        max_tokens: int = 1024,
        json_schema: dict | None = None,
    ):
        cached = self._cache_read(prompt, system, model, max_tokens, json_schema)
        if cached is not None:
            self.cache_hits += 1
            return cached
        last: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            if self.calls >= self.cap:
                raise CapReached(
                    f"{self.calls} model calls: the cap of {self.cap} is reached"
                )
            await self._pace()
            self.calls += 1
            try:
                r = await self.inner.complete(
                    prompt,
                    system=system,
                    model=model,
                    max_tokens=max_tokens,
                    json_schema=json_schema,
                )
            except LLMUnavailable as e:
                last = e
                if _is_rate_limit(str(e)):
                    self.rate_limit_hits += 1
                    self.first_rate_limit_message = (
                        self.first_rate_limit_message or str(e)[-600:]
                    )
                    raise SpendStop(
                        "a 429 or cap error: the run stops, nothing is retried and no other "
                        "key is tried: " + str(e)[-300:]
                    ) from e
                self.other_errors += 1
                wait = 2.0
                self.sleep_s += wait
                await asyncio.sleep(wait)
                continue
            self._cache_write(prompt, system, model, max_tokens, json_schema, r)
            self.tokens_in += r.input_tokens or 0
            self.tokens_out += r.output_tokens or 0
            if self.budget_inr and self.spent_inr > self.budget_inr * OVERSPEND:
                raise SpendStop(
                    f"spend Rs {self.spent_inr:,.2f} passed the estimate of Rs {self.budget_inr:,.2f} by more than "
                    f"{round((OVERSPEND - 1) * 100)}%"
                )
            return r
        raise LLMUnavailable(f"gave up after {MAX_ATTEMPTS} attempts: {last}")

    @property
    def spent_inr(self) -> float:
        return inr(self.tokens_in, self.tokens_out)

    def _cache_path(
        self, prompt, system, model, max_tokens, json_schema
    ) -> Path | None:
        if self.cache_dir is None:
            return None
        key = json.dumps(
            [model, system, prompt, max_tokens, json_schema], sort_keys=True
        )
        return self.cache_dir / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    def _cache_read(self, *key) -> LLMResult | None:
        path = self._cache_path(*key)
        if path is None or not path.exists():
            return None
        try:
            return LLMResult(**json.loads(path.read_text()))
        except (OSError, ValueError, TypeError):
            return None

    def _cache_write(self, prompt, system, model, max_tokens, json_schema, r) -> None:
        path = self._cache_path(prompt, system, model, max_tokens, json_schema)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dataclasses.asdict(r)))


def stub_rows() -> list[dict]:
    rows = [
        json.loads(line)
        for line in (REPO / "evals" / "question_set.jsonl").read_text().splitlines()
        if line.strip()
    ]
    stubs = [r for r in rows if r["status"] == "stub"]
    if len(stubs) != 100 or any(
        r["category"] != "answerable" or r["expect_records"] for r in stubs
    ):
        raise SystemExit(
            "the stub rows are not the 100 unlabelled answerable questions this run expects"
        )
    return stubs


class CountingDecisions:
    """Wraps the real decision service and counts, per call kind, the calls that worked and the calls where no decider
    could decide. When none can, the pipeline uses its designed fallback (a conservative scope and safety default, the
    rerank score at the gate), so each count is a measure of how far a run was from a working decision layer."""

    def __init__(self, inner):
        self.inner = inner
        self.stats: collections.Counter = collections.Counter()

    async def _count(self, kind, call):
        try:
            out = await call
        except DecisionUnavailable:
            self.stats[f"{kind}_unavailable"] += 1
            raise
        self.stats[f"{kind}_ok"] += 1
        return out

    async def decide(self, query, *, uploads=False):
        return await self._count("decide", self.inner.decide(query, uploads=uploads))

    async def rate_passage(self, query, passage):
        return await self._count(
            "rate_passage", self.inner.rate_passage(query, passage)
        )

    async def claim_support(self, sentence, passage):
        return await self._count(
            "claim_support", self.inner.claim_support(sentence, passage)
        )

    def __getattr__(
        self, name
    ):  # anything else (for example aclose) goes to the real service
        return getattr(self.inner, name)


class FallbackLog(logging.Handler):
    """Counts the pipeline's own warnings that a cheap step fell back (rewrite to the raw message)."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.counts: collections.Counter = collections.Counter()

    def emit(self, record):
        msg = record.getMessage()
        if "rewrite fell back" in msg:
            self.counts["rewrite_fell_back"] += 1


DECISIONS: CountingDecisions | None = None
FALLBACKS = FallbackLog()
SEEN: dict[
    str, list
] = {}  # the passages S1-S8 the gate handed the writer, for the question now running


async def recording_search(request, rq, decision, vector, deps):
    """The real search; remembers which filter layer served it and how many passages
    it returned, so the run can report zero-passage questions directly."""
    r = await real_search(request, rq, decision, vector, deps)
    SEEN["scope"], SEEN["searched"] = r.scope, len(r.passages)
    SEEN["filters"] = dataclasses.asdict(decision.filters)
    return r


async def recording_gate(rq, passages, deps):
    g = await real_gate(rq, passages, deps)
    SEEN["passages"] = list(g.passages)
    return g


def build(llm: CountingLLM) -> Deps:
    s = run_settings(
        jev_on=False
    )  # class defaults only; Jev switches at their shipped default (off)
    s = s.model_copy(
        update={
            "GEMINI_API_KEY": SecretStr(_line(EVAL_ENV, "EVAL_GEMINI_API_KEY")),
            "VOYAGE_API_KEY": SecretStr(_line(REPO / ".env", "VOYAGE_API_KEY")),
            "QDRANT_URL": COPY_QDRANT,
            # the copy instance is shared with other jobs; a slow read is not an outage here
            "QDRANT_TIMEOUT_S": 90.0,
        }
    )
    global DECISIONS
    voyage = VoyageClient(s)
    llm.inner = LiteLLMClient(s)
    DECISIONS = CountingDecisions(
        FallbackDecisions(JevClient(s), GeminiDecider(llm, s), s)
    )
    return Deps(
        settings=s,
        embedder=voyage,
        reranker=voyage,
        vectors=QdrantStore(s),
        llm=llm,
        decisions=DECISIONS,
        cache=FakeCache(),
        usage=FakeUsageMeter(),
        store=FakeStore(),
        citation_log=FakeCitationLog(),
        gate=recording_gate,
        verify=real_verify,
        begin_run=begin_run,
    )


def record(row: dict, result, seconds: float, calls: int, degraded: dict) -> dict:
    ans = result.answer
    return {
        "id": row["id"],
        "kind": row["kind"],
        "question": row["question"],
        "outcome": result.outcome,
        "message_key": result.message_key,
        "error": result.error,
        "model": result.model,
        "confidence": result.confidence,
        "answer_text": ans.text if ans else "",
        "citations": [dataclasses.asdict(c) for c in (ans.citations if ans else ())],
        "passages": [
            {
                "source_id": p.source_id,
                "record_id": p.record_id,
                "kind": p.kind,
                "title": p.title,
                "citation_string": p.citation_string,
                "pdf_url": p.pdf_url,
                "source_url": p.source_url,
                "text": p.text,
            }
            for p in SEEN.get("passages", [])
        ],
        "removed": [dataclasses.asdict(r) for r in result.removed],
        "unmarked_removed": ans.unmarked_removed if ans else 0,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "seconds": round(seconds, 2),
        "llm_calls": calls,
        "degraded": degraded,
        "search_scope": SEEN.get("scope"),
        "search_passages": SEEN.get("searched"),
        "filters": SEEN.get("filters"),
    }


async def main_async(
    limit: int | None, out: Path, budget_inr: float, decision: str
) -> None:
    _pipeline.search = recording_search  # the pipeline imports search by name
    out.parent.mkdir(parents=True, exist_ok=True)
    done = (
        {json.loads(line)["id"] for line in out.read_text().splitlines()}
        if out.exists()
        else set()
    )
    rows = [r for r in stub_rows() if r["id"] not in done]
    if limit:
        rows = rows[:limit]
    n = len(rows)
    if n > PILOT_MAX and not done:
        raise SystemExit(
            f"{n} questions and no pilot yet: run --limit {PILOT_MAX} first, check the output, then the rest"
        )
    print(
        f"RUN: {n} questions; estimate Rs {budget_inr:,.2f} (hard stop at Rs {budget_inr * OVERSPEND:,.2f}); "
        f"decides: {decision}",
        flush=True,
    )
    llm = CountingLLM(None, budget_inr=budget_inr, cache_dir=LLM_CACHE)
    deps = build(llm)
    logging.getLogger("core.rewrite").addHandler(FALLBACKS)
    t_all = time.time()
    stopped = ""
    try:
        with eval_seal_key(), out.open("a") as f:
            for i, row in enumerate(rows, 1):
                before, t0 = llm.calls, time.time()
                SEEN.clear()
                d0, f0 = (
                    collections.Counter(DECISIONS.stats),
                    collections.Counter(FALLBACKS.counts),
                )
                request = PipelineRequest(
                    user_id="labelling-pack", message=row["question"]
                )
                deps_q = dataclasses.replace(
                    deps,
                    cache=FakeCache(),
                    usage=FakeUsageMeter(),
                    store=FakeStore(),
                    citation_log=FakeCitationLog(),
                )
                result = await run_pipeline(request, deps_q)
                degraded = {
                    k: v
                    for k, v in (
                        (DECISIONS.stats - d0) + (FALLBACKS.counts - f0)
                    ).items()
                }
                rec = record(
                    row, result, time.time() - t0, llm.calls - before, degraded
                )
                f.write(json.dumps(rec) + "\n")
                f.flush()
                print(
                    f"{i}/{len(rows)} {row['id']:>5} {rec['outcome']:>10} {rec['message_key'] or '':<28} "
                    f"{len(rec['citations'])} cit  {rec['llm_calls']} calls  {rec['seconds']:.0f}s",
                    flush=True,
                )
                await asyncio.sleep(PAUSE_S)
    except SpendStop as e:
        stopped = str(e)
    print(
        f"\nSUMMARY: {len(rows)} questions, {llm.calls} model calls (cap {CALL_CAP}), {llm.cache_hits} served from the "
        f"disk cache, {llm.other_errors} other model errors, {llm.sleep_s:.0f}s spent waiting, "
        f"{time.time() - t_all:.0f}s wall"
    )
    print(
        f"SPEND: {llm.tokens_in:,} tokens in, {llm.tokens_out:,} out = Rs {llm.spent_inr:,.2f} "
        f"(estimate Rs {budget_inr:,.2f}); list price, see USD_PER_M_IN / USD_PER_M_OUT"
    )
    print(
        "decision layer, all questions:", dict(DECISIONS.stats), dict(FALLBACKS.counts)
    )
    if stopped:
        print("RUN STOPPED:", stopped, flush=True)
        raise SystemExit(2)


def main() -> None:
    global RPM  # noqa: PLW0603 - read by CountingLLM._pace at call time
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument(
        "--rpm",
        type=int,
        default=RPM,
        help="model calls a minute (the free tier allowed 14; billing is on now)",
    )
    ap.add_argument(
        "--budget-inr", type=float, required=True, help="the estimate in rupees"
    )
    ap.add_argument(
        "--decision", required=True, help="what decision this result drives"
    )
    a = ap.parse_args()
    RPM = a.rpm
    asyncio.run(main_async(a.limit, a.out, a.budget_inr, a.decision))


if __name__ == "__main__":
    main()
