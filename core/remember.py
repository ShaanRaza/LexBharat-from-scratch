"""Step 1 - REMEMBER: last 6 exchanges in full + a rolling summary of older ones."""

from __future__ import annotations

from adapters.gemini import LLMClient
from core.constants import RECENT_TURNS
from core.models import Memory, Turn
from core.prompts_loader import render_prompt
from core.settings import Settings


async def remember(
    history: tuple[Turn, ...],
    previous_summary: str,
    llm: LLMClient,
    settings: Settings,
) -> Memory:
    """Keep the last RECENT_TURNS exchanges; fold anything older into the summary.

    Each new request pushes exactly one exchange out of the "recent" window, so once a
    summary exists we only fold in that one (history[-7]). With no summary yet we fold
    in everything older. If the model call fails we keep the old summary: losing a
    summary is better than failing the user's question.
    """
    recent = history[-RECENT_TURNS:]
    older = history[:-RECENT_TURNS]
    if not older:
        return Memory(recent=tuple(recent), summary=previous_summary)

    to_fold = older if not previous_summary else older[-1:]
    turns_text = "\n".join(f"User: {t.user}\nAnswer: {t.assistant}" for t in to_fold)
    try:
        result = await llm.complete(
            system="You summarise legal research conversations.",
            prompt=render_prompt(
                "summarise", summary=previous_summary or "(none)", turns=turns_text
            ),
            model=settings.MODEL_REWRITE,
        )
        summary = result.text.strip() or previous_summary
    except Exception:  # noqa: BLE001 - keep the old summary, never fail the question
        summary = previous_summary
    return Memory(recent=tuple(recent), summary=summary)
