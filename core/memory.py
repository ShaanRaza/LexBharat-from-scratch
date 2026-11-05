"""Step 1 - Remember: last 6 turns in full plus a rolling summary of older turns."""

from __future__ import annotations

from core.contracts import MEMORY_FULL_TURNS, Memory, PipelineRequest

_SUMMARY_CAP = 1000


def remember(request: PipelineRequest) -> Memory:
    """Input: the request. Output: the last 6 turns + summary.

    v1 simplification: older turns are folded into the summary by truncation, not by a
    model call (no cost, deterministic). Ruled out: an LLM summary per turn.
    """
    turns = request.history[-MEMORY_FULL_TURNS:]
    older = request.history[:-MEMORY_FULL_TURNS]
    summary = request.summary
    if older:
        folded = " / ".join(f"{t.role}: {t.text[:80]}" for t in older)
        summary = f"{summary} {folded}".strip()[-_SUMMARY_CAP:]
    return Memory(turns=tuple(turns), summary=summary)
