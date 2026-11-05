"""Step 10 - Show: text streams word by word, then ONE final event with the checked
citations, the data-as-of date, the CC BY credit and the not-legal-advice notice."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import replace

from core.contracts import (
    FinalEvent,
    PipelineResult,
    StreamEvent,
    TextDelta,
    is_sealed,
)
from core.coverage import data_as_of_text

_WORDS = re.compile(r"\S+\s*")


async def show(result: PipelineResult) -> AsyncIterator[StreamEvent]:
    """Input: a PipelineResult. Citations come ONLY from result.answer (sealed by the
    verifier); nothing caller-supplied is ever shown. Unsealed answers raise TypeError.
    A user never sees a citation appear and then vanish: removed ones are gone before
    the first word streams."""
    citations = ()
    had_removals = False
    if result.outcome == "answered":
        ans = result.answer
        if ans is None or not is_sealed(ans):
            raise TypeError("show() refuses an answer the verifier did not seal")
        for m in _WORDS.finditer(ans.text):
            yield TextDelta(m.group())
        citations, had_removals = ans.citations, ans.had_removals
    footer = result.footer
    if citations:  # the date describes what was cited, not the release
        footer = replace(footer, data_as_of=data_as_of_text(c.kind for c in citations))
    yield FinalEvent(
        result.outcome, citations, footer, result.message_key, had_removals
    )
