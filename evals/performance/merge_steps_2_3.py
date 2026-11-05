"""Would merging step 2 (Rewrite) and step 3 (Decide) save time? A measurement only: nothing is merged.

Step 2 is one Gemini call on the user's message; step 3 runs one Gemini call on the rewritten query, in parallel with the
Voyage embedding of that query. Merging the two calls would remove one Gemini round trip, but the embedding needs the
REWRITTEN query, so it could no longer overlap with the decision: it would wait for the merged call. This script times
both paths, on the same questions, interleaved so that drift in Gemini's latency hits both equally:

  A  as built:   rewrite call, then (decide call || embed the rewritten query)           critical path = rewrite + max(decide, embed)
  B  merged:     ONE call that rewrites and decides, then embed the rewritten query      critical path = merged + embed
  B' bound:      merged call || embed the RAW message (changes what is retrieved on;     critical path = max(merged, embed)
                 computed from the same timings, not a separate call)

It also checks that the merged call decides the same thing: scope, safety and filters are compared field by field with
the separate calls, with the merged output run through the real `core.decide.decide` so the Act-year guard applies.

  python -m evals.performance.merge_steps_2_3 --questions 20 --repeats 2
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import random
import time
from pathlib import Path

from core import coverage, llm_schemas
from core.contracts import Decision, Filters, PipelineRequest, RewrittenQuery
from core.decide import decide
from core.memory import remember
from core.rewrite import _PROMPT as REWRITE_PROMPT
from core.rewrite import rewrite
from core.search import embed_query
from evals.labelling import run_real as R
from evals.performance.timing import p50_p95
from evals.real_run import eval_seal_key

OUT = Path.home() / "qdrant-kanoon" / "performance" / "merge_2_3.json"

MERGED_SCHEMA = {
    "type": "object",
    "properties": {
        **llm_schemas.REWRITE["properties"],
        **llm_schemas.DECIDE["properties"],
    },
    "required": ["query", "scope", "safety"],
}

# The two shipped prompts, joined: the rewrite instructions on the message, then the decide instructions on the query the
# first part produced. Nothing is added to either, so a difference in the result is the merge, not new wording.
_DECIDE_TEXT = (
    Path(R.__file__).parents[2] / "core" / "prompts" / "decide.txt"
).read_text()


def merged_prompt(message: str, summary: str, turns: str) -> str:
    rewrite_part = REWRITE_PROMPT.read_text().format(
        summary=summary, turns=turns, message=message
    )
    decide_part = _DECIDE_TEXT.format(
        query="<the standalone query you wrote in job 1>",
        scope_help=coverage.scope_help(),
        scope_choices=coverage.scope_choices(),
    )
    return (
        "Do two jobs on the latest message and reply with ONE JSON object holding both results.\n\n"
        "JOB 1 - REWRITE. Fields: query, act, section, case_number, year.\n"
        + rewrite_part
        + "\n\nJOB 2 - DECIDE, on the standalone query from job 1. Fields: scope, safety, court, year_from, "
        "year_to, act, act_year, section.\n"
        + decide_part
        + "\nThe final reply is one JSON object with ALL of the fields of both jobs."
    )


class Recorder:
    """Wraps the real LLM client: records every call's own duration and tokens, in order."""

    def __init__(self, inner):
        self.inner, self.calls = inner, []

    async def complete(self, prompt, **kw):
        t0 = time.perf_counter()
        r = await self.inner.complete(prompt, **kw)
        self.calls.append(
            {
                "seconds": time.perf_counter() - t0,
                "in": r.input_tokens,
                "out": r.output_tokens,
            }
        )
        return r


class StubDecisions:
    """Hands the real core.decide.decide the merged call's decision, so the Act-year guard and the merge with the rewrite
    fields run exactly as they do in the pipeline."""

    def __init__(self, d: Decision):
        self.d = d

    async def decide(self, query, *, uploads=False):
        return self.d


def _filters_key(f: Filters) -> tuple:
    return (
        f.court,
        f.year_from,
        f.year_to,
        f.act,
        f.section,
        f.case_number,
        f.act_year,
    )


async def arm_a(request, memory, deps):
    t0 = time.perf_counter()
    rq = await rewrite(request, memory, deps)
    t1 = time.perf_counter()

    async def timed(coro):
        s = time.perf_counter()
        out = await coro
        return out, time.perf_counter() - s

    (decision, t_dec), (vec, t_emb) = await asyncio.gather(
        timed(decide(rq, deps)), timed(embed_query(rq.query, deps))
    )
    return {
        "rq": rq,
        "decision": decision,
        "rewrite": t1 - t0,
        "decide": t_dec,
        "embed": t_emb,
        "path": time.perf_counter() - t0,
    }


async def arm_b(request, memory, deps):
    turns = "\n".join(f"{t.role}: {t.text}" for t in memory.turns)
    t0 = time.perf_counter()
    r = await deps.llm.complete(
        merged_prompt(request.message, memory.summary, turns),
        model=deps.settings.MODEL_REWRITE,
        max_tokens=500,
        json_schema=MERGED_SCHEMA,
    )
    t_call = time.perf_counter() - t0
    d = json.loads(r.text)
    year = d.get("year")
    rq = RewrittenQuery(
        query=str(d["query"]).strip(),
        act=d.get("act") or None,
        section=d.get("section") or None,
        case_number=d.get("case_number") or None,
        year=year if isinstance(year, int) else None,
    )
    act_year = d.get("act_year")
    dec = Decision(
        d["scope"],
        Filters(
            court=d.get("court"),
            year_from=d.get("year_from"),
            year_to=d.get("year_to"),
            act=d.get("act"),
            section=d.get("section"),
            act_year=act_year if isinstance(act_year, int) else None,
        ),
        d["safety"],
        (),
        False,
    )
    decision = await decide(rq, dataclasses.replace(deps, decisions=StubDecisions(dec)))
    s = time.perf_counter()
    await embed_query(rq.query, deps)
    t_emb = time.perf_counter() - s
    return {
        "rq": rq,
        "decision": decision,
        "merged_call": t_call,
        "embed": t_emb,
        "path": time.perf_counter() - t0,
    }


async def embed_raw(message, deps):
    s = time.perf_counter()
    await embed_query(message, deps)
    return time.perf_counter() - s


def _agree(a: dict, b: dict) -> dict:
    da, db = a["decision"], b["decision"]
    qa, qb = a["rq"].query.lower().strip(), b["rq"].query.lower().strip()
    wa, wb = set(qa.split()), set(qb.split())
    return {
        "scope": da.scope == db.scope,
        "safety": da.safety == db.safety,
        "filters": _filters_key(da.filters) == _filters_key(db.filters),
        "query_identical": qa == qb,
        "query_word_overlap": round(len(wa & wb) / max(1, len(wa | wb)), 3),
    }


async def main_async(n_questions: int, repeats: int, seed: int) -> None:
    R.RPM = 6000  # no pacing wait inside a timed call
    rows = R.stub_rows()
    sample = random.Random(seed).sample(rows, n_questions)  # noqa: S311 - a fixed sample, not security
    llm = R.CountingLLM(None)
    deps = R.build(llm)
    rec = Recorder(llm.inner)
    llm.inner = rec
    out = []
    with eval_seal_key():
        for row in sample:
            request = PipelineRequest(user_id="merge-2-3", message=row["question"])
            memory = remember(request)
            for rep in range(repeats):
                order = (
                    ("A", "B") if rep % 2 == 0 else ("B", "A")
                )  # alternate who goes first
                res = {}
                for arm in order:
                    mark = len(rec.calls)
                    res[arm] = await (arm_a if arm == "A" else arm_b)(
                        request, memory, deps
                    )
                    res[arm]["calls"] = rec.calls[mark:]
                raw_embed = await embed_raw(request.message, deps)
                a, b = res["A"], res["B"]
                out.append(
                    {
                        "id": row["id"],
                        "rep": rep,
                        "question": row["question"],
                        "A_rewrite": a["rewrite"],
                        "A_decide": a["decide"],
                        "A_embed": a["embed"],
                        "A_path": a["path"],
                        "B_merged_call": b["merged_call"],
                        "B_embed": b["embed"],
                        "B_path": b["path"],
                        "Bprime_path": max(b["merged_call"], raw_embed),
                        "A_tokens_in": sum(c["in"] for c in a["calls"]),
                        "A_tokens_out": sum(c["out"] for c in a["calls"]),
                        "B_tokens_in": sum(c["in"] for c in b["calls"]),
                        "B_tokens_out": sum(c["out"] for c in b["calls"]),
                        "agree": _agree(a, b),
                        "A_query": a["rq"].query,
                        "B_query": b["rq"].query,
                        "A_decision": [
                            a["decision"].scope,
                            a["decision"].safety,
                            list(_filters_key(a["decision"].filters)),
                        ],
                        "B_decision": [
                            b["decision"].scope,
                            b["decision"].safety,
                            list(_filters_key(b["decision"].filters)),
                        ],
                    }
                )
                print(
                    f"{row['id']} rep {rep}: A {a['path']:.2f}s  B {b['path']:.2f}s  "
                    f"(saves {a['path'] - b['path']:+.2f}s)  agree {out[-1]['agree']}",
                    flush=True,
                )
    OUT.write_text(json.dumps(out, indent=1))
    report(out, llm)


def _f(x):
    return "-" if x is None else f"{x:.2f} s"


def report(out: list[dict], llm=None) -> None:
    n = len(out)

    def col(k):
        return [r[k] for r in out]

    print(f"\n{n} paired runs ({len({r['id'] for r in out})} questions)")
    for label, key in (
        ("A rewrite call (step 2)", "A_rewrite"),
        ("A decide call (step 3, parallel with embed)", "A_decide"),
        ("A embed (step 3, parallel)", "A_embed"),
        ("A critical path, steps 2+3 as built", "A_path"),
        ("B merged call alone", "B_merged_call"),
        ("B embed after the merged call", "B_embed"),
        ("B critical path, merged then embed", "B_path"),
        ("B' bound, merged || embed of the raw message", "Bprime_path"),
    ):
        p50, p95 = p50_p95(col(key))
        print(f"  {label:<48} p50 {_f(p50)}  p95 {_f(p95)}")
    for label, key in (("B against A", "B_path"), ("B' against A", "Bprime_path")):
        d = [r["A_path"] - r[key] for r in out]
        p50, p95 = p50_p95(d)
        wins = sum(1 for x in d if x > 0)
        print(
            f"  saving, {label:<14} p50 {p50:+.2f} s  p95 {p95:+.2f} s  merged faster in {wins}/{n}"
        )
    ag = {
        k: sum(1 for r in out if r["agree"][k])
        for k in ("scope", "safety", "filters", "query_identical")
    }
    print(f"  agreement with the separate calls (of {n}): {ag}")
    print(
        f"  tokens per question, A {sum(col('A_tokens_in')) / n:.0f} in / {sum(col('A_tokens_out')) / n:.0f} out;"
        f"  B {sum(col('B_tokens_in')) / n:.0f} in / {sum(col('B_tokens_out')) / n:.0f} out"
    )
    if llm is not None:
        print(f"  model calls {llm.calls}, rate-limit hits {llm.rate_limit_hits}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--questions", type=int, default=20)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    if a.report_only:
        report(json.loads(OUT.read_text()))
        return
    asyncio.run(main_async(a.questions, a.repeats, a.seed))


if __name__ == "__main__":
    main()
