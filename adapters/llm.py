"""AI model gateway (Gemini via LiteLLM). The ONLY file that calls a writing model.

Plain words: complete(prompt) returns text. Model names come from settings, so changing
the model is a config change. Only no-training providers (Gemini PAID tier) are allowed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from core.settings import Settings


class LLMUnavailable(Exception):
    pass


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLM(Protocol):
    async def complete(
        self, prompt: str, *, system: str = "", model: str, max_tokens: int = 1024
    ) -> LLMResult: ...


class LiteLLMClient:
    """Real client. litellm is imported lazily. Not verified (no key, dep not added)."""

    def __init__(self, settings: Settings):
        self._s = settings

    async def complete(
        self, prompt: str, *, system: str = "", model: str, max_tokens: int = 1024
    ) -> LLMResult:
        try:
            import litellm

            msgs = ([{"role": "system", "content": system}] if system else []) + [
                {"role": "user", "content": prompt}
            ]
            r = await litellm.acompletion(
                model=model,
                messages=msgs,
                max_tokens=max_tokens,
                api_key=self._s.GEMINI_API_KEY.get_secret_value(),
            )
        except Exception as e:
            raise LLMUnavailable(str(e)) from e
        u = r.usage
        return LLMResult(
            r.choices[0].message.content or "",
            model,
            u.prompt_tokens,
            u.completion_tokens,
        )


class FakeLLM:
    """Scripted model. `respond(prompt, system) -> str`; `down=True` simulates outage."""

    def __init__(
        self,
        respond: Callable[[str, str], str] | str = "",
        down: bool = False,
    ):
        self.respond, self.down = respond, down
        self.prompts: list[str] = []

    async def complete(
        self, prompt: str, *, system: str = "", model: str, max_tokens: int = 1024
    ) -> LLMResult:
        self.prompts.append(prompt)
        if self.down:
            raise LLMUnavailable("fake down")
        text = self.respond(prompt, system) if callable(self.respond) else self.respond
        return LLMResult(text, model, len(prompt) // 4, len(text) // 4)
