"""Latency of the 11 pipeline steps over the 100-question stub set, against CLAUDE.md section 10 (measurement only).

Pipeline steps 1-11 all run for real (real Gemini, Voyage and the Qdrant copy instance), exactly as
`evals/labelling/run_real.py` runs them; nothing is optimised and nothing is changed. The differences are only
measurement: every step and every vendor call is timed on one monotonic clock, call pacing is effectively off (the
labelling run's pacing waits would be counted inside every Gemini-bound step), and a sampler watches the shared Qdrant
instance. A question whose window overlaps another client on the port, or a busy server, is flagged CONTENDED and is
re-run, never reported.

Stand-ins, stated so they are not over-read: step 4 (cache) uses an in-memory cache and step 11 (save) an in-memory
store, so neither includes a Redis or Postgres hop. Step 10 (show) runs after step 11, as the API bridge runs it.
Jev is off (its shipped default), so every decision is Gemini's.

  python -m evals.performance.measure --out ~/qdrant-kanoon/performance/timing.jsonl
  python -m evals.performance.report  --in  ~/qdrant-kanoon/performance/timing.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
import time
from pathlib import Path

from evals.performance import timing as T

HOME = Path.home() / "qdrant-kanoon" / "performance"
EXACT_KEYS = ("section_number", "case_number")


def _purpose(json_schema, schemas) -> str:
    for name, sch in schemas.items():
        if json_schema is sch:
            return name
    return "text"  # the answer writer and claim_support: free text, not JSON


class TimedInner:
    """Times each real Gemini call (not the runner's pacing wait) and sums the tokens."""

    def __init__(self, inner, schemas):
        self.inner, self.schemas = inner, schemas
        self.tokens_in = self.tokens_out = self.calls = 0

    async def complete(
        self, prompt, *, system="", model, max_tokens=1024, json_schema=None
    ):
        kind = f"gemini:{_purpose(json_schema, self.schemas)}"
        t0 = time.perf_counter()
        try:
            r = await self.inner.complete(
                prompt,
                system=system,
                model=model,
                max_tokens=max_tokens,
                json_schema=json_schema,
            )
        finally:
            T.REC.vendor.append(T.Interval(kind, t0, time.perf_counter()))
        self.calls += 1
        self.tokens_in += r.input_tokens
        self.tokens_out += r.output_tokens
        return r


class TimedDecisions:
    """Each decision (scope check, one passage rating, one claim check) timed as its own call."""

    def __init__(self, inner):
        self.inner = inner

    async def _t(self, kind, awaitable):
        t0 = time.perf_counter()
        try:
            return await awaitable
        finally:
            T.REC.vendor.append(T.Interval(f"decision:{kind}", t0, time.perf_counter()))

    async def decide(self, query, *, uploads=False):
        return await self._t("decide", self.inner.decide(query, uploads=uploads))

    async def rate_passage(self, query, passage):
        return await self._t("rate_passage", self.inner.rate_passage(query, passage))

    async def claim_support(self, sentence, passage):
        return await self._t(
            "claim_support", self.inner.claim_support(sentence, passage)
        )

    def __getattr__(self, name):
        return getattr(self.inner, name)


class TimedVectors:
    """Each Qdrant call timed: an exact lookup (a named section or case number) apart from the hybrid search."""

    def __init__(self, inner):
        self.inner = inner

    async def search(self, collection, vector, text, must, limit, mode="hybrid"):
        exact = any(k in must for k in EXACT_KEYS)
        t0 = time.perf_counter()
        try:
            return await self.inner.search(collection, vector, text, must, limit, mode)
        finally:
            T.REC.vendor.append(
                T.Interval(
                    "qdrant:exact" if exact else "qdrant:hybrid",
                    t0,
                    time.perf_counter(),
                )
            )

    async def get_record(self, collection, record_id, user_id=None):
        t0 = time.perf_counter()
        try:
            return await self.inner.get_record(collection, record_id, user_id=user_id)
        finally:
            T.REC.vendor.append(
                T.Interval("qdrant:get_record", t0, time.perf_counter())
            )

    def __getattr__(self, name):
        return getattr(self.inner, name)


class TimedVoyage:
    """The query embedding and the re-rank, each timed (one client serves both)."""

    def __init__(self, inner):
        self.inner = inner

    async def embed(self, text, collection, input_type, **kw):
        t0 = time.perf_counter()
        try:
            return await self.inner.embed(text, collection, input_type, **kw)
        finally:
            T.REC.vendor.append(T.Interval("voyage:embed", t0, time.perf_counter()))

    async def embed_batch(self, texts, collection, input_type, **kw):
        t0 = time.perf_counter()
        try:
            return await self.inner.embed_batch(texts, collection, input_type, **kw)
        finally:
            T.REC.vendor.append(T.Interval("voyage:embed", t0, time.perf_counter()))

    async def rerank(self, query, docs, top_k):
        t0 = time.perf_counter()
        try:
            return await self.inner.rerank(query, docs, top_k)
        finally:
            T.REC.vendor.append(T.Interval("voyage:rerank", t0, time.perf_counter()))

    def __getattr__(self, name):
        return getattr(self.inner, name)


def row_from(
    rec: T.Recorder,
    qid: str,
    result,
    wall: float,
    show_first: float,
    show_total: float,
    scope,
    samples,
) -> dict:
    steps: dict[str, float] = {}
    for s in rec.steps:
        steps[s.name] = steps.get(s.name, 0.0) + s.seconds
    vendor_in_step: dict[str, dict[str, float]] = {}
    for s in rec.steps:
        for prefix in ("gemini", "decision", "voyage", "qdrant"):
            share = T.vendor_share(s, rec.vendor, prefix + ":")
            if share:
                vendor_in_step.setdefault(s.name, {})[prefix] = round(
                    vendor_in_step.get(s.name, {}).get(prefix, 0.0) + share, 4
                )
    calls: dict[str, list[float]] = {}
    for v in rec.vendor:
        calls.setdefault(v.name, []).append(round(v.seconds, 4))
    d3 = [s for s in rec.steps if s.name in ("decide", "embed_query")]
    if d3:
        steps["decide_embed"] = max(s.t1 for s in d3) - min(s.t0 for s in d3)
    t0 = min([s.t0 for s in rec.steps] or [0.0])
    t1 = max([s.t1 for s in rec.steps] or [0.0])
    bad = T.contended_between(samples, t0, t1 + show_total)
    return {
        "id": qid,
        "outcome": result.outcome,
        "message_key": result.message_key,
        "scope": scope,
        "pipeline_seconds": round(wall, 4),
        "first_word_seconds": round(wall + show_first, 4),
        "full_answer_seconds": round(wall + show_total, 4),
        "show_first_word_seconds": round(show_first, 6),
        "show_total_seconds": round(show_total, 6),
        "steps": {k: round(v, 4) for k, v in steps.items()},
        "vendor_in_step": vendor_in_step,
        "calls": calls,
        "contended": bool(bad),
        "contention": [
            {
                "qdrant_cpu": b.qdrant_cpu,
                "load1": b.load1,
                "foreign_clients": list(b.foreign_clients),
            }
            for b in bad[:3]
        ],
    }


async def main_async(
    out: Path, rpm: int, limit: int | None, wait_quiet_min: float, reruns: int
) -> int:
    import core.pipeline as P
    from adapters.cache import FakeCache
    from adapters.memory import FakeCitationLog, FakeStore, FakeUsageMeter
    from core import llm_schemas
    from core.contracts import PipelineRequest
    from core.pipeline import run_pipeline
    from core.show import show
    from evals.labelling import run_real as R
    from evals.real_run import eval_seal_key

    R.RPM = rpm  # effectively no pacing: a pacing wait would be counted inside every Gemini-bound step
    out.parent.mkdir(parents=True, exist_ok=True)
    sampler = T.LoadSampler(every=2.0)
    sampler.start()
    try:
        # ---- the instance must be quiet before anything is timed --------------------------------------------
        deadline = time.time() + wait_quiet_min * 60
        while True:
            await asyncio.sleep(12)
            recent = sampler.samples[-6:]
            if T.is_quiet(recent):
                break
            seen = sorted({p for s in recent for p in s.foreign_clients})
            print(
                f"NOT QUIET: foreign clients on 7333 {seen}, qdrant cpu {[s.qdrant_cpu for s in recent][-3:]}",
                flush=True,
            )
            if time.time() > deadline:
                print("The instance never went quiet: nothing was timed.")
                return 2
            await asyncio.sleep(15)
        baseline = [dataclasses.asdict(s) for s in sampler.samples[-6:]]
        print(
            f"QUIET at start: qdrant cpu {[s['qdrant_cpu'] for s in baseline]}, load1 {baseline[-1]['load1']:.1f}",
            flush=True,
        )

        done = (
            {json.loads(line)["id"] for line in out.read_text().splitlines()}
            if out.exists()
            else set()
        )
        rows = [r for r in R.stub_rows() if r["id"] not in done]
        if limit:
            rows = rows[:limit]
        llm = R.CountingLLM(None)
        deps = R.build(llm)
        schemas = {
            "rewrite": llm_schemas.REWRITE,
            "decide": llm_schemas.DECIDE,
            "rate_passage": llm_schemas.RATE_PASSAGE,
            "followups": llm_schemas.FOLLOWUPS,
        }
        timed_llm = TimedInner(llm.inner, schemas)
        llm.inner = timed_llm
        voyage = TimedVoyage(deps.embedder)
        deps = dataclasses.replace(
            deps,
            embedder=voyage,
            reranker=voyage,
            vectors=TimedVectors(deps.vectors),
            decisions=TimedDecisions(deps.decisions),
            gate=T.timed_step("gate", R.recording_gate),
            verify=T.timed_step("verify", R.real_verify),
        )
        scope_box: dict = {}

        async def search_timed(request, rq, decision, vector, d):
            r = await R.real_search(request, rq, decision, vector, d)
            scope_box["scope"] = r.scope
            return r

        # the steps, by their number and name; the pipeline imports each by name, so they are replaced there
        P.remember = T.timed_step("remember", P.remember)
        P.rewrite = T.timed_step("rewrite", P.rewrite)
        P.decide = T.timed_step("decide", P.decide)
        P.embed_query = T.timed_step("embed_query", P.embed_query)
        P.cache_lookup = T.timed_step("cache", P.cache_lookup)
        P.search = T.timed_step("search", search_timed)
        P.rerank = T.timed_step("rerank", P.rerank)
        P.answer = T.timed_step("answer", P.answer)
        P.save = T.timed_step("save", P.save)

        todo = rows
        attempt = 0
        with eval_seal_key(), out.open("a") as f:
            while todo and attempt <= reruns:
                if attempt:
                    print(
                        f"RE-RUN {attempt}: {len(todo)} contended question(s)",
                        flush=True,
                    )
                    while not T.is_quiet(sampler.samples[-4:]):
                        print("  waiting for the instance to go quiet", flush=True)
                        await asyncio.sleep(20)
                contended: list[dict] = []
                for i, row in enumerate(todo, 1):
                    T.REC.reset()
                    scope_box.clear()
                    request = PipelineRequest(user_id="timing", message=row["question"])
                    dq = dataclasses.replace(
                        deps,
                        cache=FakeCache(),
                        usage=FakeUsageMeter(),
                        store=FakeStore(),
                        citation_log=FakeCitationLog(),
                    )
                    t0 = time.perf_counter()
                    result = await run_pipeline(request, dq)
                    wall = time.perf_counter() - t0
                    # step 10: as the API bridge streams it, after the pipeline (and step 11) has finished
                    ts = time.perf_counter()
                    first = None
                    async for ev in show(result):
                        if first is None:
                            first = time.perf_counter() - ts
                    total = time.perf_counter() - ts
                    T.REC.steps.append(T.Interval("show", ts, ts + total))
                    rec_row = row_from(
                        T.REC,
                        row["id"],
                        result,
                        wall,
                        first or 0.0,
                        total,
                        scope_box.get("scope"),
                        sampler.samples,
                    )
                    rec_row["rate_limit_hits_so_far"] = llm.rate_limit_hits
                    if rec_row["contended"]:
                        contended.append(row)
                        rec_row["discarded"] = True
                    else:
                        f.write(json.dumps(rec_row) + "\n")
                        f.flush()
                    print(
                        f"{i}/{len(todo)} {row['id']:>5} {rec_row['outcome']:>10} {'CONTENDED ' if rec_row['contended'] else ''}"
                        f"pipeline {wall:5.1f}s  first word {rec_row['first_word_seconds']:5.1f}s",
                        flush=True,
                    )
                    await asyncio.sleep(0.2)
                todo = contended
                attempt += 1
        summary = {
            "baseline_samples_at_start": baseline,
            "load_samples": len(sampler.samples),
            "max_qdrant_cpu": max([s.qdrant_cpu or 0 for s in sampler.samples] or [0]),
            "max_load1": max([s.load1 for s in sampler.samples] or [0]),
            "foreign_clients_seen": sorted(
                {p for s in sampler.samples for p in s.foreign_clients}
            ),
            "gemini_calls": timed_llm.calls,
            "gemini_tokens_in": timed_llm.tokens_in,
            "gemini_tokens_out": timed_llm.tokens_out,
            "counting_llm_calls": llm.calls,
            "rate_limit_hits": llm.rate_limit_hits,
            "other_model_errors": llm.other_errors,
            "backoff_seconds": round(llm.sleep_s, 1),
            "unresolved_contended": [r["id"] for r in todo],
        }
        (out.parent / (out.stem + "_summary.json")).write_text(
            json.dumps(summary, indent=1)
        )
        print(
            "\nSUMMARY",
            json.dumps(
                {k: v for k, v in summary.items() if k != "baseline_samples_at_start"}
            ),
        )
        return 0 if not todo else 3
    finally:
        sampler.stop()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=HOME / "timing.jsonl")
    ap.add_argument(
        "--rpm",
        type=int,
        default=6000,
        help="call pacing; effectively off by default, see the module docstring",
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--wait-quiet-min", type=float, default=5.0)
    ap.add_argument("--reruns", type=int, default=2)
    a = ap.parse_args()
    sys.exit(asyncio.run(main_async(a.out, a.rpm, a.limit, a.wait_quiet_min, a.reruns)))


if __name__ == "__main__":
    main()
