"""Real Jev adapter, exercised with a fake SDK client (never the network)."""

from __future__ import annotations

import asyncio

import pytest

from adapters.decisions import DecisionUnavailable, FallbackDecisions, GeminiDecider
from adapters.jev import FakeChoice, FakeJevSDKClient, JevClient
from adapters.llm import FakeLLM
from core.contracts import Passage
from core.settings import Settings


def S(**kw) -> Settings:
    kw.setdefault("JEV_API_KEY", "test-key")
    kw.setdefault("JEV_TIMEOUT_MS", 100)
    return Settings(**kw)


def jev(client, **kw) -> JevClient:
    # Batching is off by default in production; these tests exercise it, so turn it on.
    kw.setdefault("JEV_BATCH_GATE", True)
    return JevClient(S(**kw), client=client, choice=FakeChoice)


def P(i=0, kind="judgment"):
    return Passage(record_id=f"r{i}", text=f"passage text {i}", kind=kind)


async def in_run(j, n):
    from adapters.jev import begin_run

    async def run():
        begin_run()
        return await asyncio.gather(*(j.rate_passage("q", P(i)) for i in range(n)))

    return await asyncio.create_task(run())


async def test_decide_maps_scope_and_safety_in_one_request():
    def pick(name, q):
        return {"scope": ("needs_high_court", 0.9), "safety": ("trick", 0.8)}[name]

    c = FakeJevSDKClient(pick)
    d = await jev(c).decide("is bail available in Bombay High Court")
    assert (d.scope, d.safety, d.jev_used) == ("needs_high_court", "trick", True)
    assert len(c.calls) == 1 and set(c.calls[0][1]) == {"scope", "safety"}
    assert set(c.calls[0][1]["scope"].criteria) == {
        "in_scope", "needs_high_court", "needs_tribunal", "after_snapshot", "not_legal"
    }  # fmt: skip


async def test_gate_returns_choice_and_confidence_for_the_threshold():
    c = FakeJevSDKClient(lambda n, q: ("partly", 0.42))
    assert await jev(c).rate_passage("q", P()) == ("partly", 0.42)


async def test_ten_passages_are_one_request():
    c = FakeJevSDKClient(lambda n, q: ("answers", 0.9))
    j = jev(c)
    out = await in_run(j, 10)
    assert len(c.calls) == 1 and len(c.calls[0][1]) == 10
    assert out == [("answers", 0.9)] * 10


async def test_each_passage_gets_its_own_answer_in_the_batch():
    c = FakeJevSDKClient(
        lambda n, q: ("answers", 0.9) if n == "i0" else ("not_relevant", 0.7)
    )
    j = jev(c)
    out = await in_run(j, 3)
    assert [r for r, _ in out] == ["answers", "not_relevant", "not_relevant"]


async def test_claims_are_single_requests_and_weak_support_is_downgraded():
    conf = {"i0": 0.95}
    c = FakeJevSDKClient(lambda n, q: ("supports", conf.get(n, 0.3)))
    j = jev(c, JEV_CLAIM_THRESHOLD=0.7)
    a = await j.claim_support("s0", P(0))
    assert a == "supports"
    j2 = jev(FakeJevSDKClient(lambda n, q: ("supports", 0.5)), JEV_CLAIM_THRESHOLD=0.7)
    assert await j2.claim_support("s1", P(1)) == "partly"
    two = await asyncio.gather(j.claim_support("a", P(0)), j.claim_support("b", P(1)))
    assert len(c.calls) == 3 and len(two) == 2  # never batched


async def test_error_becomes_decision_unavailable():
    c = FakeJevSDKClient(fail=RuntimeError("boom"))
    with pytest.raises(DecisionUnavailable):
        await jev(c).rate_passage("q", P())


async def test_choice_outside_allowed_list_is_refused():
    c = FakeJevSDKClient(lambda n, q: ("maybe", 0.9))
    with pytest.raises(DecisionUnavailable):
        await jev(c).claim_support("s", P())


async def test_missing_key_raises_before_any_request():
    c = FakeJevSDKClient()
    with pytest.raises(DecisionUnavailable):
        await jev(c, JEV_API_KEY="").decide("q")
    assert c.calls == []


async def test_uploads_never_reach_the_jev_client():
    c = FakeJevSDKClient()
    j = jev(c)
    with pytest.raises(DecisionUnavailable):
        await j.rate_passage("q", P(kind="upload"))
    with pytest.raises(DecisionUnavailable):
        await j.claim_support("s", P(kind="upload"))
    with pytest.raises(DecisionUnavailable):
        await j.decide("q", uploads=True)
    assert c.calls == []


ALL_ON = dict(
    JEV_ENABLED_SCOPE=True, JEV_ENABLED_FILTERS=True, JEV_ENABLED_GATE=True,
    JEV_ENABLED_CLAIM=True, JEV_ENABLED_SAFETY=True,
)  # fmt: skip


def with_fallback(client, text, **kw):
    s = S(**kw)
    return FallbackDecisions(
        JevClient(s, client=client, choice=FakeChoice),
        GeminiDecider(FakeLLM(text), s),
        s,
    )


GEMINI = '{"rating": "partly", "score": 0.7}'


async def test_timeout_falls_back_to_gemini():
    c = FakeJevSDKClient(delay_s=0.5)
    d = with_fallback(c, GEMINI, **ALL_ON)
    assert await d.rate_passage("q", P()) == ("partly", 0.7)


async def test_jev_error_falls_back_to_gemini():
    d = with_fallback(FakeJevSDKClient(fail=RuntimeError("x")), GEMINI, **ALL_ON)
    assert await d.rate_passage("q", P()) == ("partly", 0.7)


async def test_switch_off_goes_to_gemini_without_touching_jev():
    c = FakeJevSDKClient()
    d = with_fallback(c, GEMINI)  # all JEV_ENABLED_* default to False
    assert await d.rate_passage("q", P()) == ("partly", 0.7)
    assert c.calls == []


async def test_missing_key_falls_back_not_crash():
    d = with_fallback(FakeJevSDKClient(), GEMINI, JEV_API_KEY="", **ALL_ON)
    assert await d.rate_passage("q", P()) == ("partly", 0.7)


async def test_upload_passage_goes_to_gemini_never_jev():
    c = FakeJevSDKClient()
    d = with_fallback(c, GEMINI, **ALL_ON)
    assert await d.rate_passage("q", P(kind="upload")) == ("partly", 0.7)
    assert c.calls == []


async def test_decide_switches_use_jev_only_when_scope_and_safety_on():
    scope = '{"scope": "in_scope", "safety": "normal"}'
    c = FakeJevSDKClient()
    off = with_fallback(c, scope, JEV_ENABLED_SCOPE=True)  # safety still off
    await off.decide("q")
    assert c.calls == []
    on = with_fallback(c, scope, **ALL_ON)
    await on.decide("q")
    assert len(c.calls) == 1


def test_all_jev_switches_default_to_false():
    s = Settings()
    assert not any(getattr(s, n) for n in dir(s) if n.startswith("JEV_ENABLED_"))
    assert len([n for n in dir(s) if n.startswith("JEV_ENABLED_")]) == 5


async def test_batches_never_mix_pipeline_runs():
    from adapters.jev import begin_run

    c = FakeJevSDKClient(lambda n, q: ("answers", 0.9))
    j = jev(c)

    async def one_run(tag):
        begin_run()
        return await asyncio.gather(
            *(j.rate_passage(f"q-{tag}", P(i)) for i in range(3))
        )

    await asyncio.gather(one_run("alice"), one_run("bob"))
    assert len(c.calls) == 2  # one request per run, never one shared request
    for state, qs in c.calls:
        assert len({v["question"] for v in state.values()}) == 1
        assert len(qs) == 3


async def test_calls_outside_a_run_are_never_batched():
    c = FakeJevSDKClient(lambda n, q: ("answers", 0.9))
    j = jev(c)
    await asyncio.gather(*(j.rate_passage("q", P(i)) for i in range(3)))
    assert len(c.calls) == 3


async def test_aclose_closes_the_client():
    c = FakeJevSDKClient()
    j = jev(c)
    await j.aclose()
    assert c.closed


async def test_error_text_never_contains_query_or_passage():
    c = FakeJevSDKClient(fail=ValueError("SECRET-PASSAGE-TEXT in the error"))
    with pytest.raises(DecisionUnavailable) as e:
        await jev(c).rate_passage("SECRET-QUERY", P())
    assert "SECRET" not in str(e.value)


async def test_claim_support_never_merges_even_inside_a_run():
    from adapters.jev import begin_run

    c = FakeJevSDKClient(lambda n, q: ("supports", 0.99))
    j = jev(c)

    async def run():
        begin_run()
        return await asyncio.gather(*(j.claim_support(f"s{i}", P(i)) for i in range(4)))

    await asyncio.create_task(run())
    assert len(c.calls) == 4 and all(len(qs) == 1 for _, qs in c.calls)


async def test_gate_batching_can_be_switched_off():
    c = FakeJevSDKClient(lambda n, q: ("answers", 0.9))
    j = jev(c, JEV_BATCH_GATE=False)
    await in_run(j, 3)
    assert len(c.calls) == 3


async def test_silent_fallback_is_logged_once_without_content(caplog):
    import logging

    from adapters import decisions as dec

    dec._warned.clear()
    caplog.set_level(logging.WARNING)
    d = with_fallback(
        FakeJevSDKClient(fail=RuntimeError("SECRET-TEXT")), GEMINI, **ALL_ON
    )
    for _ in range(3):
        await d.rate_passage("SECRET-QUERY", P())
    msgs = [r.message for r in caplog.records if "Jev unavailable" in r.message]
    assert len(msgs) == 1 and "SECRET" not in msgs[0]


def test_gate_batching_is_off_by_default():
    from core.settings import Settings

    assert Settings.model_fields["JEV_BATCH_GATE"].default is False
