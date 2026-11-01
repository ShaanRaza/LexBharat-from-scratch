"""Decision layer: Jev, with a Gemini fallback that offers the SAME fixed choices.

Plain words: Jev answers multiple-choice questions (is this in scope? does this passage
help? does it support this sentence?). Gemini writes the prose elsewhere. If Jev is
off, down, errors, or takes longer than JEV_TIMEOUT_MS (800 ms), Gemini decides with the
same choices. If Gemini also fails, DecisionUnavailable is raised and the caller copes
(CLAUDE.md section 5: checks 1-3 of the verifier never depend on this).

Hard rule: UPLOAD text never goes to Jev. Passages of kind "upload" always go to Gemini.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Protocol, cast, get_args

from adapters.guard import refuse_in_production
from adapters.llm import LLM, LLMUnavailable
from core.contracts import (
    Decision,
    Filters,
    Passage,
    Rating,
    SafetyClass,
    ScopeClass,
    Support,
)
from core.settings import Settings

log = logging.getLogger(__name__)
_PROMPTS = Path(__file__).resolve().parent.parent / "core" / "prompts"


class DecisionUnavailable(Exception):
    """No decider could answer in time. Callers must degrade honestly."""


class DecisionService(Protocol):
    async def decide(self, query: str, *, uploads: bool = False) -> Decision: ...
    async def rate_passage(
        self, query: str, passage: Passage
    ) -> tuple[Rating, float]: ...
    async def claim_support(self, sentence: str, passage: Passage) -> Support: ...


class Backend(Protocol):
    """One decider (Jev or Gemini). Raises DecisionUnavailable on any failure."""

    async def decide(self, query: str, *, uploads: bool = False) -> Decision: ...
    async def rate_passage(
        self, query: str, passage: Passage
    ) -> tuple[Rating, float]: ...
    async def claim_support(self, sentence: str, passage: Passage) -> Support: ...


def _prompt(name: str, **kw: str) -> str:
    return (_PROMPTS / f"{name}.txt").read_text().format(**kw)


class JevClient:
    """Real Jev (TypeSafe AI, early access). The API is not documented in this repo,
    so this raises until wired; the fallback then decides. Not verified."""

    def __init__(self, settings: Settings):
        self._s = settings

    async def decide(self, query: str, *, uploads: bool = False) -> Decision:
        raise DecisionUnavailable("Jev client not wired yet")

    async def rate_passage(self, query: str, passage: Passage) -> tuple[Rating, float]:
        raise DecisionUnavailable("Jev client not wired yet")

    async def claim_support(self, sentence: str, passage: Passage) -> Support:
        raise DecisionUnavailable("Jev client not wired yet")


class GeminiDecider:
    """Fixed-choice decisions through the LLM adapter. Strict parsing: anything outside
    the allowed choices is an error, never a guess."""

    def __init__(self, llm: LLM, settings: Settings):
        self._llm, self._s = llm, settings

    async def _ask(self, prompt: str) -> str:
        try:
            r = await self._llm.complete(
                prompt, model=self._s.MODEL_REWRITE, max_tokens=200
            )
        except LLMUnavailable as e:
            raise DecisionUnavailable(str(e)) from e
        return r.text.strip()

    def _json(self, text: str) -> dict:
        try:
            d = json.loads(text)
            if not isinstance(d, dict):
                raise ValueError("not an object")
            return d
        except ValueError as e:
            raise DecisionUnavailable("unparseable decision") from e

    async def decide(self, query: str, *, uploads: bool = False) -> Decision:
        d = self._json(await self._ask(_prompt("decide", query=query)))
        scope, safety = d.get("scope"), d.get("safety")
        if scope not in get_args(ScopeClass) or safety not in get_args(SafetyClass):
            raise DecisionUnavailable("choice outside allowed list")
        f = Filters(
            court=d.get("court"),
            year_from=d.get("year_from"),
            year_to=d.get("year_to"),
            act=d.get("act"),
            section=d.get("section"),
        )
        return Decision(
            cast(ScopeClass, scope), f, cast(SafetyClass, safety), (), False
        )

    async def rate_passage(self, query: str, passage: Passage) -> tuple[Rating, float]:
        d = self._json(
            await self._ask(_prompt("rate_passage", query=query, passage=passage.text))
        )
        rating, score = d.get("rating"), d.get("score")
        if rating not in get_args(Rating) or not isinstance(score, int | float):
            raise DecisionUnavailable("choice outside allowed list")
        return cast(Rating, rating), min(1.0, max(0.0, float(score)))

    async def claim_support(self, sentence: str, passage: Passage) -> Support:
        out = await self._ask(
            _prompt("claim_support", sentence=sentence, passage=passage.text)
        )
        if out not in get_args(Support):
            raise DecisionUnavailable("choice outside allowed list")
        return cast(Support, out)


class FallbackDecisions:
    """The adapter the rest of the code uses: Jev first, Gemini if Jev is off, fails,
    or is slower than JEV_TIMEOUT_MS."""

    def __init__(self, jev: Backend, fallback: Backend, settings: Settings):
        self._jev, self._fb, self._s = jev, fallback, settings

    async def _run(self, switch: bool, uploads: bool, call):
        if switch and not uploads:  # upload text NEVER reaches Jev
            try:
                return await asyncio.wait_for(
                    call(self._jev), self._s.JEV_TIMEOUT_MS / 1000
                )
            except Exception:  # noqa: BLE001
                log.warning("Jev failed or timed out; using Gemini fallback")
        return await call(self._fb)

    async def decide(self, query: str, *, uploads: bool = False) -> Decision:
        s = self._s
        on = s.JEV_ENABLED_SCOPE and s.JEV_ENABLED_FILTERS and s.JEV_ENABLED_SAFETY
        return await self._run(on, uploads, lambda b: b.decide(query, uploads=uploads))

    async def rate_passage(self, query: str, passage: Passage) -> tuple[Rating, float]:
        return await self._run(
            self._s.JEV_ENABLED_GATE,
            passage.kind == "upload",
            lambda b: b.rate_passage(query, passage),
        )

    async def claim_support(self, sentence: str, passage: Passage) -> Support:
        return await self._run(
            self._s.JEV_ENABLED_CLAIM,
            passage.kind == "upload",
            lambda b: b.claim_support(sentence, passage),
        )


class FakeDecisions:
    """In-memory decider for tests. `down=True` makes every call raise
    DecisionUnavailable. Rules: a passage 'answers' when it shares words with the query;
    a sentence is 'supported' when it shares words with the passage."""

    def __init__(
        self,
        down: bool = False,
        scope: ScopeClass = "in_scope",
        safety: SafetyClass = "normal",
        delay_s: float = 0.0,
    ):
        refuse_in_production()
        self.down, self.scope, self.safety, self.delay_s = down, scope, safety, delay_s
        self.seen_kinds: list[str] = []

    async def _gate(self) -> None:
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.down:
            raise DecisionUnavailable("fake down")

    async def decide(self, query: str, *, uploads: bool = False) -> Decision:
        await self._gate()
        return Decision(self.scope, Filters(), self.safety, (), True)

    async def rate_passage(self, query: str, passage: Passage) -> tuple[Rating, float]:
        await self._gate()
        self.seen_kinds.append(passage.kind)
        from adapters.voyage import words

        q, p = set(words(query)), set(words(passage.text))
        score = len(q & p) / (len(q) or 1)
        rating: Rating = (
            "answers" if score >= 0.5 else "partly" if score > 0 else "not_relevant"
        )
        return rating, score

    async def claim_support(self, sentence: str, passage: Passage) -> Support:
        await self._gate()
        self.seen_kinds.append(passage.kind)
        from adapters.voyage import words

        s, p = set(words(sentence)), set(words(passage.text))
        r = len(s & p) / (len(s) or 1)
        return "supports" if r >= 0.6 else "partly" if r >= 0.3 else "does_not_support"
