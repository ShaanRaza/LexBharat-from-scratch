"""The "Improve my question" helper. It lives in the INPUT BOX, before the user sends.

Plain words: the user types a rough question and asks for a sharper version. One cheap
model call returns editable text; the user accepts it, changes it or ignores it. This is
NOT a pipeline step (the 11 steps and the 50-10-8 counts are untouched) and it is not an
answer. It never cites anything: if the result adds a citation, a quotation or a bracket
that the user did not write, it is thrown away and the user's own text is returned."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from adapters.llm import LLMUnavailable
from core.contracts import Deps
from core.question_text import (
    citation_shapes,
    has_citation_marker,
    has_quotes,
    normalise,
)

log = logging.getLogger(__name__)
_PROMPT = Path(__file__).parent / "prompts" / "improve.txt"
MAX_LENGTH = 1000


@dataclass(frozen=True)
class Improved:
    text: str  # editable text for the input box
    changed: bool  # False when the helper could not improve it (text == the user's own)


def safe_improvement(original: str, improved: str) -> str | None:
    """The model's suggestion, or None if it must be rejected. Pure; no model."""
    t = normalise(improved)
    if not t or len(t) > MAX_LENGTH:
        return None
    # Never cites: no source marker, label or bracket at all. Never adds a quotation or
    # a citation-shaped string that the user did not write.
    if has_citation_marker(t):
        return None
    if has_quotes(t) and not has_quotes(original):
        return None
    if citation_shapes(t) - citation_shapes(original):
        return None
    return t


async def improve_question(text: str, deps: Deps) -> Improved:
    original = normalise(text)
    try:
        r = await deps.llm.complete(
            _PROMPT.read_text().format(text=original),
            model=deps.settings.MODEL_REWRITE,
            max_tokens=300,
        )
    except LLMUnavailable:
        log.warning("improve helper unavailable")
        return Improved(original, False)
    safe = safe_improvement(original, r.text)
    if safe is None or safe == original:
        return Improved(original, False)
    return Improved(safe, True)
