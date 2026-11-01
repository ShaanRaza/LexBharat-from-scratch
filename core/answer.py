"""Step 8 - ANSWER: the model writes using ONLY the gated passages S1..S8 plus any
reviewed knowledge notes, putting a source ID after every point.

The result is a DRAFT. Nothing in it may be shown until step 9 has checked it.
"""

from __future__ import annotations

from adapters.gemini import LLMClient
from core.models import AnswerDraft, Source
from core.prompts_loader import render_prompt
from core.settings import Settings


def model_for_plan(settings: Settings, plan: str) -> str:
    """Model names come from settings (rule 2); this only picks which one."""
    return {
        "student": settings.MODEL_STUDENT,
        "pro": settings.MODEL_PRO,
        "chambers": settings.MODEL_PRO,
    }.get(plan, settings.MODEL_FREE)


def format_passages(sources: tuple[Source, ...]) -> str:
    """Passages are fenced so the model treats them as data, not instructions."""
    return "\n".join(
        f'<passage id="{s.source_id}">\n{s.text}\n</passage>' for s in sources
    )


async def answer(
    query: str,
    sources: tuple[Source, ...],
    llm: LLMClient,
    settings: Settings,
    model: str,
    *,
    notes: tuple[str, ...] = (),
) -> AnswerDraft:
    prompt = render_prompt(
        "answer",
        product_name=settings.PRODUCT_NAME,
        notes="\n".join(f"- {n}" for n in notes) or "(none)",
        passages=format_passages(sources),
        question=query,
    )
    result = await llm.complete(
        system="Follow the rules in the prompt exactly.", prompt=prompt, model=model
    )
    return AnswerDraft(
        text=result.text,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )
