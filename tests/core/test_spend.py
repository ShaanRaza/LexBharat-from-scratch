"""The daily AI spend figure counts helper calls next to answers (PRD-v2 5.1, A52)."""

from datetime import date

from core.settings import Settings
from core.spend import estimate_cost, summarise

DAY = date(2026, 11, 2)
ROWS = [
    {
        "day": DAY,
        "feature": "answer",
        "calls": 4,
        "tokens_in": 4000,
        "tokens_out": 1000,
    },
    {
        "day": DAY,
        "feature": "improve",
        "calls": 10,
        "tokens_in": 300,
        "tokens_out": 200,
    },
    {
        "day": DAY,
        "feature": "followups",
        "calls": 5,
        "tokens_in": 600,
        "tokens_out": 200,
    },
]


def test_no_price_means_tokens_only_not_an_invented_cost():
    s = Settings(_env_file=None)
    assert estimate_cost(s, 1000, 1000) is None
    [d] = summarise(ROWS, s)
    assert d["estimated_cost"] is None and d["cost_per_answer"] is None
    assert d["tokens_per_answer"] == (4900 + 1400) / 4


def test_helper_tokens_are_in_the_daily_total_and_the_cost_per_answer():
    s = Settings(_env_file=None, AI_PRICE_IN_PER_MTOK=1.0, AI_PRICE_OUT_PER_MTOK=2.0)
    [d] = summarise(ROWS, s)
    assert d["answers"] == 4 and d["helper_calls"] == 15 and d["helper_tokens"] == 1300
    assert (d["tokens_in"], d["tokens_out"]) == (4900, 1400)
    cost = 4900 * 1.0 / 1e6 + 1400 * 2.0 / 1e6
    assert d["estimated_cost"] == cost and d["cost_per_answer"] == cost / 4
    # without the helpers the figure would be lower: they ARE in it
    no_helpers = [r for r in ROWS if r["feature"] == "answer"]
    assert summarise(no_helpers, s)[0]["estimated_cost"] < cost


def test_days_are_listed_newest_first_and_zero_answers_do_not_divide_by_zero():
    s = Settings(_env_file=None, AI_PRICE_IN_PER_MTOK=1.0, AI_PRICE_OUT_PER_MTOK=1.0)
    rows = ROWS + [
        {
            "day": date(2026, 11, 1),
            "feature": "improve",
            "calls": 1,
            "tokens_in": 5,
            "tokens_out": 5,
        }
    ]
    out = summarise(rows, s)
    assert [d["day"] for d in out] == [DAY, date(2026, 11, 1)]
    assert out[1]["cost_per_answer"] is None and out[1]["answers"] == 0
