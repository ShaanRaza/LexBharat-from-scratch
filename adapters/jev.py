"""Jev adapter: every fixed-choice decision in the pipeline, with a Gemini fallback.

Rule 1: the ONLY file that talks to Jev (TypeSafe AI). Jev never writes prose; it picks
one option from a fixed list. Gemini writes all prose (adapters/gemini.py).

Pipeline steps that use it:
  3 Decide  -> scope, safety, (filters / knowledge notes later)
  7 Gate    -> relevance of each passage: answers / partly / not_relevant
  9 Verify  -> claim_support (check 4): supports / partly / does_not_support

FALLBACK PATH (docs/ARCHITECTURE.md "Safeguards"). `DecisionAdapter` uses Gemini with
the SAME fixed choices when:
  - the per-use switch in settings is off (JEV_ENABLED_SCOPE, _GATE, _CLAIM, _SAFETY),
  - Jev raises an error,
  - Jev is slower than JEV_TIMEOUT_MS (800 ms),
  - the text involved is upload text. Upload text NEVER goes to Jev (CLAUDE.md s.6).
If the fallback fails too, `DecisionUnavailable` is raised and the caller decides what
is safe (the verifier marks the citation "unchecked", never "verified").

Only interfaces and Fakes here; no real network calls and no real Jev client yet.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from adapters.gemini import LLMClient
from core.settings import Settings

# --- The fixed choice lists (copied from docs/ARCHITECTURE.md "Decision layer") ---
SCOPE_CHOICES = (
    "in_scope",
    "needs_high_court",
    "needs_tribunal",
    "after_snapshot",
    "not_legal",
)
SAFETY_CHOICES = ("normal", "personal_advice", "trick")
RELEVANCE_CHOICES = ("answers", "partly", "not_relevant")
SUPPORT_CHOICES = ("supports", "partly", "does_not_support")

Scope = Literal[
    "in_scope", "needs_high_court", "needs_tribunal", "after_snapshot", "not_legal"
]
Safety = Literal["normal", "personal_advice", "trick"]
Relevance = Literal["answers", "partly", "not_relevant"]
Support = Literal["supports", "partly", "does_not_support"]


class DecisionUnavailable(Exception):
    """Neither Jev nor the Gemini fallback could make the decision."""


@dataclass(frozen=True)
class Decision:
    """One decision: the chosen option, how sure it is (0-1), and who made it."""

    choice: str
    confidence: float
    source: Literal["jev", "fallback"]


class DecisionBackend(Protocol):
    """Anything that can make the four decisions. Jev and the fallback both fit."""

    async def scope(self, query: str) -> tuple[str, float]: ...
    async def safety(self, query: str) -> tuple[str, float]: ...
    async def relevance(self, query: str, passage: str) -> tuple[str, float]: ...
    async def claim_support(self, sentence: str, passage: str) -> tuple[str, float]: ...


# --------------------------------------------------------------------------
# The fallback: Gemini answering the same fixed choices
# --------------------------------------------------------------------------

_REPLY = re.compile(r"^\s*([a-z_]+)\s+([01](?:\.\d+)?)\s*$")


class GeminiDecisionBackend:
    """Makes the same decisions as Jev with a plain model call.

    The model must reply "<choice> <confidence 0-1>", for example "supports 0.8".
    Anything else raises ValueError, so a garbled reply is never mistaken for a decision.
    """

    def __init__(self, llm: LLMClient, model: str) -> None:
        self.llm = llm
        self.model = model

    async def _choose(
        self, question: str, choices: tuple[str, ...]
    ) -> tuple[str, float]:
        prompt = (
            f"{question}\nReply with exactly: <choice> <confidence between 0 and 1>.\n"
            f"Allowed choices: {', '.join(choices)}."
        )
        result = await self.llm.complete(
            system="You make one fixed-choice decision. Never write anything else.",
            prompt=prompt,
            model=self.model,
        )
        match = _REPLY.match(result.text.lower())
        if not match or match.group(1) not in choices:
            raise ValueError(f"unusable decision reply: {result.text!r}")
        return match.group(1), min(1.0, float(match.group(2)))

    async def scope(self, query: str) -> tuple[str, float]:
        return await self._choose(f"Scope of this question: {query}", SCOPE_CHOICES)

    async def safety(self, query: str) -> tuple[str, float]:
        return await self._choose(f"Kind of request: {query}", SAFETY_CHOICES)

    async def relevance(self, query: str, passage: str) -> tuple[str, float]:
        q = f"Question: {query}\nPassage: {passage}\nDoes the passage help answer it?"
        return await self._choose(q, RELEVANCE_CHOICES)

    async def claim_support(self, sentence: str, passage: str) -> tuple[str, float]:
        q = f"Sentence: {sentence}\nPassage: {passage}\nDoes the passage support it?"
        return await self._choose(q, SUPPORT_CHOICES)


# --------------------------------------------------------------------------
# The adapter the rest of the code uses
# --------------------------------------------------------------------------


class DecisionAdapter:
    """Front door for every decision. Handles switches, timeout, fallback, privacy."""

    def __init__(
        self, primary: DecisionBackend, fallback: DecisionBackend, settings: Settings
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.settings = settings

    async def _decide(
        self,
        method: str,
        enabled: bool,
        args: tuple[str, ...],
        contains_upload_text: bool,
    ) -> Decision:
        # Upload text and switched-off decisions never touch Jev.
        if enabled and not contains_upload_text:
            try:
                choice, conf = await asyncio.wait_for(
                    getattr(self.primary, method)(*args),
                    timeout=self.settings.JEV_TIMEOUT_MS / 1000,
                )
            except Exception:  # noqa: BLE001, S110 - timeout/outage/bad reply: fall back
                pass
            else:
                return Decision(choice, conf, "jev")
        try:
            choice, conf = await getattr(self.fallback, method)(*args)
        except Exception as exc:
            raise DecisionUnavailable(
                f"{method}: jev and fallback both failed"
            ) from exc
        return Decision(choice, conf, "fallback")

    async def scope(
        self, query: str, *, contains_upload_text: bool = False
    ) -> Decision:
        s = self.settings
        return await self._decide(
            "scope", s.JEV_ENABLED_SCOPE, (query,), contains_upload_text
        )

    async def safety(
        self, query: str, *, contains_upload_text: bool = False
    ) -> Decision:
        s = self.settings
        return await self._decide(
            "safety", s.JEV_ENABLED_SAFETY, (query,), contains_upload_text
        )

    async def relevance(
        self, query: str, passage: str, *, contains_upload_text: bool = False
    ) -> Decision:
        s = self.settings
        return await self._decide(
            "relevance", s.JEV_ENABLED_GATE, (query, passage), contains_upload_text
        )

    async def claim_support(
        self, sentence: str, passage: str, *, contains_upload_text: bool = False
    ) -> Decision:
        s = self.settings
        return await self._decide(
            "claim_support",
            s.JEV_ENABLED_CLAIM,
            (sentence, passage),
            contains_upload_text,
        )


# --------------------------------------------------------------------------
# Fakes for tests
# --------------------------------------------------------------------------

_WORD = re.compile(r"\w+", re.UNICODE)


def _overlap(a: str, b: str) -> float:
    """Share of a's words that also appear in b (a crude stand-in for meaning)."""
    wa = {w.casefold() for w in _WORD.findall(a) if len(w) > 3}
    wb = {w.casefold() for w in _WORD.findall(b)}
    return len(wa & wb) / len(wa) if wa else 0.0


class FakeDecisionBackend:
    """Deterministic fake. Works as the "Jev" side or the fallback side in tests.

    Defaults use word overlap, so tests need no setup. Override any decision with
    `scope_fn`, `safety_fn`, `relevance_fn`, `claim_fn` (each returns (choice, conf)).
    `down=True` raises, `delay_s` sleeps (to test the 800 ms timeout).
    Every call is logged in `.calls` as (method, args).
    """

    def __init__(
        self,
        *,
        down: bool = False,
        delay_s: float = 0.0,
        scope_fn: Callable[[str], tuple[str, float]] | None = None,
        safety_fn: Callable[[str], tuple[str, float]] | None = None,
        relevance_fn: Callable[[str, str], tuple[str, float]] | None = None,
        claim_fn: Callable[[str, str], tuple[str, float]] | None = None,
    ) -> None:
        self.down = down
        self.delay_s = delay_s
        self.scope_fn = scope_fn
        self.safety_fn = safety_fn
        self.relevance_fn = relevance_fn
        self.claim_fn = claim_fn
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def _enter(self, method: str, args: tuple[str, ...]) -> None:
        self.calls.append((method, args))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.down:
            raise RuntimeError("fake decision backend is down")

    async def scope(self, query: str) -> tuple[str, float]:
        await self._enter("scope", (query,))
        if self.scope_fn:
            return self.scope_fn(query)
        q = query.casefold()
        if "high court" in q:
            return "needs_high_court", 0.95
        if "tribunal" in q:
            return "needs_tribunal", 0.95
        if "2027" in q or "2028" in q:
            return "after_snapshot", 0.95
        return "in_scope", 0.95

    async def safety(self, query: str) -> tuple[str, float]:
        await self._enter("safety", (query,))
        if self.safety_fn:
            return self.safety_fn(query)
        q = query.casefold()
        if "ignore previous" in q:
            return "trick", 0.95
        if " my " in f" {q} " and "should i" in q:
            return "personal_advice", 0.9
        return "normal", 0.95

    async def relevance(self, query: str, passage: str) -> tuple[str, float]:
        await self._enter("relevance", (query, passage))
        if self.relevance_fn:
            return self.relevance_fn(query, passage)
        score = _overlap(query, passage)
        if score >= 0.5:
            return "answers", max(score, 0.7)
        if score >= 0.25:
            return "partly", max(score, 0.6)
        return "not_relevant", 0.9

    async def claim_support(self, sentence: str, passage: str) -> tuple[str, float]:
        await self._enter("claim_support", (sentence, passage))
        if self.claim_fn:
            return self.claim_fn(sentence, passage)
        score = _overlap(sentence, passage)
        if score >= 0.5:
            return "supports", 0.9
        if score >= 0.25:
            return "partly", 0.7
        return "does_not_support", 0.9
