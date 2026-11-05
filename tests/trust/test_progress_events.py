"""Live progress events (pipeline steps 1-9 telling the client where they are).

The promise being protected: a step event is a NAME and COUNTS, never a case name,
citation, quote or record id, and no verified citation can reach the client before the
verifier (step 9) has finished. Step 10 is unchanged: citations arrive as ONE final
event afterwards. These tests try to break both promises."""

from __future__ import annotations

import ast
import asyncio
import dataclasses
import json
import re
from pathlib import Path

import pytest

from adapters.cache import FakeCache
from adapters.decisions import FakeDecisions
from adapters.llm import FakeLLM
from adapters.memory import FakeCitationLog, FakeStore, FakeUsageMeter
from adapters.qdrant import FakeVectorStore
from adapters.voyage import FakeEmbedder, FakeReranker
from api import bridge
from core.contracts import (
    STEP_NAMES,
    Deps,
    PipelineRequest,
    StepEvent,
    run_pipeline,
    stream_events,
)
from core.gate import gate
from core.settings import get_settings
from core.verify import verify

CASE_ID = "rec-zq-00917"
CASE_TITLE = "Zorblax versus Quuxington"
CASE_CITE = "(1987) 41 XYZ 777"
TEXT = (
    "Personal liberty under Article 21 cannot be curtailed except by procedure "
    "established by law, and bail is the rule while jail is the exception."
)
QUERY = "personal liberty bail"


def _llm() -> FakeLLM:
    def respond(prompt: str, system: str) -> str:
        if prompt.startswith("Turn the user's"):
            return '{"query": "%s"}' % QUERY
        m = re.search(r"\[S1\] (.*?)(?:\n\n|\Z)", prompt, re.S)
        words = m.group(1).split()[:12] if m else []
        return " ".join(words) + " [S1]."

    return FakeLLM(respond)


def make_deps(verify_fn=verify) -> Deps:
    settings = get_settings()
    store = FakeVectorStore(settings)
    store.add_law(
        CASE_ID,
        TEXT,
        title=CASE_TITLE,
        citation=CASE_CITE,
        pdf_url="https://example.test/zq.pdf",
    )
    return Deps(
        settings=settings,
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        vectors=store,
        llm=_llm(),
        decisions=FakeDecisions(),
        cache=FakeCache(),
        usage=FakeUsageMeter(),
        store=FakeStore(),
        citation_log=FakeCitationLog(),
        gate=gate,
        verify=verify_fn,
    )


REQUEST = PipelineRequest("u1", "Tell me about personal liberty and bail")


# ---- 1. a step event cannot hold text -------------------------------------------
def test_step_event_has_only_a_name_and_two_counts():
    assert [f.name for f in dataclasses.fields(StepEvent)] == [
        "step",
        "found",
        "kept",
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"step": "searching", "found": CASE_TITLE},  # a case name as a "count"
        {"step": "checking", "found": CASE_CITE},  # a citation
        {"step": "writing", "kept": CASE_ID},  # a record id
        {"step": f"searching {CASE_TITLE}"},  # text smuggled into the name
        {"step": "verifying", "found": True},  # bool is not a count
        {"step": "checking", "found": -1},
        {"step": "unknown"},
        {"step": "writing", "found": 8.5},
    ],
)
def test_step_event_refuses_anything_that_is_not_a_name_and_counts(kwargs):
    with pytest.raises(ValueError):
        StepEvent(**kwargs)


# ---- 2. what the pipeline actually emits -----------------------------------------
async def test_pipeline_step_events_carry_no_case_name_citation_quote_or_id():
    events: list[StepEvent] = []
    res = await run_pipeline(REQUEST, make_deps(), events.append)
    assert res.outcome == "answered"
    wire = json.dumps([dataclasses.asdict(e) for e in events])
    for secret in (CASE_ID, CASE_TITLE, CASE_CITE, "Zorblax", "Quuxington"):
        assert secret not in wire
    for word in re.findall(r"[A-Za-z]{6,}", TEXT):  # nothing quoted from the record
        assert word.lower() not in wire.lower()
    assert [e.step for e in events] == list(STEP_NAMES)
    checking, writing = events[2], events[3]
    assert checking.found and checking.kept is None
    assert writing.found >= writing.kept >= 1  # "N passages found, M kept"


def test_pipeline_only_builds_step_events_from_names_and_len_counts():
    """Read the pipeline's source: every StepEvent(...) is a literal step name plus
    `found=len(...)` / `kept=len(...)`. Passing a passage field would fail this."""
    path = Path(__file__).resolve().parents[2] / "core" / "pipeline.py"
    calls = [
        n
        for n in ast.walk(ast.parse(path.read_text()))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "StepEvent"
    ]
    assert len(calls) == len(STEP_NAMES)  # one per named step, no stray emitters
    for c in calls:
        assert len(c.args) == 1
        assert isinstance(c.args[0], ast.Constant) and c.args[0].value in STEP_NAMES
        for kw in c.keywords:
            assert kw.arg in ("found", "kept")
            assert isinstance(kw.value, ast.Call) and kw.value.func.id == "len"


async def test_a_failing_progress_callback_cannot_change_the_answer():
    def boom(_):
        raise RuntimeError("client went away")

    res = await run_pipeline(REQUEST, make_deps(), boom)
    assert res.outcome == "answered" and res.answer is not None


# ---- 3. no citation reaches the client before verification completes -------------
async def _collect(gen, into: list):
    async for name, data in gen:
        into.append((name, data))


async def test_no_citation_reaches_the_client_before_verify_completes():
    release = asyncio.Event()
    entered = asyncio.Event()

    async def slow_verify(draft, passages, deps):
        entered.set()
        await release.wait()  # the verifier is "still running"
        return await verify(draft, passages, deps)

    deps = make_deps(slow_verify)

    async def runner(req, on_step):
        return await run_pipeline(req, deps, on_step)

    frames: list[tuple[str, dict]] = []
    consumer = asyncio.create_task(
        _collect(
            bridge.stream_answer(
                REQUEST, runner, stream_events, "2026-08-31", "c", "r"
            ),
            frames,
        )
    )
    await asyncio.wait_for(entered.wait(), 2)
    await asyncio.sleep(0.05)  # give any early frame every chance to appear
    names_so_far = [n for n, _ in frames]
    assert set(names_so_far) == {"step"}, names_so_far  # no token, no citation, no done
    assert frames[-1][1]["step"] == "verifying"
    blob = json.dumps(frames)
    for secret in (CASE_ID, CASE_TITLE, CASE_CITE, "[S1]"):
        assert secret not in blob

    release.set()
    await asyncio.wait_for(consumer, 2)
    names = [n for n, _ in frames]
    ci = names.index("citations")
    assert names.count("citations") == 1 and names[-1] == "done"
    assert all(n == "step" for n in names[: names.index("token")])
    assert "step" not in names[names.index("token") :]  # no step after the first token
    assert ci > max(i for i, n in enumerate(names) if n in ("step", "token"))
    # Only the single final event may name the record or its citation string.
    for n, d in frames[:ci]:
        assert CASE_CITE not in json.dumps(d)
    assert CASE_CITE in json.dumps(frames[ci][1])


async def test_a_late_step_event_can_never_follow_the_citations():
    """A runner that fires a step event AFTER finishing (a stray background task) must
    not put a step on the wire after the answer has started."""
    deps = make_deps()

    async def runner(req, on_step):
        result = await run_pipeline(req, deps, on_step)
        asyncio.get_running_loop().call_later(0.01, on_step, StepEvent("writing"))
        return result

    frames: list[tuple[str, dict]] = []
    await _collect(
        bridge.stream_answer(REQUEST, runner, stream_events, "2026-08-31", "c", "r"),
        frames,
    )
    await asyncio.sleep(0.05)
    names = [n for n, _ in frames]
    first_token = names.index("token")
    assert "step" not in names[first_token:]
    assert names.count("citations") == 1 and names[-1] == "done"


async def test_a_refused_answer_streams_steps_then_done_and_no_citation():
    deps = make_deps()
    deps.decisions = FakeDecisions(scope="needs_high_court")  # step 3 refuses

    async def runner(req, on_step):
        return await run_pipeline(req, deps, on_step)

    frames: list[tuple[str, dict]] = []
    await _collect(
        bridge.stream_answer(REQUEST, runner, stream_events, "2026-08-31", "c", "r"),
        frames,
    )
    names = [n for n, _ in frames]
    assert names == ["step", "done"] and frames[1][1]["refused"]
