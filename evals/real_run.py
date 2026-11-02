"""Run the 200-question set through the REAL pipeline with FAKE adapters (A103).

Plain words: evals/question_set.py can score a pipeline, but had only a scripted one
that reads the answer key. This file runs the actual code, core.pipeline.run_pipeline,
with the real steps 2-11 (rewrite, decide, search, re-rank, gate, answer, verify, save),
and fakes only the vendors (Voyage, Qdrant, Gemini, Jev). No key, no network, no Qdrant.
It is TWO runs of the same set, side by side:

  (a) every Jev switch forced ON, Jev answering through its real client class
      (adapters/jev.py) over a stub of the vendor SDK. Asks: does the code path work?
  (b) every switch at its shipped default (all off), read from the Settings class,
      never from the environment. Asks: what does the product do today?

WHAT A SWITCH DOES (found while building this, A104): it picks WHO answers a
fixed-choice decision, Jev or the Gemini fallback (adapters/decisions.py,
FallbackDecisions). Off is NOT "no check": the scope check, the gate and the claim
check still run, decided by Gemini. So "fails in (b), passes in (a)" does not mean a
check was skipped; it means the two deciders gave different answers. Here both are
driven by the SAME rules below, so the columns are expected to agree, and a difference
means the two code paths disagree.

THE FAKES, WRITTEN DOWN BEFORE THE FIRST RUN ON THE 200 ROWS (git history shows the
order). They are not tuned: a rule changed after seeing results must be reported.

  Rewrite  returns the user's message unchanged as the query.
  Scope    checked in this order, from core/coverage.json, never from a typed list:
             1. for each item of coverage.excluded, if its singular form (trailing
                "s" dropped) is in the question: the bucket whose description
                contains it, else not_in_dataset.
             2. a four-digit year (1900-2099) later than the snapshot year:
                after_snapshot.
             3. no word that starts like a word of 5+ letters in the in-scope
                criterion or the "normal" safety class (legal_stems): not_legal.
             4. otherwise in_scope.
  Safety   trick if the question tells the system to ignore, disregard or forget its
           instructions, rules or prompt, or asks to reveal them; else personal_advice
           if it has a first-person word (I, my, me, mine, we, our, us); else normal.
           Crude on purpose: a plausible neutral rule, not a model of Jev.
  Gate     the existing FakeDecisions word-overlap rule (adapters/decisions.py), not a
           new one: score = share of the question's words found in the passage;
           answers at >= 0.5, partly above 0, else not_relevant. The gate then
           applies its own 0.6 threshold.
  Claim    the existing FakeDecisions rule: share of the sentence's words found in
           the passage; supports at >= 0.6, partly at >= 0.3, else does_not_support.
  Writer   extractive and faithful: for each of the first three passages it writes
           that passage's first sentence (quote marks removed, cut at 200
           characters) and tags it with its [S#].
  Jev stub answers column (a) with the same rules; its confidence for a gate rating
           is the overlap score, so both deciders hand the gate the same number.

WHERE EACH CATEGORY ENTERS (A111: the latest point that still exercises its subject,
so a fake upstream of the subject cannot veto it). The row's `enter` field says which:
  top          out_of_scope (subject: step 3), rule36 (a feature that does not exist,
               A102; the REASON is asserted, so a refusal for another reason fails).
  below_scope  nothing_found (the gate, step 7), name_bait and in_force_bait (passage
               and answer content, step 8), personal_advice (the safety decision) and
               injection (the writer). The row declares scope in_scope as an input; the
               real pipeline runs from there.
  verifier     fabricated_citation (step 9): the harness builds the answer from the
               row's declared `recall`, hands the verifier an explicit S1-S3 that does
               not contain the recalled record, and asserts on what it removes and
               logs. No scope rule, gate or writer is in the path.
  (answerable stubs are not run.)

WHAT THIS CANNOT SHOW (stated so a green board is not over-read):
  * Every decision is the fake's. These numbers say the code paths route and the
    checks fire; they say nothing about what real Jev or Gemini decide.
  * The writer cannot be talked into anything, so INJECTION rows pass vacuously on the
    model side. They test only the pipeline's own handling of the question text.
  * nothing_found and not_legal results depend on the overlap and vocabulary rules.

    .venv/bin/python -m evals.real_run --out /tmp/real_run.json
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from adapters.cache import FakeCache
from adapters.decisions import FakeDecisions, FallbackDecisions, GeminiDecider
from adapters.jev import (
    SAFETY_CRITERIA,
    FakeChoice,
    FakeJevSDKClient,
    JevClient,
    begin_run,
)
from adapters.llm import FakeLLM
from adapters.memory import FakeCitationLog, FakeStore, FakeUsageMeter
from adapters.qdrant import FakeVectorStore
from adapters.voyage import FakeEmbedder, FakeReranker
from core import coverage
from core.contracts import (
    Deps,
    DraftAnswer,
    Footer,
    Passage,
    PipelineRequest,
    PipelineResult,
)
from core.gate import gate as real_gate
from core.pipeline import run_pipeline
from core.search import hit_to_passage
from core.settings import Settings, get_settings
from core.verify import verify as real_verify
from evals import question_set as qs

HERE = Path(__file__).parent
PRACTICE = HERE.parent / "tests" / "fixtures" / "practice"

JEV_FLAGS = (
    "JEV_ENABLED_SCOPE",
    "JEV_ENABLED_GATE",
    "JEV_ENABLED_CLAIM",
    "JEV_ENABLED_SAFETY",
)
EVAL_SEAL_KEY = "eval-seal-key-not-a-secret"
EVAL_JEV_KEY = (
    "eval-not-a-jev-key"  # a fake client needs a non-empty string, nothing more
)
# A real reported case that the practice corpus does not hold (asserted at start).

_TRICK = re.compile(
    r"\b(ignore|disregard|forget)\b.{0,40}\b(instructions?|rules?|prompt|above|"
    r"previous)\b|system prompt|reveal (your|the) (instructions?|prompt)",
    re.IGNORECASE | re.DOTALL,
)
_FIRST_PERSON = re.compile(r"\b(i|i'm|i've|my|me|mine|we|our|us)\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(19\d\d|20\d\d)\b")


# --- 1. The neutral rules (see the docstring) ----------------------------------------


_WORD = re.compile(r"[a-z]{5,}")


def legal_stems(cov: coverage.Coverage) -> set[str]:
    """What "a legal question" means, taken from the words the real system itself is
    told: the in-scope criterion (core/coverage.py, built from core/coverage.json) and
    the "normal" safety class (adapters/jev.py), as 5-letter word starts. Nothing here
    is typed by hand, so nobody can widen it while looking at a red board; a blind
    spot is fixed by changing those sources, which also change the real system (A109).
    """
    scope = coverage.scope_criteria(cov)[coverage.IN_SCOPE]
    text = f"{scope} {SAFETY_CRITERIA['normal']}"
    return {w[:5] for w in _WORD.findall(text.lower())}


def neutral_scope(query: str, cov: coverage.Coverage, snapshot_year: int) -> str:
    q = query.lower()
    for item in cov.excluded:
        stem = item.lower().rstrip("s")
        if stem in q:
            for bucket, text in cov.buckets.items():
                if stem in text.lower():
                    return bucket
            return coverage.NOT_IN_DATASET
    if any(int(y) > snapshot_year for y in _YEAR.findall(q)):
        return "after_snapshot"
    if not (legal_stems(cov) & {w[:5] for w in _WORD.findall(q)}):
        return coverage.NOT_LEGAL
    return coverage.IN_SCOPE


def neutral_safety(query: str) -> str:
    if _TRICK.search(query):
        return "trick"
    if _FIRST_PERSON.search(query):
        return "personal_advice"
    return "normal"


_RULES = FakeDecisions()  # gate and claim: the rules that already existed


async def neutral_rate(query: str, text: str) -> tuple[str, float]:
    return await _RULES.rate_passage(query, Passage("x", text))


async def neutral_claim(sentence: str, text: str) -> str:
    return await _RULES.claim_support(sentence, Passage("x", text))


def _first_sentence(text: str, limit: int = 200) -> str:
    text = re.sub(r"[\"“”‘’]", "", " ".join(text.split()))
    m = re.search(r"(?<=[a-z0-9\)])\.\s", text)
    cut = text[: m.start()] if m else text
    if len(cut) > limit:
        cut = cut[:limit].rsplit(" ", 1)[0]
    return cut.strip(" .;,")


def write_answer(passages: Sequence[tuple[str, str]]) -> str:
    """Writer rule: first sentence of each of the first three passages, tagged."""
    out = [f"{_first_sentence(t)} [{label}]." for label, t in passages[:3]]
    return " ".join(out)


# --- 2. The fake vendors that carry those rules ---------------------------------------


@dataclass
class RowState:
    """What the current row declares as INPUT (A111): below the scope check the row
    fixes scope; the fake scope rule is not asked."""

    force_scope: str | None = None


@dataclass
class Counts:
    """Which decider answered, counted. Proof that (a) used Jev and (b) did not."""

    jev_requests: int = 0
    gemini_decisions: int = 0
    gemini_other: Counter = field(default_factory=Counter)


class NeutralJevSDK(FakeJevSDKClient):
    """Stands in for typesafe_sdk's client. Answers with the neutral rules."""

    def __init__(self, cov: coverage.Coverage, snapshot_year: int, row: RowState):
        super().__init__()
        self._cov, self._year, self._row = cov, snapshot_year, row

    async def system_one(self, *, state: Any, questions: dict, model: str) -> Any:
        self.calls.append((state, questions))
        answers: dict[str, Any] = {}
        for name in questions:
            if name == "scope":
                scope = self._row.force_scope or neutral_scope(
                    state["question"], self._cov, self._year
                )
                pick = (scope, 0.9)
            elif name == "safety":
                pick = (neutral_safety(state["question"]), 0.9)
            else:
                item = state[name]
                if "sentence" in item:
                    pick = (await neutral_claim(item["sentence"], item["passage"]), 0.9)
                else:
                    pick = await neutral_rate(item["question"], item["passage"])
            answers[name] = type("A", (), {"choice": pick[0], "confidence": pick[1]})()
        usage = type("U", (), {"input_tokens": 0, "output_tokens": 0})()
        return type("R", (), {"answers": answers, "usage": usage})()


class NeutralLLM:
    """The scripted model behind FakeLLM: answers every prompt the pipeline sends it."""

    def __init__(
        self,
        cov: coverage.Coverage,
        snapshot_year: int,
        counts: Counts,
        row: RowState,
    ):
        self._cov, self._year, self._counts, self._row = cov, snapshot_year, counts, row

    def respond(self, prompt: str, system: str = "") -> str:  # sync, as FakeLLM wants
        first = prompt.lstrip().split("\n", 1)[0]
        if first.startswith("Turn the user's latest message"):
            msg = prompt.split("Latest message:", 1)[1].strip()
            return json.dumps(
                {"query": msg, "act": None, "section": None, "case_number": None,
                 "year": None}
            )  # fmt: skip
        if first.startswith("You are a legal research assistant"):
            body = prompt.split("Passages:\n", 1)[1]
            blocks = re.split(r"\n\n(?=\[S\d+\] )", body.strip())
            parsed = []
            for b in blocks:
                m = re.match(r"\[(S\d+)\] (.*)", b, re.DOTALL)
                if m:
                    parsed.append((m.group(1), m.group(2)))
            return write_answer(parsed)
        # Gemini-path decisions: counted, so (b) can be shown to have used them
        self._counts.gemini_decisions += 1
        if first.startswith("You make a fixed-choice decision"):
            self._counts.gemini_other["decide"] += 1
            q = re.search(r"Question: (.*?)\nChoose", prompt, re.DOTALL).group(1)
            return json.dumps(
                {"scope": self._row.force_scope
                 or neutral_scope(q, self._cov, self._year),
                 "safety": neutral_safety(q), "court": None, "year_from": None,
                 "year_to": None, "act": None, "section": None}
            )  # fmt: skip
        if first.startswith("Does the passage help answer"):
            self._counts.gemini_other["rate"] += 1
            m = re.search(r"Question: (.*?)\nPassage: (.*)", prompt, re.DOTALL)
            rating, score = _run(neutral_rate(m.group(1), m.group(2)))
            return json.dumps({"rating": rating, "score": score})
        if first.startswith("Does the passage support the sentence"):
            self._counts.gemini_other["claim"] += 1
            m = re.search(r"Sentence: (.*?)\nPassage: (.*)", prompt, re.DOTALL)
            return _run(neutral_claim(m.group(1), m.group(2)))
        raise ValueError(f"the fake model met a prompt it has no rule for: {first!r}")


def _run(coro):
    """The two neutral helpers are async only because FakeDecisions' methods are; they
    do no waiting. Drive one to its end without a running loop."""
    try:
        coro.send(None)
    except StopIteration as done:
        return done.value
    raise RuntimeError("a neutral rule waited; it must not")


# --- 3. Settings: forced for the run only ---------------------------------------------


def run_settings(*, jev_on: bool) -> Settings:
    """A Settings built from the CLASS DEFAULTS only: no .env, no environment variable
    can change it. The four Jev switches are set here and nowhere else; `jev_on=False`
    gives each its shipped default. Never used outside evals/ (a test scans for
    that)."""
    base = {
        name: f.get_default(call_default_factory=True)
        for name, f in Settings.model_fields.items()
    }
    base.update(
        ENVIRONMENT="development",
        SEAL_KEY=EVAL_SEAL_KEY,
        DATA_AS_OF="2026-08-31",
    )
    if jev_on:
        base.update({flag: True for flag in JEV_FLAGS})
        base["JEV_API_KEY"] = EVAL_JEV_KEY
    return Settings(_env_file=None, **base)


@contextmanager
def eval_seal_key():
    """core.verify seals with get_settings().SEAL_KEY (a process-wide setting). Give it
    the eval key for the run and put everything back afterwards."""
    old = os.environ.get("SEAL_KEY")
    os.environ["SEAL_KEY"] = EVAL_SEAL_KEY
    get_settings.cache_clear()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("SEAL_KEY", None)
        else:
            os.environ["SEAL_KEY"] = old
        get_settings.cache_clear()


# --- 4. One column = one wired pipeline ----------------------------------------------


def load_corpus(settings: Settings) -> tuple[FakeVectorStore, set[str]]:
    """All practice records (judgment chunks and Act sections) as the fake
    collection."""
    store = FakeVectorStore(settings)
    ids: set[str] = set()
    for c in _records():
        store.add_law(
            c["chunk_id"], c["text"], **{k: v for k, v in c.items() if k != "text"}
        )
        ids.add(c["chunk_id"])
    return store, ids


def _records():
    for name in ("chunks", "act_sections"):
        with gzip.open(PRACTICE / f"{name}.jsonl.gz", "rt") as fh:
            for line in fh:
                yield json.loads(line)


def check_recall_rows(questions: Sequence[qs.Question]) -> None:
    """A recall row must mean what its bait says: "nonexistent" names a case the corpus
    does not hold, "exists_not_retrieved" one it does."""
    recs = list(_records())
    blob = " ".join(c["text"].casefold() for c in recs)
    ids = {c["chunk_id"] for c in recs}
    bad = []
    for q in questions:
        if "recall" not in q.row:
            continue
        if q.bait == "nonexistent" and q.must_not_contain[0].casefold() in blob:
            bad.append(f"{q.id}: {q.must_not_contain[0]!r} is in the corpus")
        if q.bait == "exists_not_retrieved" and not set(q.must_not_cite) <= ids:
            bad.append(f"{q.id}: a must_not_cite record is not in the corpus")
    if bad:
        raise RuntimeError("recall rows do not match their bait: " + "; ".join(bad))


@dataclass
class Column:
    name: str
    settings: Settings
    counts: Counts
    sdk: NeutralJevSDK
    retrieved: dict[str, list[str]] = field(default_factory=dict)
    current: str = ""  # the question being run (the gate does not see the message)
    recall_log: dict[str, str] = field(
        default_factory=dict
    )  # row id -> what check 1 did
    result_keys: dict[str, str] = field(default_factory=dict)  # row id -> what user got
    removed: Counter = field(default_factory=Counter)
    pipeline: Callable[[dict], Awaitable[PipelineResult]] | None = None

    def retrieved_for(self, row: dict) -> list[str]:
        """Record ids the gate handed the model (S1-S8). A question that stopped before
        the gate handed it nothing."""
        return self.retrieved.get(row["question"], [])


def explicit_passages(
    store: FakeVectorStore, banned: Sequence[str], settings: Settings, n: int = 3
) -> list[Passage]:
    """The S1..Sn a verifier row is given: the first n judgment records of the corpus
    that are not on the row's avoid-list. Explicit, so what the verifier was and was not
    handed is known by construction, not by what a fake search happened to return."""
    out: list[Passage] = []
    for h in store.law:
        if "section_number" in h.payload or h.record_id in banned:
            continue
        p = hit_to_passage(h, settings=settings)
        out.append(replace(p, source_id=f"S{len(out) + 1}"))
        if len(out) == n:
            break
    return out


def build_column(name: str, *, jev_on: bool, store: FakeVectorStore) -> Column:
    settings = run_settings(jev_on=jev_on)
    cov = coverage.load_coverage()
    year = int(re.search(r"(\d{4})", settings.SNAPSHOT_VERSION).group(1))
    counts, row_state = Counts(), RowState()
    sdk = NeutralJevSDK(cov, year, row_state)
    col = Column(name, settings, counts, sdk)
    llm = FakeLLM(NeutralLLM(cov, year, counts, row_state).respond)
    decisions = FallbackDecisions(
        JevClient(settings, client=sdk, choice=FakeChoice),
        GeminiDecider(llm, settings),
        settings,
    )

    async def recording_gate(rq, passages, deps):
        g = await real_gate(rq, passages, deps)
        col.retrieved[col.current] = [p.record_id for p in g.passages]
        return g

    def new_deps() -> Deps:
        return Deps(
            settings=settings,
            embedder=FakeEmbedder(),
            reranker=FakeReranker(),
            vectors=store,
            llm=llm,
            decisions=decisions,
            cache=FakeCache(),
            usage=FakeUsageMeter(),
            store=FakeStore(),
            citation_log=FakeCitationLog(),
            gate=recording_gate,
            verify=real_verify,
            begin_run=begin_run,
        )

    def note(row: dict, result: PipelineResult, deps: Deps) -> None:
        col.result_keys[row["id"]] = result.message_key or result.outcome
        for _, _, r in deps.citation_log.rows:
            col.removed[r.reason] += 1

    async def through_pipeline(row: dict) -> PipelineResult:
        """Entry "top" or "below_scope": the real pipeline, steps 1-11. Below the
        scope check the row declares scope in_scope; safety is still the fake's."""
        row_state.force_scope = (
            coverage.IN_SCOPE if row.get("enter") == "below_scope" else None
        )
        deps = new_deps()
        request = PipelineRequest(user_id="eval-user", message=row["question"])
        result = await run_pipeline(request, deps)
        note(row, result, deps)
        return result

    async def at_verifier(row: dict) -> PipelineResult:
        """Entry "verifier" (step 9 only): build the answer, hand the verifier an
        explicit S1-S3, assert on what it removes and logs. No scope rule, gate or
        writer runs."""
        deps = new_deps()
        passages = explicit_passages(store, row.get("must_not_cite", []), settings)
        supported = _first_sentence(passages[0].text)
        text = f"{supported} [S1]. {row['recall']} [S1]."
        draft = DraftAnswer(text, "eval", 0, 0, row["question"])
        verified = await real_verify(draft, passages, deps)
        logged = tuple(r for _, _, r in deps.citation_log.rows)
        if logged != verified.removed:  # the log must be what the verifier removed
            raise RuntimeError(
                "the invented-citation log differs from what was removed"
            )
        col.retrieved[row["question"]] = [p.record_id for p in passages]
        footer = Footer(settings.DATA_AS_OF, settings.SNAPSHOT_VERSION)
        result = PipelineResult("answered", verified, footer, removed=verified.removed)
        note(row, result, deps)
        col.recall_log[row["id"]] = (
            "removed"
            if any(r.reason == row.get("expect_removed") for r in logged)
            else "let_through"
        )
        return result

    async def pipeline(row: dict) -> PipelineResult:
        col.current = row["question"]
        if row.get("enter") == "verifier":
            return await at_verifier(row)
        return await through_pipeline(row)

    col.pipeline = pipeline
    return col


def require_path_used(col: Column, jev_on: bool) -> None:
    """Fail loudly if the column did not run the decider it claims to: a Jev client with
    no key falls back to Gemini silently, and that would make (a) a copy of (b)."""
    if jev_on and (not col.sdk.calls or col.counts.gemini_decisions):
        raise RuntimeError(
            f"column {col.name}: expected Jev to answer every decision, got "
            f"{len(col.sdk.calls)} Jev requests and {col.counts.gemini_decisions} "
            "Gemini decisions"
        )
    if not jev_on and (col.sdk.calls or not col.counts.gemini_decisions):
        raise RuntimeError(
            f"column {col.name}: expected only the Gemini fallback, got "
            f"{len(col.sdk.calls)} Jev requests"
        )


# --- 5. Both columns, side by side ---------------------------------------------------


@dataclass
class ColumnResult:
    column: Column
    outcomes: list[qs.Outcome]


async def run_column(
    col: Column, questions: Sequence[qs.Question], corpus_ids: set[str], jev_on: bool
) -> ColumnResult:
    outcomes = await qs.run_question_set(
        questions,
        col.pipeline,
        retrieved_for=col.retrieved_for,
        corpus_ids=corpus_ids,
    )
    if any(o.status != qs.NOT_RUN for o in outcomes):  # nothing ran: nothing to prove
        require_path_used(col, jev_on)
    return ColumnResult(col, outcomes)


def classify(a: qs.Outcome, b: qs.Outcome) -> str:
    """ok | switched_off (fails with the defaults, passes forced on) | broken (fails in
    both) | worse_forced_on (passes with the defaults, fails forced on) | not_run."""
    if a.status == qs.NOT_RUN:
        return "not_run"
    if a.status == qs.PASS and b.status == qs.PASS:
        return "ok"
    if a.status == qs.PASS:
        return "switched_off"
    return "broken" if b.status == qs.FAIL else "worse_forced_on"


def compare(
    a: Sequence[qs.Outcome], b: Sequence[qs.Outcome]
) -> dict[str, dict[str, int]]:
    out: dict[str, Counter] = {}
    for x, y in zip(a, b, strict=True):
        out.setdefault(x.category, Counter())[classify(x, y)] += 1
    return {k: dict(v) for k, v in out.items()}


def _kinds(r: ColumnResult, cat: str) -> tuple[int, int]:
    """(answered, refused as not a legal question) among a category's run rows, so a
    board made of refusals cannot pass for a board made of answers."""
    ids = [o.id for o in r.outcomes if o.category == cat and o.status != qs.NOT_RUN]
    keys = [r.column.result_keys.get(i, "") for i in ids]
    return keys.count("answered"), keys.count("out_of_scope:not_legal")


def render_side_by_side(a: ColumnResult, b: ColumnResult) -> str:
    ta, tb = qs.by_category(a.outcomes), qs.by_category(b.outcomes)
    cmp = compare(a.outcomes, b.outcomes)
    head = (
        f"{'category':<22}{'run':>5}{'(a) forced on':>15}{'(b) defaults':>15}"
        f"{'switched off':>14}{'broken':>8}{'worse on':>10}{'answered':>10}"
        f"{'not_legal':>11}"
    )
    lines = [head, "-" * len(head)]

    def cell(t: qs.Tally) -> str:
        return "NOT RUN" if t.pass_rate is None else f"{t.passed}/{t.run}"

    for cat in ta:
        c = cmp[cat]
        lines.append(
            f"{cat:<22}{ta[cat].run:>5}{cell(ta[cat]):>15}{cell(tb[cat]):>15}"
            f"{c.get('switched_off', 0):>14}{c.get('broken', 0):>8}"
            f"{c.get('worse_forced_on', 0):>10}"
            f"{_kinds(a, cat)[0]:>10}{_kinds(a, cat)[1]:>11}"
        )
    oa, ob = qs.tally(a.outcomes), qs.tally(b.outcomes)
    lines += [
        "-" * len(head),
        f"{'OVERALL':<22}{oa.run:>5}{cell(oa):>15}{cell(ob):>15}",
        f"{oa.not_run} of {oa.total} questions are stubs: NOT RUN in both columns, "
        "counted in neither",
        "gate: " + (
            "READY" if not qs.gate_blockers(a.outcomes) else "NOT READY - "
            + "; ".join(qs.gate_blockers(a.outcomes))
        ),
    ]  # fmt: skip
    return "\n".join(lines)


def to_json(a: ColumnResult, b: ColumnResult, set_path: Path) -> dict[str, Any]:
    def meta(r: ColumnResult) -> dict[str, Any]:
        c = r.column
        return {
            "name": c.name,
            "jev_flags": {f: getattr(c.settings, f) for f in JEV_FLAGS},
            "jev_requests": len(c.sdk.calls),
            "gemini_decisions": c.counts.gemini_decisions,
            "gemini_decisions_by_kind": dict(c.counts.gemini_other),
            "verifier_removals_by_reason": dict(c.removed),
            "recall_rows": dict(c.recall_log),
        }

    return {
        "meta": {
            "what": "real pipeline, fake adapters; every decision is a fake's rule",
            "set": set_path.name,
            "set_sha256": qs.set_fingerprint(set_path),
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "columns": {"a": meta(a), "b": meta(b)},
        },
        "a_forced_on": qs.to_json(a.outcomes, {}, True),
        "b_defaults": qs.to_json(b.outcomes, {}, True),
        "comparison_by_category": compare(a.outcomes, b.outcomes),
        "per_question": [
            {
                "id": x.id,
                "category": x.category,
                "a": x.status,
                "b": y.status,
                "class": classify(x, y),
                "a_reasons": list(x.reasons),
                "b_reasons": list(y.reasons),
            }
            for x, y in zip(a.outcomes, b.outcomes, strict=True)
            if x.status != qs.NOT_RUN
        ],
    }


async def run_both(
    questions: Sequence[qs.Question],
) -> tuple[ColumnResult, ColumnResult]:
    check_recall_rows(questions)
    with eval_seal_key():
        store, corpus_ids = load_corpus(run_settings(jev_on=False))
        a = await run_column(
            build_column("a_forced_on", jev_on=True, store=store),
            questions,
            corpus_ids,
            True,
        )
        b = await run_column(
            build_column("b_defaults", jev_on=False, store=store),
            questions,
            corpus_ids,
            False,
        )
    return a, b


async def _main(args: argparse.Namespace) -> int:
    questions = qs.load_set(args.questions)
    a, b = await run_both(questions)
    print(render_side_by_side(a, b))
    for label, r in (("(a)", a), ("(b)", b)):
        c = r.column
        print(
            f"{label} Jev requests {len(c.sdk.calls)}, Gemini-path decisions "
            f"{c.counts.gemini_decisions}, verifier removals {dict(c.removed)}"
        )
        print(f"{label} recall rows: {dict(Counter(c.recall_log.values()))}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(to_json(a, b, args.questions), indent=2, default=str) + "\n"
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--questions", type=Path, default=qs.DEFAULT_SET)
    ap.add_argument("--out", type=Path, help="write the JSON result here")
    raise SystemExit(asyncio.run(_main(ap.parse_args())))
