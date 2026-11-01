"""Small tests for single steps and for each adapter's Fake."""

from __future__ import annotations

import hashlib
import hmac

import pytest
from conftest import make_corpus, make_settings

from adapters.cache import FakeCache
from adapters.firebase import AuthUser, FakeAuth, InvalidToken
from adapters.gemini import FakeLLM, LLMUnavailable
from adapters.jev import (
    DecisionAdapter,
    DecisionUnavailable,
    FakeDecisionBackend,
    GeminiDecisionBackend,
)
from adapters.ocr import FakeOcr
from adapters.qdrant import SearchFilters
from adapters.razorpay import FakeRazorpay, verify_webhook_signature
from adapters.s3 import FakeObjectStore
from adapters.voyage import FakeVoyage, VoyageUnavailable
from core.cache import cache_key, cache_lookup
from core.decide import decide
from core.gate import gate
from core.models import Memory, RankedPassage, RerankResult, RewriteResult, Turn
from core.remember import remember
from core.rerank import rerank
from core.rewrite import rewrite

# ---------------- steps ----------------


async def test_remember_without_enough_history_keeps_everything_and_no_llm_call():
    llm = FakeLLM("x")
    history = tuple(Turn(f"q{i}", f"a{i}") for i in range(3))
    mem = await remember(history, "", llm, make_settings())
    assert len(mem.recent) == 3 and mem.summary == "" and llm.calls == []


async def test_remember_keeps_old_summary_if_the_model_fails():
    history = tuple(Turn(f"q{i}", f"a{i}") for i in range(8))
    mem = await remember(history, "old summary", FakeLLM(down=True), make_settings())
    assert mem.summary == "old summary" and len(mem.recent) == 6


async def test_remember_folds_in_only_the_one_exchange_that_fell_out():
    llm = FakeLLM("new summary")
    history = tuple(Turn(f"q{i}", f"a{i}") for i in range(7))
    await remember(history, "old summary", llm, make_settings())
    prompt = llm.calls[0]["prompt"]
    assert "q0" in prompt and "q1" not in prompt


async def test_rewrite_parses_the_model_json():
    llm = FakeLLM('{"query": "bail under section 438", "section": "438", "year": 2014}')
    out = await rewrite("and that one?", Memory(), llm, make_settings())
    assert (out.query, out.section, out.year) == ("bail under section 438", "438", 2014)


async def test_rewrite_falls_back_to_the_users_words_on_garbage_or_outage():
    for llm in (FakeLLM("not json"), FakeLLM(down=True)):
        out = await rewrite(
            "What is Section 302 in 1973?", Memory(), llm, make_settings()
        )
        assert out.query == "What is Section 302 in 1973?"
        assert out.section == "302" and out.year == 1973


async def test_decide_builds_filters_from_the_rewrite_and_uses_defaults_if_all_down():
    settings = make_settings()
    rw = RewriteResult("q", act_name="CrPC", section="438", year=2014)
    ok = DecisionAdapter(FakeDecisionBackend(), FakeDecisionBackend(), settings)
    d = await decide(rw, ok)
    assert d.scope == "in_scope" and d.filters.section_number == "438"
    down = DecisionAdapter(
        FakeDecisionBackend(down=True), FakeDecisionBackend(down=True), settings
    )
    d2 = await decide(rw, down)
    assert d2.degraded and d2.scope == "in_scope"


async def test_gate_keeps_rerank_order_and_labels_s1_up():
    passages = tuple(
        RankedPassage(f"r{i}", f"c{i}", "bail arrest offence", 1.0 - i / 10, i + 1)
        for i in range(10)
    )
    jev = FakeDecisionBackend(relevance_fn=lambda q, p: ("answers", 0.9))
    adapter = DecisionAdapter(jev, FakeDecisionBackend(), make_settings())
    out = await gate("bail", RerankResult(passages), adapter, make_settings())
    assert [s.record_id for s in out.sources] == [f"r{i}" for i in range(8)]
    assert out.sources[0].source_id == "S1" and out.sources[7].source_id == "S8"


async def test_rerank_falls_back_to_search_order_when_voyage_is_down():
    from core.models import SearchResult

    store = make_corpus()
    hits = tuple(await store.search_keyword("arrest bail", SearchFilters(), 50))
    out = await rerank("arrest bail", SearchResult(hits), FakeVoyage(down=True))
    assert out.used_fallback and len(out.passages) == len(hits)


def test_cache_key_depends_on_query_filters_and_model_and_ignores_case():
    f = SearchFilters(court="supreme_court")
    assert cache_key("Bail", f, "m1") == cache_key("bail ", f, "m1")
    assert cache_key("bail", f, "m1") != cache_key("bail", f, "m2")
    assert cache_key("bail", f, "m1") != cache_key("bail", SearchFilters(), "m1")


async def test_cache_lookup_ignores_the_cache_for_upload_chats():
    cache = FakeCache()
    f = SearchFilters()
    await cache.set(cache_key("q", f, "m"), {"x": 1}, 7)
    assert (await cache_lookup("q", f, "m", cache)).hit
    assert not (await cache_lookup("q", f, "m", cache, is_upload_chat=True)).hit


# ---------------- Jev adapter: switches, timeout, fallback ----------------


def adapter(primary, fallback, **settings):
    return DecisionAdapter(primary, fallback, make_settings(**settings))


async def test_jev_is_used_when_enabled_and_healthy():
    d = await adapter(FakeDecisionBackend(), FakeDecisionBackend()).scope("bail")
    assert d.source == "jev"


async def test_switch_off_means_the_fallback_is_used_and_jev_is_not_called():
    jev = FakeDecisionBackend()
    d = await adapter(jev, FakeDecisionBackend(), JEV_ENABLED_SCOPE=False).scope("bail")
    assert d.source == "fallback" and jev.calls == []


async def test_jev_error_and_jev_timeout_both_use_the_fallback():
    for jev in (FakeDecisionBackend(down=True), FakeDecisionBackend(delay_s=0.5)):
        d = await adapter(jev, FakeDecisionBackend(), JEV_TIMEOUT_MS=20).safety("bail")
        assert d.source == "fallback"


async def test_both_down_raises_decision_unavailable():
    a = adapter(FakeDecisionBackend(down=True), FakeDecisionBackend(down=True))
    with pytest.raises(DecisionUnavailable):
        await a.relevance("q", "p")


async def test_gemini_fallback_backend_parses_choice_and_confidence():
    backend = GeminiDecisionBackend(FakeLLM("supports 0.8"), "m")
    assert await backend.claim_support("s", "p") == ("supports", 0.8)


@pytest.mark.parametrize("reply", ["maybe 0.8", "supports", "supports 7", "I think so"])
async def test_gemini_fallback_rejects_replies_outside_the_fixed_choices(reply):
    backend = GeminiDecisionBackend(FakeLLM(reply), "m")
    with pytest.raises(ValueError):
        await backend.claim_support("s", "p")


async def test_gemini_fallback_is_wired_through_the_adapter():
    a = adapter(
        FakeDecisionBackend(down=True),
        GeminiDecisionBackend(FakeLLM("partly 0.7"), "m"),
    )
    d = await a.claim_support("s", "p")
    assert (d.choice, d.confidence, d.source) == ("partly", 0.7, "fallback")


# ---------------- other adapters ----------------


async def test_voyage_fake_is_deterministic_and_can_go_down():
    v = FakeVoyage()
    assert await v.embed("bail") == await v.embed("bail")
    hits = await v.rerank("bail arrest", ["tax law", "bail and arrest"], 1)
    assert hits[0].index == 1
    with pytest.raises(VoyageUnavailable):
        await FakeVoyage(down=True).embed("x")


async def test_llm_fake_records_calls_and_can_go_down():
    llm = FakeLLM("hi")
    r = await llm.complete(system="s", prompt="p q", model="m")
    assert r.text == "hi" and r.tokens_in == 2 and llm.calls[0]["model"] == "m"
    with pytest.raises(LLMUnavailable):
        await FakeLLM(down=True).complete(system="", prompt="", model="m")


async def test_every_upload_query_requires_a_user_id_and_only_returns_that_users_chunks():
    store = make_corpus()
    store.add_upload_chunk("alice", "c1", "alice's client file")
    store.add_upload_chunk("bob", "c2", "bob's client file")
    with pytest.raises(ValueError):
        await store.search_user_documents(user_id="", vector=[1.0], limit=5)
    hits = await store.search_user_documents(user_id="alice", vector=[1.0], limit=5)
    assert [h.chunk_id for h in hits] == ["c1"]
    assert store.upload_queries == ["alice"]


def test_record_type_has_no_judge_or_party_fields():
    from adapters.qdrant import Record

    banned = {"judges", "judge", "petitioner", "respondent", "parties", "party"}
    assert banned.isdisjoint(Record.__dataclass_fields__)


async def test_s3_fake_delete_really_removes_the_object():
    s3 = FakeObjectStore()
    await s3.put("u/doc.pdf", b"x")
    assert await s3.exists("u/doc.pdf")
    await s3.delete("u/doc.pdf")
    assert not await s3.exists("u/doc.pdf")
    assert "expires=300" in await s3.presign_upload("u/doc.pdf")


async def test_firebase_fake_accepts_known_tokens_only():
    auth = FakeAuth({"tok": AuthUser("uid1", "a@b.c")})
    assert (await auth.verify_token("tok")).firebase_uid == "uid1"
    with pytest.raises(InvalidToken):
        await auth.verify_token("forged")


async def test_ocr_fake_splits_pages_on_form_feed():
    out = await FakeOcr().extract(b"page one\fpage two", "application/pdf")
    assert [p.page_no for p in out.pages] == [1, 2]


async def test_razorpay_fake_and_real_webhook_signature():
    rp = FakeRazorpay()
    sub = await rp.create_subscription("pro", "u1")
    assert (await rp.cancel_subscription(sub.subscription_id)).status == "cancelled"
    body, secret = b'{"event":"x"}', "whsec"
    good = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, good, secret)
    assert not verify_webhook_signature(body, good, "other-secret")
    assert not verify_webhook_signature(b"tampered", good, secret)
    assert not verify_webhook_signature(body, "", secret)
    assert not verify_webhook_signature(body, good, "")
