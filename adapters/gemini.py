"""Gemini adapter (via the LiteLLM gateway): writes prose and makes fallback decisions.

Rule 1: the ONLY file that talks to the AI model gateway. Model names come from
core/settings.py (MODEL_FREE, MODEL_REWRITE ...), never from code.

Pipeline steps that use it: 1 (summary), 2 (rewrite), 8 (answer). It is also the
fallback for the Jev decisions (see adapters/jev.py). Upload chats use it for ALL
decisions, because upload text must never reach Jev (CLAUDE.md section 6).

Only the interface and a Fake live here; no real network calls.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class LLMUnavailable(Exception):
    """Raised when the model provider fails or times out."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    model: str


class LLMClient(Protocol):
    async def complete(self, *, system: str, prompt: str, model: str) -> LLMResult: ...


class FakeLLM:
    """Scripted model for tests.

    Give it a `responder(system, prompt, model) -> str`, or a fixed `reply`.
    Every call is recorded in `.calls` so tests can check what the model was shown.
    Set `down=True` to simulate a provider outage.
    """

    def __init__(
        self,
        reply: str = "",
        responder: Callable[[str, str, str], str] | None = None,
        down: bool = False,
    ) -> None:
        self.reply = reply
        self.responder = responder
        self.down = down
        self.calls: list[dict[str, str]] = []

    async def complete(self, *, system: str, prompt: str, model: str) -> LLMResult:
        if self.down:
            raise LLMUnavailable("fake llm is down")
        self.calls.append({"system": system, "prompt": prompt, "model": model})
        text = self.responder(system, prompt, model) if self.responder else self.reply
        return LLMResult(
            text=text,
            tokens_in=len(prompt.split()),
            tokens_out=len(text.split()),
            model=model,
        )
