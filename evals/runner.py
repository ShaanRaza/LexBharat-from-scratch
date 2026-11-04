"""Eval runner for the 200-question set (docs/TESTING.md). Pipeline steps 7 and 9.

Plain words: give it a file of questions (one JSON object per line, fields as in
evals/README.md plus `kind`: real | lookup | trap) and a function that answers a
question. It scores the launch-gate numbers:

  verified_citation_rate   citations that survived verification / citations written
                           (target >= 98%)
  removed_answer_rate      answers with at least one removed citation (target < 0.5%)
  fabricated_reached_user  citations shown whose record is not in the corpus, or that
                           the question marked must_not_cite (target: zero)
  trap_failures            trap questions that got an answer instead of a refusal
                           (do NOT drop traps to raise the score)

Real runs plug in the full pipeline (admin page, costs money). `--sample` runs a
tiny offline demo with fakes over the practice fixtures. Not the 200-question set.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from core.contracts import PipelineResult
from core.coverage import data_as_of_text

HERE = Path(__file__).parent
Pipeline = Callable[[dict], Awaitable[PipelineResult]]


@dataclass
class Report:
    questions: int
    answered: int
    citations_shown: int
    citations_removed: int
    answers_with_removal: int
    fabricated_reached_user: int
    trap_failures: int
    traps: int

    @property
    def verified_citation_rate(self) -> float:
        written = self.citations_shown + self.citations_removed
        return 1.0 if written == 0 else self.citations_shown / written

    @property
    def removed_answer_rate(self) -> float:
        return 0.0 if self.answered == 0 else self.answers_with_removal / self.answered

    def passes_launch_gate(self) -> bool:
        return (
            self.verified_citation_rate >= 0.98
            and self.removed_answer_rate < 0.005
            and self.fabricated_reached_user == 0
            and self.trap_failures == 0
        )


def load_questions(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


async def run_set(
    questions: Iterable[dict],
    pipeline: Pipeline,
    corpus_ids: set[str] | None = None,
) -> Report:
    r = Report(0, 0, 0, 0, 0, 0, 0, 0)
    for q in questions:
        result = await pipeline(q)
        r.questions += 1
        is_trap = q.get("kind") == "trap"
        r.traps += is_trap
        if result.outcome != "answered" or result.answer is None:
            continue
        r.answered += 1
        if is_trap:
            r.trap_failures += 1
        cits = result.answer.citations
        r.citations_shown += len(cits)
        r.citations_removed += len(result.answer.removed)
        r.answers_with_removal += bool(result.answer.removed)
        banned = set(q.get("must_not_cite", []))
        for c in cits:
            if c.record_id in banned or (
                corpus_ids is not None and c.record_id not in corpus_ids
            ):
                r.fabricated_reached_user += 1
    return r


# --- Offline demo: fakes over the practice fixtures -----------------------------------
async def _sample_pipeline_factory():
    import gzip
    from types import SimpleNamespace

    from adapters.decisions import FakeDecisions
    from adapters.memory import FakeCitationLog
    from adapters.qdrant import FakeVectorStore
    from adapters.voyage import words
    from core.contracts import (
        DraftAnswer,
        Footer,
        Passage,
        PipelineResult,
        RewrittenQuery,
    )
    from core.gate import gate
    from core.settings import Settings
    from core.verify import verify

    settings = Settings()
    store = FakeVectorStore(settings)
    chunks_path = HERE.parent / "tests/fixtures/practice/chunks.jsonl.gz"
    pool: list[Passage] = []
    with gzip.open(chunks_path, "rt") as fh:
        for line in fh:
            c = json.loads(line)
            body = c["text"][-(int(c["char_end"]) - int(c["char_start"])) :]
            store.add_law(c["chunk_id"], body)
            pool.append(
                Passage(
                    record_id=c["chunk_id"],
                    text=body,
                    citation_string=c.get("citation") or None,
                    title=c.get("title"),
                )
            )
    deps = SimpleNamespace(
        settings=settings,
        vectors=store,
        decisions=FakeDecisions(),
        citation_log=FakeCitationLog(),
    )
    footer = Footer(data_as_of_text(), settings.SNAPSHOT_VERSION)

    async def pipeline(q: dict) -> PipelineResult:
        qwords = set(words(q["question"]))
        ranked = sorted(pool, key=lambda p: -len(qwords & set(words(p.text))))[:10]
        scored = [
            Passage(
                **{
                    **p.__dict__,
                    "score": len(qwords & set(words(p.text))) / (len(qwords) or 1),
                }
            )
            for p in ranked
        ]
        g = await gate(RewrittenQuery(q["question"]), scored, deps)
        if not g.passages:
            return PipelineResult("not_found", None, footer)
        top = g.passages[0]
        sentence = top.text.strip().split(".")[0].strip()
        draft = DraftAnswer(
            f'The record states "{sentence[:80]}" [S1].', "demo", 0, 0, q["question"]
        )
        answer = await verify(draft, g.passages, deps)
        return PipelineResult("answered", answer, footer, model="demo")

    return pipeline, {p.record_id for p in pool}


async def _main(sample: bool, path: Path | None) -> int:
    if not sample:
        raise SystemExit("Real runs need the full pipeline wired in (admin page).")
    pipeline, corpus_ids = await _sample_pipeline_factory()
    qs = load_questions(path or HERE / "sample_questions.jsonl")
    rep = await run_set(qs, pipeline, corpus_ids)
    print(
        json.dumps(
            {
                **rep.__dict__,
                "verified_citation_rate": rep.verified_citation_rate,
                "removed_answer_rate": rep.removed_answer_rate,
                "passes_launch_gate": rep.passes_launch_gate(),
            },
            indent=2,
        )
    )
    return 0 if rep.passes_launch_gate() else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="offline demo with fakes")
    ap.add_argument("--questions", type=Path)
    a = ap.parse_args()
    raise SystemExit(asyncio.run(_main(a.sample, a.questions)))
