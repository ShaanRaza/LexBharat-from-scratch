"""Eval runner: runs a question set through the real pipeline with FAKE services and
reports the numbers that gate a launch (docs/TESTING.md, docs/METRICS.md).

    python -m evals.runner                       # the small sample set
    python -m evals.runner --questions my.jsonl  # the frozen 200-question set
    python -m evals.runner --gate                # exit 1 if a launch gate is missed

Everything is faked (no keys, no network), so this proves the SCAFFOLD works. It does
NOT measure answer quality, speed or cost - that needs the real services and the real,
advocate-signed-off 200 questions.

Question format (one JSON object per line):
  id, kind (real | lookup | trap), question,
  expect_scope, expect_outcome (answered | out_of_scope | not_found),
  expect_records, must_not_cite, notes,
  fake_model (honest | invent_citation | wrong_quote)  <- fake-only; drop for real runs
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from adapters.cache import FakeCache
from adapters.gemini import FakeLLM
from adapters.jev import DecisionAdapter, FakeDecisionBackend
from adapters.qdrant import FakeVectorStore, Record
from adapters.voyage import FakeVoyage
from core.models import PipelineRequest
from core.pipeline import PipelineDeps, run_pipeline
from core.save import InMemoryMessageRepository
from core.settings import Settings

HERE = Path(__file__).parent

# Launch gates (docs/TESTING.md). Changing these is the owner's call.
GATE_VERIFIED_RATE = 0.98
GATE_REMOVED_ANSWERS_RATE = 0.005


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    kind: str = "real"
    expect_scope: str = "in_scope"
    expect_outcome: str = "answered"
    expect_records: tuple[str, ...] = ()
    must_not_cite: tuple[str, ...] = ()
    fake_model: str = "honest"
    notes: str = ""


@dataclass
class QuestionResult:
    id: str
    kind: str
    outcome: str
    ok: bool
    cited: int = 0  # citations the model wrote
    passed: int = 0  # citations that survived the verifier with support
    removed_reasons: list[str] = field(default_factory=list)
    cited_records: list[str] = field(default_factory=list)
    forbidden_cited: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


@dataclass
class EvalReport:
    results: list[QuestionResult]

    @property
    def total_citations(self) -> int:
        return sum(r.cited for r in self.results)

    @property
    def verified_citation_rate(self) -> float:
        """Citations that passed all checks / citations the model wrote."""
        total = self.total_citations
        return sum(r.passed for r in self.results) / total if total else 1.0

    @property
    def answers_with_removed_citation_rate(self) -> float:
        answered = [r for r in self.results if r.outcome == "answered"]
        if not answered:
            return 0.0
        return sum(1 for r in answered if r.removed_reasons) / len(answered)

    @property
    def forbidden_citations_shown(self) -> int:
        return sum(len(r.forbidden_cited) for r in self.results)

    @property
    def question_pass_rate(self) -> float:
        return (
            sum(r.ok for r in self.results) / len(self.results) if self.results else 0
        )

    def meets_launch_gates(self) -> bool:
        return (
            self.verified_citation_rate >= GATE_VERIFIED_RATE
            and self.answers_with_removed_citation_rate < GATE_REMOVED_ANSWERS_RATE
            and self.forbidden_citations_shown == 0
        )

    def summary(self) -> str:
        by_kind: dict[str, list[QuestionResult]] = {}
        for r in self.results:
            by_kind.setdefault(r.kind, []).append(r)
        gate_v = f"(gate >= {GATE_VERIFIED_RATE:.0%})"
        gate_r = f"(gate < {GATE_REMOVED_ANSWERS_RATE:.1%})"
        removed_rate = f"{self.answers_with_removed_citation_rate:.1%}"
        lines = [
            f"questions run:                    {len(self.results)}",
            f"questions behaving as expected:   {self.question_pass_rate:.1%}",
            f"verified-citation rate:           {self.verified_citation_rate:.1%}  {gate_v}",
            f"answers with a removed citation:  {removed_rate}  {gate_r}",
            f"forbidden citations shown:        {self.forbidden_citations_shown}  (gate = 0)",
        ]
        for kind, rs in sorted(by_kind.items()):
            lines.append(f"  {kind:<8} {sum(r.ok for r in rs)}/{len(rs)} as expected")
        for r in self.results:
            if not r.ok:
                lines.append(
                    f"  FAILED {r.id}: outcome={r.outcome} cited={r.cited_records}"
                )
        lines.append(
            "launch gates met: " + ("YES" if self.meets_launch_gates() else "NO")
        )
        lines.append("(fake services: quality, speed and cost are NOT measured)")
        return "\n".join(lines)


# ---------------- loading ----------------


def load_questions(path: Path) -> list[Question]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        questions.append(
            Question(
                id=d["id"],
                question=d["question"],
                kind=d.get("kind", "real"),
                expect_scope=d.get("expect_scope", "in_scope"),
                expect_outcome=d.get("expect_outcome", "answered"),
                expect_records=tuple(d.get("expect_records", ())),
                must_not_cite=tuple(d.get("must_not_cite", ())),
                fake_model=d.get("fake_model", "honest"),
                notes=d.get("notes", ""),
            )
        )
    return questions


def load_corpus(path: Path) -> FakeVectorStore:
    store = FakeVectorStore()
    for d in json.loads(path.read_text(encoding="utf-8")):
        store.add_record(Record(**d))
    return store


# ---------------- the fake model ----------------


def fake_model_responder(behaviour: str) -> Callable[[str, str, str], str]:
    """Stands in for Gemini. Honest = repeats the first sentence of the top passages with
    the right label. The other behaviours misbehave on purpose to test the verifier."""

    def respond(system: str, prompt: str, model: str) -> str:
        if "JSON only" in system:
            message = prompt.split("User message:\n", 1)[1].strip()
            return json.dumps({"query": message})
        if "summarise" in system:
            return ""
        passages = re.findall(
            r'<passage id="(S\d+)">\n(.*?)\n</passage>', prompt, re.DOTALL
        )
        parts = []
        for sid, text in passages[:2]:
            first = re.split(r"(?<=[.!?])\s", text.strip())[0].rstrip(".")
            parts.append(f"{first} [{sid}].")
        if behaviour == "invent_citation":
            parts.append("The leading case of Nobody v. Nobody settled this [S9].")
        if behaviour == "wrong_quote" and passages:
            parts.append(
                f'The court said "words that never appear anywhere" [{passages[0][0]}].'
            )
        return " ".join(parts)

    return respond


def build_fake_deps(store: FakeVectorStore, behaviour: str = "honest") -> PipelineDeps:
    settings = Settings(
        _env_file=None,
        JEV_ENABLED_SCOPE=True,
        JEV_ENABLED_SAFETY=True,
        JEV_ENABLED_GATE=True,
        JEV_ENABLED_CLAIM=True,
        DATA_AS_OF="sample",
    )
    return PipelineDeps(
        settings=settings,
        llm=FakeLLM(responder=fake_model_responder(behaviour)),
        voyage=FakeVoyage(),
        store=store,
        decisions=DecisionAdapter(
            FakeDecisionBackend(), FakeDecisionBackend(), settings
        ),
        cache=FakeCache(),
        repo=InMemoryMessageRepository(),
    )


# ---------------- running ----------------


async def run_question(q: Question, store: FakeVectorStore) -> QuestionResult:
    deps = build_fake_deps(store, q.fake_model)
    started = time.perf_counter()
    result = await run_pipeline(
        PipelineRequest(user_id="eval", message=q.question), deps
    )
    latency = (time.perf_counter() - started) * 1000

    kept = result.final.citations if result.final else ()
    removed = [r.reason for _, r in deps.repo.invented]
    cited_records = [c.record_id for c in kept]
    forbidden = [r for r in cited_records if r in q.must_not_cite]
    passed = sum(1 for c in kept if c.status in ("verified", "partly"))

    ok = result.outcome == q.expect_outcome and not forbidden
    if result.outcome == "answered":
        ok = ok and set(q.expect_records) <= set(cited_records)
    return QuestionResult(
        id=q.id,
        kind=q.kind,
        outcome=result.outcome,
        ok=ok,
        cited=len(kept) + len(removed),
        passed=passed,
        removed_reasons=removed,
        cited_records=cited_records,
        forbidden_cited=forbidden,
        latency_ms=latency,
    )


async def run_eval(questions: list[Question], store: FakeVectorStore) -> EvalReport:
    results = [await run_question(q, store) for q in questions]
    return EvalReport(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the eval set with fake services.")
    parser.add_argument(
        "--questions", type=Path, default=HERE / "sample_questions.jsonl"
    )
    parser.add_argument("--corpus", type=Path, default=HERE / "sample_corpus.json")
    parser.add_argument(
        "--gate", action="store_true", help="exit 1 if a launch gate fails"
    )
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_eval(load_questions(args.questions), load_corpus(args.corpus))
    )
    print(report.summary())
    return 1 if args.gate and not report.meets_launch_gates() else 0


if __name__ == "__main__":
    sys.exit(main())
