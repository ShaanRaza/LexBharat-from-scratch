"""Bridge from the API to core's pipeline (pipeline steps 1-11, entry point only).

Plain words: the route hands us a question; we build core's PipelineRequest, call
`run_pipeline`, then turn core's stream events into the wire events in schemas.py.
No pipeline logic lives here. The order we guarantee on the wire is:

    token*  ->  citations (exactly once)  ->  done        (answered)
    done(refused=True, message_key=...)                     (out of scope / not found)
    error                                                   (limit reached / failure)

Nothing citation-shaped is emitted before the single citations event (step 10).

FAKE MODE (api/config.py FAKE_PIPELINE) swaps in `FakePipeline` below. It cannot be on
in production: ApiSettings refuses to load, and `assert_fake_allowed` checks again.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from types import SimpleNamespace

from api import schemas as s
from api.repo import _last_message
from core.contracts import (
    AnswerProvenance,
    FinalEvent,
    Footer,
    OnStep,
    PipelineRequest,
    PipelineResult,
    StepEvent,
    StreamEvent,
    TextDelta,
    Turn,
)
from core.contracts import (
    Citation as CoreCitation,
)

log = logging.getLogger("api.bridge")

Runner = Callable[[PipelineRequest, OnStep], Awaitable[PipelineResult]]
Streamer = Callable[[PipelineResult], AsyncIterator[StreamEvent]]


def assert_fake_allowed(app_env: str) -> None:
    if app_env not in ("development", "test"):
        raise RuntimeError("fake pipeline refused: APP_ENV must be development or test")


def to_wire_citation(c: CoreCitation) -> s.Citation:
    return s.Citation(
        source_id=c.source_id,
        kind=c.kind,
        anchor=c.anchor,
        act_slug=c.act_slug,
        section=c.section,
        record_id=c.record_id,
        # Judgment titles are "X v. Y" party names: never sent (CLAUDE.md section 6).
        title=c.title if c.kind == "act" else None,
        citation_string=c.citation_string,  # exactly as stored, never retyped
        url=c.pdf_url or c.source_url,
        status=c.status,
    )


def build_request(
    user_id: str,
    plan: str,
    conversation_id: str,
    message: str,
    turns: list[tuple[str, str]],
    summary: str,
    document_ids: tuple[str, ...] = (),
) -> PipelineRequest:
    return PipelineRequest(
        user_id=user_id,
        message=message,
        conversation_id=conversation_id,
        history=tuple(Turn(role=r, text=t) for r, t in turns),  # type: ignore[arg-type]
        summary=summary,
        plan=plan,  # type: ignore[arg-type]
        document_ids=document_ids,
    )


async def stream_answer(
    request: PipelineRequest,
    runner: Runner,
    streamer: Streamer,
    data_as_of: str,
    credit: str,
    request_id: str,
) -> AsyncIterator[tuple[str, dict]]:
    """Yield (event_name, json_data) pairs. Never raises: failures become `error`.

    Order: `step` events while the pipeline runs (names and counts only), then, only
    after the pipeline (including the verifier) has finished, token*, citations, done.
    One channel: step events cannot arrive after the citations event."""
    holder: dict = {}
    _last_message.set(holder)  # the store (step 11) writes the saved message id here
    steps: asyncio.Queue[StepEvent] = asyncio.Queue()
    task = asyncio.ensure_future(runner(request, steps.put_nowait))
    try:
        while True:
            getter = asyncio.ensure_future(steps.get())
            await asyncio.wait({task, getter}, return_when=asyncio.FIRST_COMPLETED)
            if getter.done():
                yield "step", _step_wire(getter.result())
                continue
            getter.cancel()
            break
        while not steps.empty():  # events queued just before the pipeline finished
            yield "step", _step_wire(steps.get_nowait())
        result = task.result()
    except Exception:  # never echo exception text: it can hold document text
        log.exception("pipeline failed request_id=%s", request_id)
        yield _error(
            "service_unavailable", "We could not answer right now.", request_id
        )
        return
    finally:
        if not task.done():  # client went away: stop the work
            task.cancel()

    if result.outcome == "usage_limit":
        yield _error("quota_exceeded", "You have reached your limit.", request_id)
        return
    if result.outcome == "error":
        yield _error("internal_error", "We could not answer right now.", request_id)
        return
    if result.outcome != "answered":
        done = s.DoneEvent(
            refused=True,
            reason=result.outcome,  # type: ignore[arg-type]
            message_key=result.message_key or result.outcome,
        )
        yield "done", done.model_dump(mode="json")
        return

    try:
        async for ev in streamer(result):
            if isinstance(ev, TextDelta):
                yield "token", s.TokenEvent(text=ev.text).model_dump(mode="json")
            elif isinstance(ev, FinalEvent):
                footer: Footer = ev.footer
                cit = s.CitationsEvent(
                    citations=[to_wire_citation(c) for c in ev.citations],
                    removed_count=len(result.removed),
                    data_as_of=footer.data_as_of or data_as_of,
                    credit=footer.credit or credit,
                )
                yield "citations", cit.model_dump(mode="json")
    except Exception:
        log.exception("streaming failed request_id=%s", request_id)
        yield _error("internal_error", "The answer was interrupted.", request_id)
        return
    done = s.DoneEvent(message_id=holder.get("id"), from_cache=result.cache_hit)
    yield "done", done.model_dump(mode="json")


def _step_wire(ev: StepEvent) -> dict:
    return s.StepEvent(step=ev.step, found=ev.found, kept=ev.kept).model_dump(
        mode="json"
    )


def _error(code: str, message: str, request_id: str) -> tuple[str, dict]:
    return "error", s.ErrorEvent(
        code=code, message=message, request_id=request_id
    ).model_dump()  # type: ignore[arg-type]


# --------------------------------------------------------------------- FAKE MODE
@dataclass(frozen=True)
class FakeResult:
    """Looks like PipelineResult to the bridge but is NOT one: core's answers carry a
    seal only the real verifier can make, and fake mode must never forge it."""

    outcome: str
    footer: Footer
    answer_text: str = ""
    citations: tuple[CoreCitation, ...] = ()
    message_key: str = ""
    cache_hit: bool = False
    removed: tuple = ()
    model: str = "fake"


class FakePipeline:
    """Canned answer with one citation. NEVER used in production (see module doc).

    A question containing "outofscope" is refused; "boom" raises; "limit" hits quota.
    """

    def __init__(self, repo=None, footer: Footer | None = None):
        self.repo = repo
        self.footer = footer or Footer(
            data_as_of="2026-08-31", snapshot_version="v2026.08"
        )

    async def run(
        self, request: PipelineRequest, on_step: OnStep | None = None
    ) -> FakeResult:
        if on_step is not None:
            on_step(StepEvent("understanding"))
        if "boom" in request.message:
            raise RuntimeError("fake failure")
        if "limit" in request.message:
            return FakeResult("usage_limit", self.footer)
        if "outofscope" in request.message:
            return FakeResult(
                "out_of_scope", self.footer, message_key="out_of_scope:fake"
            )
        if on_step is not None:  # the rest of the steps, like the real pipeline
            for ev in (
                StepEvent("searching"),
                StepEvent("checking", found=23),
                StepEvent("writing", found=23, kept=8),
                StepEvent("verifying"),
            ):
                on_step(ev)
        cit = CoreCitation(
            source_id="S1", record_id="fake-record-1", status="verified",
            citation_string="(fake) 1 SCC 1", pdf_url="https://example.invalid/fake.pdf",
            source_url=None, title="Fake v. Fake", kind="judgment", anchor="p3",
        )  # fmt: skip
        result = FakeResult(
            "answered", self.footer,
            "FAKE ANSWER. A fake point [S1]. Not real law.", (cit,),
        )  # fmt: skip
        if self.repo is not None:
            await self.repo.save(request, SimpleNamespace(
                outcome="answered", cache_hit=False,
                answer=SimpleNamespace(text=result.answer_text, citations=()),
                model="fake", input_tokens=0, output_tokens=0,
                provenance=AnswerProvenance(),
            ))  # fmt: skip
        return result

    async def stream(self, result: FakeResult) -> AsyncIterator[StreamEvent]:
        for word in result.answer_text.split(" "):
            yield TextDelta(word + " ")
        yield FinalEvent("answered", result.citations, result.footer)
