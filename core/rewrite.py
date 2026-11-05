"""Step 2 - Rewrite: one standalone query, plus any Act, section, case number, year."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from adapters.llm import LLMUnavailable
from core import llm_schemas
from core.contracts import Deps, Memory, PipelineRequest, RewrittenQuery

log = logging.getLogger(__name__)
_PROMPT = Path(__file__).parent / "prompts" / "rewrite.txt"
_SECTION = re.compile(r"\bsection\s+(\d+[A-Za-z]?)", re.I)
_YEAR = re.compile(r"\b(19[4-9]\d|20[0-3]\d)\b")


def _regex_extract(message: str) -> dict:
    s, y = _SECTION.search(message), _YEAR.search(message)
    return {
        "section": s.group(1) if s else None,
        "year": int(y.group(1)) if y else None,
    }


async def rewrite(
    request: PipelineRequest, memory: Memory, deps: Deps
) -> RewrittenQuery:
    """Input: message + memory. Output: RewrittenQuery. If the model is down or returns
    junk we fall back to the user's own message (never block on a cheap step)."""
    base = _regex_extract(request.message)
    turns = "\n".join(f"{t.role}: {t.text}" for t in memory.turns)
    prompt = _PROMPT.read_text().format(
        summary=memory.summary, turns=turns, message=request.message
    )
    try:
        r = await deps.llm.complete(
            prompt,
            model=deps.settings.MODEL_REWRITE,
            max_tokens=300,
            json_schema=llm_schemas.REWRITE,
        )
        d = json.loads(r.text)
        query = str(d["query"]).strip()
        if not query:
            raise ValueError("empty")
    except (LLMUnavailable, ValueError, KeyError, TypeError):
        log.warning("rewrite fell back to the raw message")
        return RewrittenQuery(request.message.strip(), **base)
    year = d.get("year")
    return RewrittenQuery(
        query=query,
        act=d.get("act") or None,
        section=d.get("section") or base["section"],
        case_number=d.get("case_number") or None,
        year=year if isinstance(year, int) else base["year"],
    )
