"""Step 8 - Answer: the model writes using only the gated passages (S1-S8)."""

from __future__ import annotations

from pathlib import Path

from core.contracts import (
    Decision,
    Deps,
    DraftAnswer,
    GateResult,
    PipelineRequest,
    RewrittenQuery,
)

_PROMPT = Path(__file__).parent / "prompts" / "answer.txt"


def model_for(plan: str, deps: Deps) -> str:
    s = deps.settings
    return {"free": s.MODEL_FREE, "student": s.MODEL_STUDENT}.get(plan, s.MODEL_PRO)


def build_prompt(rq: RewrittenQuery, gate: GateResult, notes: list[str]) -> str:
    blocks = "\n\n".join(f"[{p.source_id}] {p.text}" for p in gate.passages)
    return _PROMPT.read_text().format(
        query=rq.query, notes="\n".join(notes) or "(none)", passages=blocks
    )


async def answer(
    request: PipelineRequest,
    rq: RewrittenQuery,
    decision: Decision,
    gate: GateResult,
    deps: Deps,
) -> DraftAnswer:
    """Input: gated passages. Output: a DRAFT with [S1]-style markers. The draft is
    never shown; it goes to the verifier, which seals it."""
    notes = list(deps.notes(decision.note_ids))
    model = model_for(request.plan, deps)
    r = await deps.llm.complete(
        build_prompt(rq, gate, notes), model=model, max_tokens=1500
    )
    return DraftAnswer(r.text, model, r.input_tokens, r.output_tokens, rq.query)
