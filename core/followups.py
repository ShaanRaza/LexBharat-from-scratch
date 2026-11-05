"""Follow-up suggestions under an answer. QUESTIONS ONLY.

Plain words: after an answer has been verified and saved, one cheap model call proposes
a few next questions. The model is not trusted: every suggestion goes through plain
Python rules and anything that is not a short, citation-free question is dropped. A
suggestion the user runs is an ORDINARY NEW QUESTION through all 11 pipeline steps; this
file is not a pipeline step and adds none. It never produces a citation, so nothing here
can bypass the verifier."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from adapters.llm import LLMUnavailable
from core import llm_schemas
from core.contracts import Deps
from core.question_text import (
    citation_shapes,
    has_citation_marker,
    has_quotes,
    normalise,
)

log = logging.getLogger(__name__)
_PROMPT = Path(__file__).parent / "prompts" / "followups.txt"
MAX_SUGGESTIONS = 3
MAX_LENGTH = 200
_QUESTION_WORDS = (
    "what|why|how|when|where|which|who|whom|whose|is|are|was|were|can|could|does|do|did|"
    "should|would|will|may|might|has|have|had|must|shall"
)
_STARTS_LIKE_QUESTION = re.compile(rf"^(?:{_QUESTION_WORDS})\b", re.IGNORECASE)
_MARKER_IN_ANSWER = re.compile(r"\s*[\[(]\s*S\d+(?:\s*[,;]\s*S\d+)*\s*[\])]")


@dataclass(frozen=True)
class Followups:
    suggestions: list[str]
    tokens_in: int = 0  # what the model call cost, for the spend view (A52)
    tokens_out: int = 0
    model: str = ""


def clean_followups(
    candidates: Iterable[object], limit: int = MAX_SUGGESTIONS
) -> list[str]:
    """Keep only short, single-sentence QUESTIONS with no citation. Pure; no model."""
    out: list[str] = []
    for c in candidates:
        if not isinstance(c, str):
            continue
        q = normalise(c)
        if not q or len(q) > MAX_LENGTH:
            continue
        if not q.endswith("?") or q.count("?") != 1:  # one sentence, a question
            continue
        if not _STARTS_LIKE_QUESTION.match(q):  # a statement ending in "?" is dropped
            continue
        if has_citation_marker(q) or has_quotes(q) or citation_shapes(q):
            continue
        if q.lower() not in {x.lower() for x in out}:
            out.append(q)
        if len(out) == limit:
            break
    return out


async def suggest_followups(question: str, answer_text: str, deps: Deps) -> Followups:
    """Input: the question and the VERIFIED, saved answer text. Output: 0-3 questions
    plus the tokens the call used. Any failure returns no suggestions (follow-ups are
    optional and must never block an answer)."""
    plain = _MARKER_IN_ANSWER.sub("", answer_text)  # the model never sees S-labels
    prompt = _PROMPT.read_text().format(question=question, answer=plain)
    try:
        r = await deps.llm.complete(
            prompt,
            model=deps.settings.MODEL_REWRITE,
            max_tokens=300,
            json_schema=llm_schemas.FOLLOWUPS,
        )
    except LLMUnavailable:
        log.warning("follow-up suggestions unavailable")
        return Followups([])
    usage = dict(tokens_in=r.input_tokens, tokens_out=r.output_tokens, model=r.model)
    try:
        data = json.loads(r.text)
        candidates = data["questions"]
        if not isinstance(candidates, list):
            raise TypeError("questions must be a list")
    except (ValueError, KeyError, TypeError):
        log.warning("follow-up suggestions unparseable")
        return Followups([], **usage)  # the call was paid for: still counted
    return Followups(clean_followups(candidates), **usage)
