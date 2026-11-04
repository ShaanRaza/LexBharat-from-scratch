"""Pipeline steps 1-6 one by one, using only fakes and the practice fixtures."""

from __future__ import annotations

import pytest
from core_helpers import make_deps

from adapters.decisions import DecisionUnavailable, FakeDecisions
from adapters.llm import FakeLLM
from adapters.voyage import FakeEmbedder, FakeReranker
from core.contracts import (
    GATE_MAX_PASSAGES,
    RERANK_TOP_K,
    SEARCH_TOP_K,
    Decision,
    Filters,
    Memory,
    PipelineRequest,
    RewrittenQuery,
    Turn,
)
from core.decide import decide
from core.gate import gate
from core.memory import remember
from core.rerank import rerank
from core.rewrite import rewrite
from core.search import search
from core.verify import verify


def test_fixed_numbers():
    assert (SEARCH_TOP_K, RERANK_TOP_K, GATE_MAX_PASSAGES) == (50, 10, 8)


def test_remember_keeps_last_six_turns_and_folds_older_into_summary():
    hist = tuple(Turn("user", f"question {i}") for i in range(10))
    m = remember(PipelineRequest("u1", "next", history=hist, summary="earlier"))
    assert len(m.turns) == 6 and m.turns[0].text == "question 4"
    assert "earlier" in m.summary and "question 0" in m.summary


async def test_rewrite_uses_model_and_extracts_section(settings, store):
    llm = FakeLLM('{"query": "bail under section 438", "section": "438"}')
    deps = make_deps(settings, store, gate, verify, llm=llm)
    rq = await rewrite(PipelineRequest("u1", "what about it?"), Memory((), ""), deps)
    assert rq.query == "bail under section 438" and rq.section == "438"


async def test_rewrite_falls_back_to_raw_message_when_model_down(settings, store):
    deps = make_deps(settings, store, gate, verify, llm=FakeLLM(down=True))
    rq = await rewrite(
        PipelineRequest("u1", "Explain section 302 in 1973"), Memory((), ""), deps
    )
    assert rq.query == "Explain section 302 in 1973"
    assert rq.section == "302" and rq.year == 1973


async def test_rewrite_falls_back_on_junk_output(settings, store):
    deps = make_deps(settings, store, gate, verify, llm=FakeLLM("not json"))
    rq = await rewrite(PipelineRequest("u1", "hello"), Memory((), ""), deps)
    assert rq.query == "hello"


async def test_decide_conservative_when_every_decider_is_down(settings, store):
    deps = make_deps(settings, store, gate, verify, decisions=FakeDecisions(down=True))
    d = await decide(RewrittenQuery("q", section="438"), deps)
    assert d.in_scope and d.safety == "personal_advice"
    assert d.filters.section == "438"  # rewrite's section still applied


async def test_search_a_bare_section_number_is_a_ranking_signal_not_a_filter(
    settings, store
):
    # DECISIONS A144: no Act named, so the section number cannot be scoped. It used to
    # be a hard filter that returned only section 130 of every Act (or nothing); now
    # section 130 is guaranteed slots and the ordinary search still runs.
    deps = make_deps(settings, store, gate, verify)
    dec = Decision("in_scope", Filters(section="130"), "normal")
    r = await search(
        PipelineRequest("u1", "x"),
        RewrittenQuery("official communications"),
        dec,
        [0.0],
        deps,
    )
    assert r.passages and r.scope == "section signal"
    assert any(p.section == "130" for p in r.passages)
    assert any(p.section != "130" for p in r.passages)  # nothing was excluded


async def test_search_caps_at_fifty_and_strips_header(settings, store):
    deps = make_deps(settings, store, gate, verify)
    dec = Decision("in_scope", Filters(), "normal")
    r = await search(
        PipelineRequest("u1", "x"), RewrittenQuery("court appeal"), dec, [0.0], deps
    )
    assert 0 < len(r.passages) <= SEARCH_TOP_K
    judg = next(p for p in r.passages if p.kind == "judgment")
    assert judg.char_end and len(judg.text) == judg.char_end - judg.char_start


async def test_search_flags_keyword_only_when_voyage_down(settings, store):
    from core.search import embed_query

    deps = make_deps(settings, store, gate, verify, embedder=FakeEmbedder(down=True))
    vec = await embed_query("q", deps)
    assert vec is None
    dec = Decision("in_scope", Filters(), "normal")
    r = await search(
        PipelineRequest("u1", "x"), RewrittenQuery("court"), dec, vec, deps
    )
    assert r.keyword_only and r.passages


async def test_rerank_keeps_ten_and_survives_outage(settings, store):
    deps = make_deps(settings, store, gate, verify)
    dec = Decision("in_scope", Filters(), "normal")
    rq = RewrittenQuery("court appeal")
    found = await search(PipelineRequest("u1", "x"), rq, dec, [0.0], deps)
    assert len(await rerank(rq, found.passages, deps)) == RERANK_TOP_K
    down = make_deps(settings, store, gate, verify, reranker=FakeReranker(down=True))
    assert len(await rerank(rq, found.passages, down)) == RERANK_TOP_K
    assert await rerank(rq, (), deps) == ()


async def test_decisions_unavailable_error_type():
    with pytest.raises(DecisionUnavailable):
        await FakeDecisions(down=True).decide("q")
