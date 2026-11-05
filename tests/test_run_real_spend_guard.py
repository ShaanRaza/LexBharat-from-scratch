"""The paid-key rules of the eval runner (owner's standing rule, 5 Nov 2026), proved offline with a fake inner client.

No test here calls Gemini. They pin: a 429 or cap error stops the run at once and is never retried; spend past the
estimate by 20% stops it; a repeated prompt is served from disk at no cost; the rupee arithmetic; and a run of more
than 10 questions needs a pilot first.
"""

from __future__ import annotations

import asyncio

import pytest

from adapters.llm import LLMResult, LLMUnavailable
from evals.labelling import run_real as R


class Inner:
    def __init__(self, error: str = "", tokens: tuple[int, int] = (1000, 100)):
        self.calls, self.error, self.tokens = 0, error, tokens

    async def complete(self, prompt, **kw):
        self.calls += 1
        if self.error:
            raise LLMUnavailable(self.error)
        return LLMResult("ok", kw["model"], *self.tokens)


def run(coro):
    return asyncio.run(coro)


def test_a_spending_cap_error_stops_the_run_at_once_and_is_not_retried():
    inner = Inner(
        "litellm.RateLimitError: GeminiException 429 RESOURCE_EXHAUSTED: exceeded its monthly spending cap"
    )
    llm = R.CountingLLM(inner)
    with pytest.raises(R.SpendStop):
        run(llm.complete("p", model="m"))
    assert inner.calls == 1  # one call, no backoff loop, no second key
    assert llm.rate_limit_hits == 1


def test_a_plain_429_also_stops_the_run():
    llm = R.CountingLLM(Inner("429 too many requests"))
    with pytest.raises(R.SpendStop):
        run(llm.complete("p", model="m"))


def test_spend_past_the_estimate_by_twenty_percent_stops_the_run():
    one_call = R.inr(1000, 100)
    llm = R.CountingLLM(Inner(), budget_inr=one_call * 2)  # estimate: two calls
    run(llm.complete("a", model="m"))
    run(llm.complete("b", model="m"))  # exactly the estimate: carries on
    with pytest.raises(R.SpendStop):  # 3 calls = 150% of the estimate, past +20%
        run(llm.complete("c", model="m"))


def test_a_repeated_prompt_is_served_from_disk_and_costs_nothing(tmp_path):
    inner = Inner()
    llm = R.CountingLLM(inner, cache_dir=tmp_path)
    a = run(llm.complete("same prompt", model="m", json_schema={"x": 1}))
    b = run(llm.complete("same prompt", model="m", json_schema={"x": 1}))
    assert a == b and inner.calls == 1 and llm.cache_hits == 1
    assert llm.tokens_in == 1000  # the hit added no tokens
    run(llm.complete("a different prompt", model="m", json_schema={"x": 1}))
    run(llm.complete("same prompt", model="other-model", json_schema={"x": 1}))
    assert inner.calls == 3  # a changed prompt or model is a new key
    fresh = R.CountingLLM(Inner(), cache_dir=tmp_path)  # a crash and restart
    run(fresh.complete("same prompt", model="m", json_schema={"x": 1}))
    assert fresh.inner.calls == 0


def test_the_cache_is_off_unless_a_directory_is_given():
    inner = Inner()
    llm = R.CountingLLM(inner)  # the latency runs must time real calls
    run(llm.complete("p", model="m"))
    run(llm.complete("p", model="m"))
    assert inner.calls == 2


def test_rupee_arithmetic_is_tokens_times_the_list_price():
    usd = 1_000_000 / 1e6 * R.USD_PER_M_IN + 1_000_000 / 1e6 * R.USD_PER_M_OUT
    assert R.inr(1_000_000, 1_000_000) == pytest.approx(usd * R.INR_PER_USD)
    assert R.inr(0, 0) == 0


def test_more_than_ten_questions_needs_a_pilot_first(tmp_path):
    out = tmp_path / "answers.jsonl"  # nothing in it: no pilot yet
    with pytest.raises(SystemExit, match="no pilot"):
        run(R.main_async(None, out, 50.0, "a test"))
