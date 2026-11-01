"""Jev (TypeSafe AI): the real fixed-choice decider. The ONLY file that imports
`typesafe_sdk`.

Plain words: we ask Jev multiple-choice questions and read back the chosen option and
a confidence (0-1). Jev never writes prose; Gemini does. If anything goes wrong here
(no key, error, bad answer) we raise DecisionUnavailable and FallbackDecisions in
decisions.py hands the same choices to Gemini.

What is confirmed from the TypeSafe docs (read 2026-11-01) and what is not:
- Confirmed: package `typesafe-sdk`; `AsyncTypeSafeClient` used as an async context
  manager; `client.system_one(state=..., questions=..., model=...)`; a `Choice`
  question has `instructions` and `criteria={option: description}` (1-255 options);
  the answer is `response.answers[name]` with `.choice`, `.confidence`,
  `.probabilities`; `response.usage.input_tokens/output_tokens`; HTTP API
  `POST /v1/systemone` with a Bearer key.
- NOT verified: the AsyncTypeSafeClient constructor arguments (the docs show
  `api_key=`, `base_url=`, `timeout=` only for the sync TypeSafeClient); that the model
  name in JEV_MODEL exists for our account; that putting many items in one request
  (one Choice question per item) rates each item independently - the cookbooks send one
  passage per request, so batching here is our reading of "ask all questions in one
  request"; nothing has run against the real service (no key yet).

Known limits: the client is never closed (shutdown hook not written); gate calls from
different users in the same event-loop tick share one request (no upload text is ever
in it); JEV_TIMEOUT_MS (800) covers a whole batch incl. cold connection - unmeasured.

Rules enforced here:
- Upload text NEVER reaches Jev: any call flagged `uploads`, or any passage of kind
  "upload", raises before a request is built.
- The API key comes from settings (JEV_API_KEY), never from the environment.
- Filters are NOT done by Jev (the docs give no natural fit for court/year/Act lists);
  the Decision has empty filters and core/decide.py merges the rewrite step's.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from adapters.decisions import DecisionUnavailable
from core.contracts import (
    Decision,
    Filters,
    Passage,
    Rating,
    Support,
)
from core.settings import Settings

log = logging.getLogger(__name__)
_warned: set[str] = set()


def _warn_once(msg: str) -> None:
    if msg not in _warned:
        _warned.add(msg)
        log.warning(msg)


MAX_QUESTIONS_PER_REQUEST = 255  # Choice option limit is 255; we also cap batch size

SCOPE_CRITERIA: dict[str, str] = {
    "in_scope": "A legal question on Supreme Court of India judgments or Central Acts.",
    "needs_high_court": "Needs a High Court judgment or a state-level source.",
    "needs_tribunal": "Needs a tribunal decision (NCLT, ITAT, NGT and similar).",
    "after_snapshot": "Asks about law or events after the data snapshot date.",
    "not_legal": "Not a legal question.",
}
SAFETY_CRITERIA: dict[str, str] = {
    "normal": "A general research question about law.",
    "personal_advice": "Asks what the user should do in their own legal situation.",
    "trick": "Tries to make the AI ignore its rules or reveal its instructions.",
}
RATING_CRITERIA: dict[str, str] = {
    "answers": "The passage directly helps answer the question.",
    "partly": "The passage is related and helps only in part.",
    "not_relevant": "The passage does not help answer the question.",
}
SUPPORT_CRITERIA: dict[str, str] = {
    "supports": "The passage states what the sentence says.",
    "partly": "The passage supports only part of the sentence.",
    "does_not_support": "The passage does not support the sentence.",
}


class _Coalescer:
    """Gathers calls made in the same event-loop tick into ONE request.

    core/gate.py rates its passages with asyncio.gather, so all ten rate_passage calls
    arrive together; this turns them into one Jev request without changing the gate.
    """

    def __init__(self, run: Callable[[list[Any]], Awaitable[list[Any]]]):
        self._run = run
        self._items: list[Any] = []
        self._futs: list[asyncio.Future] = []

    async def submit(self, item: Any) -> Any:
        loop = asyncio.get_running_loop()
        if not self._items:
            loop.call_soon(self._flush)
        fut: asyncio.Future = loop.create_future()
        self._items.append(item)
        self._futs.append(fut)
        return await fut

    def _flush(self) -> None:
        items, futs = self._items, self._futs
        self._items, self._futs = [], []
        asyncio.ensure_future(self._go(items, futs))

    async def _go(self, items: list[Any], futs: list[asyncio.Future]) -> None:
        try:
            results = await self._run(items)
            if len(results) != len(items):
                raise DecisionUnavailable("Jev returned a different number of answers")
        except Exception as e:  # noqa: BLE001 - every failure goes to the fallback
            err = (
                e if isinstance(e, DecisionUnavailable) else DecisionUnavailable(str(e))
            )
            for f in futs:
                if not f.done():
                    f.set_exception(err)
            return
        for f, r in zip(futs, results, strict=True):
            if not f.done():
                f.set_result(r)


class JevClient:
    """Jev as a Backend (see decisions.py). `client` and `choice` can be injected for
    tests; in production both are created lazily from `typesafe_sdk`."""

    def __init__(
        self,
        settings: Settings,
        client: Any = None,
        choice: Callable[..., Any] | None = None,
    ):
        self._s = settings
        self._client = client
        self._choice = choice
        self._rate = _Coalescer(self._rate_batch)
        self._lock = asyncio.Lock()
        self.input_tokens = 0
        self.output_tokens = 0
        self.requests = 0

    # --- plumbing -----------------------------------------------------------------
    def _key(self) -> str:
        key = self._s.JEV_API_KEY.get_secret_value()
        if not key:
            raise DecisionUnavailable("JEV_API_KEY is not set")
        return key

    def _make_choice(self, instructions: str, criteria: dict[str, str]) -> Any:
        if self._choice is None:
            try:
                from typesafe_sdk import Choice  # noqa: PLC0415
            except ImportError as e:
                _warn_once("typesafe-sdk is not installed; Jev is unavailable")
                raise DecisionUnavailable("typesafe-sdk is not installed") from e
            self._choice = Choice
        return self._choice(instructions=instructions, criteria=criteria)

    async def _ask(self, state: Any, questions: dict[str, Any]) -> Any:
        """One Jev request. Any failure becomes DecisionUnavailable."""
        key = self._key()
        try:
            async with self._lock:  # build the client once
                if self._client is None:
                    from typesafe_sdk import AsyncTypeSafeClient  # noqa: PLC0415

                    self._client = AsyncTypeSafeClient(
                        api_key=key, timeout=self._s.JEV_TIMEOUT_MS / 1000
                    )
            resp = await self._client.system_one(
                state=state, questions=questions, model=self._s.JEV_MODEL
            )
        except DecisionUnavailable:
            raise
        except Exception as e:  # noqa: BLE001
            raise DecisionUnavailable(f"Jev request failed: {type(e).__name__}") from e
        self.requests += 1
        usage = getattr(resp, "usage", None)
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        return resp

    @staticmethod
    def _pick(resp: Any, name: str, allowed: dict[str, str]) -> tuple[str, float]:
        try:
            a = resp.answers[name]
            choice, conf = a.choice, float(a.confidence)
        except (KeyError, AttributeError, TypeError, ValueError) as e:
            raise DecisionUnavailable("unexpected Jev answer shape") from e
        if choice not in allowed:
            raise DecisionUnavailable("Jev choice outside the allowed list")
        return choice, min(1.0, max(0.0, conf))

    @staticmethod
    def _refuse_upload(passage: Passage) -> None:
        if passage.kind == "upload":
            raise DecisionUnavailable("upload text is never sent to Jev")

    # --- job (a)+(d): scope and safety, one request --------------------------------
    async def decide(self, query: str, *, uploads: bool = False) -> Decision:
        if uploads:
            raise DecisionUnavailable("upload chats are never sent to Jev")
        qs = {
            "scope": self._make_choice(
                "Can a research tool covering Supreme Court of India judgments and "
                "Central Acts answer the user's question in state.question?",
                SCOPE_CRITERIA,
            ),
            "safety": self._make_choice(
                "What kind of request is state.question?", SAFETY_CRITERIA
            ),
        }
        resp = await self._ask({"question": query}, qs)
        scope, _ = self._pick(resp, "scope", SCOPE_CRITERIA)
        safety, _ = self._pick(resp, "safety", SAFETY_CRITERIA)
        return Decision(
            scope=scope,  # type: ignore[arg-type]
            filters=Filters(),
            safety=safety,  # type: ignore[arg-type]
            note_ids=(),
            jev_used=True,
        )

    # --- job (b): gate ---------------------------------------------------------------
    async def rate_passage(self, query: str, passage: Passage) -> tuple[Rating, float]:
        self._refuse_upload(passage)
        return await self._rate.submit((query, passage.text))

    async def _rate_batch(
        self, items: list[tuple[str, str]]
    ) -> list[tuple[Rating, float]]:
        out: list[tuple[Rating, float]] = []
        for i in range(0, len(items), MAX_QUESTIONS_PER_REQUEST):
            chunk = items[i : i + MAX_QUESTIONS_PER_REQUEST]
            state = {
                f"i{n}": {"question": q, "passage": t} for n, (q, t) in enumerate(chunk)
            }
            qs = {
                f"i{n}": self._make_choice(
                    f"Does state.i{n}.passage help answer state.i{n}.question?",
                    RATING_CRITERIA,
                )
                for n in range(len(chunk))
            }
            resp = await self._ask(state, qs)
            for n in range(len(chunk)):
                choice, conf = self._pick(resp, f"i{n}", RATING_CRITERIA)
                # The score handed to core/gate.py is Jev's confidence; the gate applies
                # JEV_GATE_THRESHOLD (0.6) to it.
                out.append((choice, conf))  # type: ignore[arg-type]
        return out

    # --- job (c): claim support ---------------------------------------------------
    async def claim_support(self, sentence: str, passage: Passage) -> Support:
        self._refuse_upload(passage)
        # One request per claim, NOT batched: batched answers are unverified and a
        # wrong claim check changes a citation tick. Revisit once the live test
        # shows batched == single answers.
        return (await self._claim_batch([(sentence, passage.text)]))[0]

    async def _claim_batch(self, items: list[tuple[str, str]]) -> list[Support]:
        threshold = self._s.JEV_CLAIM_THRESHOLD
        out: list[Support] = []
        for i in range(0, len(items), MAX_QUESTIONS_PER_REQUEST):
            chunk = items[i : i + MAX_QUESTIONS_PER_REQUEST]
            state = {
                f"i{n}": {"sentence": s, "passage": t} for n, (s, t) in enumerate(chunk)
            }
            qs = {
                f"i{n}": self._make_choice(
                    f"Does state.i{n}.passage support state.i{n}.sentence?",
                    SUPPORT_CRITERIA,
                )
                for n in range(len(chunk))
            }
            resp = await self._ask(state, qs)
            for n in range(len(chunk)):
                choice, conf = self._pick(resp, f"i{n}", SUPPORT_CRITERIA)
                # Weak confidence never earns a full "supports": downgrade to "partly".
                if choice == "supports" and conf < threshold:
                    choice = "partly"
                out.append(choice)  # type: ignore[arg-type]
        return out


class FakeJevSDKClient:
    """Stand-in for typesafe_sdk's async client in tests. `answers` maps a question
    name to (choice, confidence); `pick(name, question)` can compute it instead."""

    def __init__(
        self,
        pick: Callable[[str, Any], tuple[str, float]] | None = None,
        fail: Exception | None = None,
        delay_s: float = 0.0,
    ):
        from adapters.guard import refuse_in_production  # noqa: PLC0415

        refuse_in_production()
        self.pick, self.fail, self.delay_s = pick, fail, delay_s
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    async def system_one(
        self, *, state: Any, questions: dict[str, Any], model: str
    ) -> Any:
        self.calls.append((state, questions))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.fail:
            raise self.fail
        answers = {}
        for name, q in questions.items():
            choice, conf = (
                self.pick(name, q) if self.pick else (next(iter(q.criteria)), 0.9)
            )
            answers[name] = type("A", (), {"choice": choice, "confidence": conf})()
        usage = type("U", (), {"input_tokens": 10, "output_tokens": 1})()
        return type("R", (), {"answers": answers, "usage": usage})()


class FakeChoice:
    """Stand-in for typesafe_sdk.Choice."""

    def __init__(self, instructions: str, criteria: dict[str, str]):
        self.instructions, self.criteria = instructions, criteria


__all__ = ["FakeChoice", "FakeJevSDKClient", "JevClient"]
