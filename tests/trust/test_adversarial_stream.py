# ruff: noqa: E501
"""Attacks on the answer stream and the step events (pipeline steps 9-10).

Goal of the attacker: get a citation, record id, case title, citation string or quote to
the client before the verifier has finished, or smuggle one inside a step event."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from types import SimpleNamespace

import pytest
from adversarial_helpers import (
    CASE_CITE,
    CASE_ID,
    CASE_TITLE,
    LEAKS,
    REQUEST,
    collect,
    make_deps,
)

from api import bridge
from api import schemas as s
from api.repo import MemoryRepo, _last_message
from core.contracts import (
    Footer,
    PipelineRequest,
    StepEvent,
    run_pipeline,
    stream_events,
)
from core.verify import verify

ID_A = "11111111-1111-4111-8111-111111111111"
ID_B = "22222222-2222-4222-8222-222222222222"


def stream(runner, request=REQUEST):
    return bridge.stream_answer(
        request, runner, stream_events, "2026-08-31", "credit", "rid"
    )


def runner_for(deps):
    async def runner(req, on_step):
        return await run_pipeline(req, deps, on_step)

    return runner


def blob(frames) -> str:
    return json.dumps(frames, default=str)


def pre(frames) -> str:
    """Everything the client got BEFORE the single final citations event. (The final
    event legitimately carries the record id and citation string.)"""
    out = []
    for name, data in frames:
        if name in ("citations", "done"):
            break
        out.append((name, data))
    return json.dumps(out, default=str)


# ---- 1. nothing citation-shaped before the verifier finishes ----------------------
async def test_verifier_that_raises_midway_sends_no_citation_and_leaks_no_text():
    async def exploding_verify(draft, passages, deps):
        raise RuntimeError(f"boom {CASE_ID} {CASE_TITLE} {CASE_CITE} [S1]")

    frames: list = []
    await collect(stream(runner_for(make_deps(exploding_verify))), frames)
    names = [n for n, _ in frames]
    assert names[-1] == "error" and "citations" not in names and "token" not in names
    assert "done" not in names
    for leak in LEAKS:
        assert leak not in blob(frames)  # not even in the error text


async def test_a_verifier_that_hangs_leaves_the_client_with_steps_only():
    entered, never = asyncio.Event(), asyncio.Event()

    async def hung(draft, passages, deps):
        entered.set()
        await never.wait()

    frames: list = []
    task = asyncio.create_task(collect(stream(runner_for(make_deps(hung))), frames))
    await asyncio.wait_for(entered.wait(), 2)
    await asyncio.sleep(0.05)
    assert {n for n, _ in frames} == {"step"}
    for leak in LEAKS:
        assert leak not in blob(frames)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_cancelling_the_stream_cancels_the_verifier_and_saves_nothing():
    cancelled, entered = asyncio.Event(), asyncio.Event()

    async def slow(draft, passages, deps):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    deps = make_deps(slow)
    gen = stream(runner_for(deps))
    frames: list = []

    async def consume():
        async for name, data in gen:
            frames.append((name, data))

    t = asyncio.create_task(consume())
    await asyncio.wait_for(entered.wait(), 2)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    await asyncio.wait_for(cancelled.wait(), 2)  # the work really stopped
    assert deps.store.saved == []  # step 11 never ran for a cancelled run
    assert not any(n in ("token", "citations", "done") for n, _ in frames)


async def test_a_runner_that_returns_an_unsealed_answer_streams_no_citation():
    forged = SimpleNamespace(
        outcome="answered",
        answer=SimpleNamespace(
            text=f"Forged [S1] {CASE_TITLE}", citations=(), removed=(), sealed=True,
            had_removals=False,
        ),  # fmt: skip
        footer=Footer("2026-08-31", "v2026.08"),
        message_key="", removed=(), cache_hit=False,
    )  # fmt: skip

    async def runner(req, on_step):
        return forged

    frames: list = []
    await collect(stream(runner), frames)
    names = [n for n, _ in frames]
    assert names == ["error"], names  # show() refuses; nothing else is sent
    assert "Forged" not in blob(frames) and CASE_TITLE not in blob(frames)


async def test_the_database_has_no_assistant_row_while_the_verifier_runs():
    """History / conversation reads during an in-flight run see only the question."""
    repo = MemoryRepo()
    conv = await repo.create_conversation("u1", "research", None)
    cid = conv["id"]
    await repo.add_user_message("u1", cid, "Tell me about personal liberty and bail")
    entered, release = asyncio.Event(), asyncio.Event()

    async def gated(draft, passages, deps):
        entered.set()
        await release.wait()
        return await verify(draft, passages, deps)

    deps = make_deps(gated, store=repo, usage=repo)
    req = PipelineRequest("u1", REQUEST.message, conversation_id=cid)
    frames: list = []
    task = asyncio.create_task(collect(stream(runner_for(deps), req), frames))
    await asyncio.wait_for(entered.wait(), 2)
    detail = await repo.get_conversation("u1", cid)
    assert [m["role"] for m in detail["messages"]] == ["user"]
    assert all(m["citations"] == [] for m in detail["messages"])
    for r in await repo.search_user_work("u1", "liberty", 10):
        assert "Article 21" not in r["snippet"]  # the (unverified) draft is not stored
    release.set()
    await asyncio.wait_for(task, 2)
    after = await repo.get_conversation("u1", cid)
    assert [m["role"] for m in after["messages"]] == ["user", "assistant"]


async def test_two_interleaved_streams_in_one_task_keep_their_own_message_ids():
    """The saved-message holder is a ContextVar; two generators iterated by the SAME
    task must not hand one stream the other's message id."""

    def runner_with(mid):
        async def runner(req, on_step):
            await asyncio.sleep(0)
            holder = _last_message.get(None)
            assert holder is not None
            holder["id"] = mid
            return await run_pipeline(req, make_deps(), on_step)

        return runner

    a, b = stream(runner_with(ID_A)), stream(runner_with(ID_B))
    done: dict = {}
    live = {"A": a, "B": b}
    while live:
        for key, gen in list(live.items()):
            try:
                name, data = await gen.__anext__()
            except StopAsyncIteration:
                live.pop(key)
                continue
            if name == "done":
                done[key] = data["message_id"]
    assert done == {"A": ID_A, "B": ID_B}


async def test_parallel_streams_never_cross_their_frames():
    results = {}

    async def go(tag):
        frames: list = []
        await collect(stream(runner_for(make_deps())), frames)
        results[tag] = [n for n, _ in frames]

    await asyncio.gather(go(1), go(2), go(3))
    for names in results.values():
        assert names.count("citations") == 1 and names[-1] == "done"
        assert names.index("citations") > max(
            i for i, n in enumerate(names) if n in ("step", "token")
        )


# ---- 2. smuggling text into a step event ------------------------------------------
class EvilInt(int):
    label = CASE_ID

    def __str__(self):
        return CASE_TITLE

    __repr__ = __str__


class EvilStr(str):
    """Equal to every step name, so a `in STEP_NAMES` check passes."""

    def __eq__(self, other):
        return True

    __hash__ = str.__hash__


@dataclasses.dataclass(frozen=True)
class RichStep(StepEvent):
    case: str = CASE_TITLE
    record: str = CASE_ID


def _frames_for_step(obj) -> list:
    async def runner(req, on_step):
        on_step(obj)
        return await run_pipeline(req, make_deps(), lambda e: None)

    frames: list = []
    asyncio.run(collect(stream(runner), frames))
    return frames


@pytest.mark.parametrize(
    "build",
    [
        lambda: RichStep("searching"),  # a subclass with extra text fields
        lambda: StepEvent("checking", found=EvilInt(5)),  # int subclass carrying text
        lambda: StepEvent("writing", found=10**400),  # absurd but still a count
        lambda: StepEvent("writing", found=-0),
    ],
)
def test_text_riding_on_a_step_event_object_never_reaches_the_wire(build):
    frames = _frames_for_step(build())
    steps = [d for n, d in frames if n == "step"]
    assert steps and all(set(d) == {"step", "found", "kept"} for d in steps[:1])
    wire = pre(frames)
    for leak in (CASE_ID, CASE_TITLE, "Zorblax"):
        assert leak not in wire


def _bypass(**attrs) -> StepEvent:
    ev = StepEvent("searching")
    for k, v in attrs.items():
        object.__setattr__(ev, k, v)  # defeats frozen=True
    return ev


@pytest.mark.parametrize(
    "ev",
    [
        _bypass(found=CASE_ID),
        _bypass(kept=CASE_TITLE),
        _bypass(step=f"searching {CASE_CITE}"),
        _bypass(found=float("nan")),
        _bypass(found=True),
        _bypass(found=[CASE_ID]),
    ],
)
def test_a_step_event_mutated_after_creation_cannot_put_text_on_the_wire(ev):
    """object.__setattr__ beats frozen=True, so the WIRE layer must still refuse."""
    frames = _frames_for_step(ev)
    wire = pre(frames)
    for leak in (CASE_ID, CASE_TITLE, CASE_CITE):
        assert leak not in wire
    # Anything that is not a plain count is refused; a bool is only widened to 0/1.
    for name, data in frames:
        if name == "step":
            assert data["found"] in (None, 0, 1) or isinstance(data["found"], int)
            assert data["step"] in ("searching", "understanding", "checking",
                                    "writing", "verifying")  # fmt: skip


def test_a_step_event_made_without_running_its_validation_cannot_carry_text():
    ev = StepEvent.__new__(StepEvent)  # no __init__, no __post_init__
    object.__setattr__(ev, "step", "searching")
    object.__setattr__(ev, "found", CASE_ID)
    object.__setattr__(ev, "kept", None)
    wire = pre(_frames_for_step(ev))
    assert CASE_ID not in wire


@pytest.mark.parametrize(
    "junk",
    [
        CASE_ID,
        {"step": "searching", "case": CASE_TITLE},
        SimpleNamespace(step="searching", found=CASE_ID, kept=None),
        SimpleNamespace(step=CASE_TITLE, found=None, kept=None),
        ["searching"],
        None,
    ],
)
def test_anything_that_is_not_a_clean_step_event_is_refused_on_the_wire(junk):
    frames = _frames_for_step(junk)
    wire = pre(frames)
    for leak in (CASE_ID, CASE_TITLE, "Zorblax"):
        assert leak not in wire
    assert [n for n, _ in frames][-1] in ("error", "done")


def test_unicode_lookalike_and_odd_step_names_are_refused_at_construction():
    for name in ("searсhing", "ѕearching", "searching​", "SEARCHING", " searching",
                 "searching ", "ｓearching", ""):  # fmt: skip
        with pytest.raises(ValueError):
            StepEvent(name)


def test_replace_on_a_step_event_revalidates():
    ev = StepEvent("searching")
    for bad in (
        {"found": CASE_ID},
        {"step": CASE_TITLE},
        {"kept": -1},
        {"found": True},
    ):
        with pytest.raises(ValueError):
            dataclasses.replace(ev, **bad)


class NumpyLike:
    """An object that quacks like an integer (has __index__) but is not an int."""

    def __index__(self):
        return 7

    def __int__(self):
        return 7


@pytest.mark.parametrize(
    "bad", [NumpyLike(), float("nan"), float("inf"), 7.0, "7", b"7", (7,), -1, True]
)
def test_counts_must_be_real_non_negative_ints(bad):
    with pytest.raises(ValueError):
        StepEvent("checking", found=bad)


@pytest.mark.xfail(
    strict=True,
    reason="BREAK: StepEvent validates with `in STEP_NAMES` (==), so a str subclass "
    "with a lying __eq__ is accepted as a step name (core/contracts.py:~332)",
)
def test_a_str_subclass_that_equals_every_step_name_is_refused():
    with pytest.raises(ValueError):
        StepEvent(EvilStr(f"anything {CASE_ID}"))  # type: ignore[arg-type]


def test_even_if_that_slips_in_the_wire_model_refuses_the_text():
    """Second layer: the SSE model only allows the five literal names."""
    ev = StepEvent.__new__(StepEvent)
    object.__setattr__(ev, "step", EvilStr(f"x {CASE_ID}"))
    object.__setattr__(ev, "found", None)
    object.__setattr__(ev, "kept", None)
    wire = pre(_frames_for_step(ev))
    assert CASE_ID not in wire


def test_the_wire_model_is_exactly_three_fields_and_ignores_extras():
    m = s.StepEvent(step="searching", found=3, kept=1, case=CASE_TITLE)  # type: ignore[call-arg]
    assert set(m.model_dump()) == {"step", "found", "kept"}
    with pytest.raises(Exception):  # noqa: B017, PT011
        s.StepEvent(step=CASE_TITLE)  # type: ignore[arg-type]
    with pytest.raises(Exception):  # noqa: B017, PT011
        s.StepEvent(step="searching", found=CASE_ID)  # type: ignore[arg-type]
