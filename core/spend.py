"""AI spend figures for the helper calls and for answers (PRD-v2 section 5.1).

Plain words: the "Improve my question" helper and the next-question suggestions call a
paid model (Gemini) but are not answers, so they do not use the user's answer limit
(A52). They ARE counted here: every call records its tokens, and the daily spend view
adds them to the answers' tokens so the cost per answer is honest. Money is worked out
at read time from the configured price per million tokens; if no price is configured
the figure is tokens only (nothing is invented).

Not a pipeline step."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from core.settings import Settings

HelperFeature = Literal["improve", "followups"]
HELPER_FEATURES: tuple[str, ...] = ("improve", "followups")


@dataclass(frozen=True)
class AiCall:
    """One paid model call made by a helper."""

    feature: HelperFeature
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""


def estimate_cost(settings: Settings, tokens_in: int, tokens_out: int) -> float | None:
    """Money for these tokens, or None when no price is configured."""
    pin, pout = settings.AI_PRICE_IN_PER_MTOK, settings.AI_PRICE_OUT_PER_MTOK
    if pin is None or pout is None:
        return None
    return tokens_in * pin / 1_000_000 + tokens_out * pout / 1_000_000


def summarise(
    rows: Iterable[Mapping[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Per day: answers, helper calls, tokens, estimated cost and cost per answer.
    `rows` have day, feature ("answer", "improve", "followups"), calls, tokens_in,
    tokens_out (the shape of the `ai_spend_daily` view)."""
    days: dict[Any, dict[str, Any]] = {}
    for r in rows:
        d = days.setdefault(
            r["day"],
            {"day": r["day"], "answers": 0, "helper_calls": 0, "tokens_in": 0,
             "tokens_out": 0, "helper_tokens": 0},
        )  # fmt: skip
        d["tokens_in"] += int(r["tokens_in"])
        d["tokens_out"] += int(r["tokens_out"])
        if r["feature"] == "answer":
            d["answers"] += int(r["calls"])
        else:
            d["helper_calls"] += int(r["calls"])
            d["helper_tokens"] += int(r["tokens_in"]) + int(r["tokens_out"])
    out = []
    for day in sorted(days, reverse=True):
        d = days[day]
        cost = estimate_cost(settings, d["tokens_in"], d["tokens_out"])
        d["estimated_cost"] = cost
        d["cost_per_answer"] = (
            cost / d["answers"] if cost is not None and d["answers"] else None
        )
        d["tokens_per_answer"] = (
            (d["tokens_in"] + d["tokens_out"]) / d["answers"] if d["answers"] else None
        )
        out.append(d)
    return out
