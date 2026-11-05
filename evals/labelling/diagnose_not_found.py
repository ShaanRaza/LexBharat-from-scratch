"""Why did these questions come back not_found? One question at a time, every step's passages recorded.

Measurement only: the pipeline runs exactly as `run_real.py` runs it (real Gemini, Voyage and the Qdrant copy instance);
nothing is changed, and the gate threshold (0.6) and the 50 / 10 / 8 counts are read, not touched. For each question it
records what step 5 returned (how many, which filter layer, the filters), what step 6 kept (each passage's rerank
score), what step 7 rated (each passage's rating and score, and whether it cleared the threshold), and, if the gate
kept any, what step 9 removed and why. So "where did the emptying happen" is a recorded fact per question.

  python -m evals.labelling.diagnose_not_found --ids q031 q032 ... --repeat 2
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
from pathlib import Path

from adapters.cache import FakeCache
from adapters.memory import FakeCitationLog, FakeStore, FakeUsageMeter
from core import pipeline as _pipeline
from core.contracts import PipelineRequest
from core.pipeline import run_pipeline
from core.rerank import rerank as real_rerank
from core.search import search as real_search
from evals.labelling import run_real as rr
from evals.real_run import eval_seal_key

OUT = Path.home() / "qdrant-kanoon" / "labelling" / "not_found_diagnosis.json"
REC: dict = {}


def _p(p) -> dict:
    return {
        "record_id": p.record_id,
        "kind": p.kind,
        "title": (p.title or "")[:90],
        "text_start": (p.text or "")[:110].replace("\n", " "),
        "score": round(float(p.score), 4),
    }


async def recording_search(request, rq, decision, vector, deps):
    r = await real_search(request, rq, decision, vector, deps)
    REC["search"] = {
        "scope": r.scope,
        "passages": len(r.passages),
        "filters": dataclasses.asdict(decision.filters),
        "keyword_only": r.keyword_only,
        "rewritten_query": rq.query,
        "top": [_p(p) for p in r.passages[:10]],
    }
    return r


async def recording_rerank(rq, passages, deps):
    top = await real_rerank(rq, passages, deps)
    REC["rerank"] = {"in": len(passages), "out": len(top), "kept": [_p(p) for p in top]}
    return top


class RecordingDecisions:
    """Notes each passage's gate rating and score as the gate asks for them."""

    def __init__(self, inner):
        self.inner = inner

    async def rate_passage(self, query, passage):
        rating, score = await self.inner.rate_passage(query, passage)
        REC.setdefault("rated", {})[passage.record_id] = {
            "rating": rating,
            "score": round(float(score), 4),
        }
        return rating, score

    def __getattr__(self, name):
        return getattr(self.inner, name)


async def one(row: dict, deps) -> dict:
    REC.clear()
    deps_q = dataclasses.replace(
        deps,
        cache=FakeCache(),
        usage=FakeUsageMeter(),
        store=FakeStore(),
        citation_log=FakeCitationLog(),
        decisions=RecordingDecisions(deps.decisions),
    )
    request = PipelineRequest(user_id="not-found-diagnosis", message=row["question"])
    result = await run_pipeline(request, deps_q)
    threshold = deps.settings.JEV_GATE_THRESHOLD
    rated = REC.get("rated", {})
    for p in REC.get("rerank", {}).get("kept", []):
        g = rated.get(p["record_id"], {})
        p["gate_rating"], p["gate_score"] = g.get("rating"), g.get("score")
        p["cleared"] = (
            g.get("rating") not in (None, "not_relevant")
            and (g.get("score") or 0) >= threshold
        )
    cleared = [p for p in REC.get("rerank", {}).get("kept", []) if p.get("cleared")]
    if result.outcome == "answered":
        where = "answered (not a not_found this time)"
    elif not REC.get("search", {}).get("passages"):
        where = "step 5: nothing retrieved"
    elif not cleared:
        where = "step 7 (gate): no passage cleared the threshold"
    else:
        where = "step 9 (verify): the gate kept passages, no citation survived"
    return {
        "id": row["id"],
        "question": row["question"],
        "outcome": result.outcome,
        "emptied_at": where,
        "threshold": threshold,
        "search": REC.get("search"),
        "rerank": REC.get("rerank"),
        "gate_kept": len(cleared),
        "removed": [
            {"source_id": x.source_id, "reason": x.reason, "sentence": x.sentence[:140]}
            for x in (result.removed or ())
        ],
    }


async def main_async(ids: list[str], repeat: int) -> None:
    _pipeline.search = recording_search
    _pipeline.rerank = recording_rerank
    rows = {r["id"]: r for r in rr.stub_rows()}
    llm = rr.CountingLLM(None)
    deps = rr.build(llm)
    out = []
    with eval_seal_key():
        for i in ids:
            for n in range(repeat):
                d = await one(rows[i], deps)
                d["run"] = n + 1
                out.append(d)
                print(
                    f"{i} run {n + 1}: {d['outcome']:>10}  "
                    f"retrieved {d['search']['passages'] if d['search'] else 0:>2}  "
                    f"reranked {d['rerank']['out'] if d['rerank'] else 0:>2}  "
                    f"cleared {d['gate_kept']}  -> {d['emptied_at']}",
                    flush=True,
                )
    OUT.write_text(json.dumps(out, indent=1))
    print(
        f"\nwrote {OUT}; {llm.calls} model calls, {llm.rate_limit_hits} rate-limit hits"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="+", required=True)
    ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args()
    asyncio.run(main_async(a.ids, a.repeat))


if __name__ == "__main__":
    main()
