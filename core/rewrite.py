"""Step 2 - REWRITE: one cheap model call -> a standalone query plus any Act, section,
case number or year the user named."""

from __future__ import annotations

import json
import re

from adapters.gemini import LLMClient
from core.models import Memory, RewriteResult
from core.prompts_loader import render_prompt
from core.settings import Settings

_SECTION = re.compile(r"\bsection\s+(\d+[A-Za-z]?)", re.IGNORECASE)
_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def _fallback(message: str) -> RewriteResult:
    """No model, or a garbled reply: use the user's own words and regex the basics."""
    section = _SECTION.search(message)
    year = _YEAR.search(message)
    return RewriteResult(
        query=message.strip(),
        section=section.group(1) if section else "",
        year=int(year.group(1)) if year else None,
    )


async def rewrite(
    message: str, memory: Memory, llm: LLMClient, settings: Settings
) -> RewriteResult:
    recent = "\n".join(f"User: {t.user}\nAnswer: {t.assistant}" for t in memory.recent)
    try:
        result = await llm.complete(
            system="You rewrite legal questions. Reply with JSON only.",
            prompt=render_prompt(
                "rewrite",
                product_name=settings.PRODUCT_NAME,
                summary=memory.summary or "(none)",
                recent=recent or "(none)",
                message=message,
            ),
            model=settings.MODEL_REWRITE,
        )
        data = json.loads(result.text)
        query = str(data["query"]).strip()
        if not query:
            raise ValueError("empty query")
        year = data.get("year")
        return RewriteResult(
            query=query,
            act_name=str(data.get("act_name") or ""),
            section=str(data.get("section") or ""),
            case_number=str(data.get("case_number") or ""),
            year=int(year) if year else None,
        )
    except Exception:  # noqa: BLE001 - model down, bad JSON, missing key: never fail the question
        return _fallback(message)
