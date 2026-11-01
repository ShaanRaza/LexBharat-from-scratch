"""run_pipeline end to end with fakes + trust's real gate and verifier."""

from __future__ import annotations

import dataclasses
import json
import re

import pytest
from core_helpers import make_deps

from adapters.decisions import FakeDecisions
from adapters.llm import FakeLLM
from adapters.memory import FakeUsageMeter
from core.contracts import (
    Citation,
    FinalEvent,
    Footer,
    PipelineRequest,
    PipelineResult,
    TextDelta,
    VerifiedAnswer,
    run_pipeline,
    stream_events,
)
from core.gate import gate
from core.verify import verify

QUERY = "official communications"


def scripted(answer_fn=None):
    """Rewrite prompt -> JSON; answer prompt -> text citing S1 with S1's own words."""

    def respond(prompt: str, system: str) -> str:
        if prompt.startswith("Turn the user's"):
            return '{"query": "%s"}' % QUERY
        m = re.search(r"\[S1\] (.*?)(?:\n\n|\Z)", prompt, re.S)
        words = m.group(1).split()[:12] if m else []
        if answer_fn:
            return answer_fn(" ".join(words))
        return " ".join(words) + " [S1]."

    return FakeLLM(respond)


def deps_for(settings, store, **over):
    over.setdefault("llm", scripted())
    over.setdefault("verify", verify)
    return make_deps(settings, store, gate, **over)


async def test_happy_path_answers_with_sealed_verified_citation(settings, store):
    deps = deps_for(settings, store)
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    assert res.outcome == "answered", res.error
    assert res.answer is not None and res.answer.sealed
    assert res.answer.citations
    assert all(c.status in ("verified", "partly") for c in res.answer.citations)
    assert res.footer.data_as_of == "2026-08-31"
    assert "CC BY 4.0" in res.footer.credit
    assert res.counted and deps.usage.counts == {"u1": 1}
    assert len(deps.store.saved) == 1


async def test_second_identical_question_is_a_free_cache_hit(settings, store):
    deps = deps_for(settings, store)
    req = PipelineRequest("u1", "Tell me about " + QUERY)
    first = await run_pipeline(req, deps)
    llm_calls = len(deps.llm.prompts)
    second = await run_pipeline(req, deps)
    assert second.cache_hit and second.outcome == "answered"
    assert second.answer.sealed and second.answer.text == first.answer.text
    assert not second.counted and deps.usage.counts == {"u1": 1}
    assert len(deps.llm.prompts) == llm_calls + 1  # only the cheap rewrite


async def test_tampered_cache_entry_is_a_miss(settings, store):
    deps = deps_for(settings, store)
    req = PipelineRequest("u1", "Tell me about " + QUERY)
    await run_pipeline(req, deps)
    (key,) = deps.cache.data
    entry = json.loads(deps.cache.data[key])
    entry["text"] += " An extra claim nobody verified."
    deps.cache.data[key] = json.dumps(entry)
    again = await run_pipeline(req, deps)
    assert not again.cache_hit and again.outcome == "answered"


async def test_usage_limit(settings, store):
    deps = deps_for(settings, store, usage=FakeUsageMeter(limit=0))
    res = await run_pipeline(PipelineRequest("u1", QUERY), deps)
    assert res.outcome == "usage_limit" and res.answer is None and not res.counted
    assert deps.llm.prompts == [] and deps.embedder.calls == 0  # no AI cost


async def test_out_of_scope_stops_before_search_and_writing(settings, store):
    deps = deps_for(settings, store, decisions=FakeDecisions(scope="needs_high_court"))
    res = await run_pipeline(PipelineRequest("u1", QUERY), deps)
    assert res.outcome == "out_of_scope"
    assert res.message_key == "out_of_scope:needs_high_court"
    assert deps.embedder.calls == 1  # embedding runs in parallel with the decision
    assert all("Passages:" not in p for p in deps.llm.prompts)  # nothing written


async def test_tricky_request_is_blocked(settings, store):
    deps = deps_for(settings, store, decisions=FakeDecisions(safety="trick"))
    res = await run_pipeline(PipelineRequest("u1", QUERY), deps)
    assert res.outcome == "out_of_scope" and res.message_key == "blocked:trick"


async def test_personal_advice_sets_footer_flag(settings, store):
    deps = deps_for(settings, store, decisions=FakeDecisions(safety="personal_advice"))
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    assert res.footer.personal_advice_flag


async def test_nothing_relevant_means_not_found_and_nothing_written(settings, store):
    deps = deps_for(settings, store, llm=FakeLLM('{"query": "zzzqqq xylophone"}'))
    res = await run_pipeline(PipelineRequest("u1", "zzzqqq xylophone"), deps)
    assert res.outcome == "not_found" and res.answer is None and not res.counted
    assert deps.usage.counts == {}
    assert all("Passages:" not in p for p in deps.llm.prompts)


async def test_invented_citation_is_removed_and_logged(settings, store):
    deps = deps_for(
        settings,
        store,
        llm=scripted(lambda w: w + " [S1]. Another point is made here [S9]."),
    )
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    assert res.outcome == "answered"
    assert "S9" not in res.answer.text
    assert all(c.source_id != "S9" for c in res.answer.citations)
    assert res.answer.had_removals
    assert deps.citation_log.rows and deps.citation_log.rows[0][2].reason


async def test_pipeline_error_shows_nothing_partial(settings, store):
    async def boom(*a, **k):
        raise RuntimeError("verifier exploded")

    deps = deps_for(settings, store, verify=boom)
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    assert res.outcome == "error" and res.answer is None
    assert not deps.cache.data and deps.usage.counts == {}


async def test_upload_chat_is_never_cached_and_isolated(settings, store):
    s = settings.model_copy(update={"FEATURE_UPLOADS": True})
    store.add_upload("a1", "official communications privilege note", "alice", "docA")
    store.add_upload("b1", "official communications secret of bob", "bob", "docB")
    deps = deps_for(s, store)
    req = PipelineRequest("alice", "Tell me about " + QUERY, document_ids=("docA",))
    res = await run_pipeline(req, deps)
    assert res.outcome == "answered"
    assert not deps.cache.data
    assert store.upload_queries == [{"user_id": "alice", "document_ids": ("docA",)}]
    assert all("secret of bob" not in p for p in deps.llm.prompts)


async def test_upload_chat_decision_not_sent_to_jev(settings, store):
    seen = []

    class Spy(FakeDecisions):
        async def decide(self, query, *, uploads=False):
            seen.append(uploads)
            return await super().decide(query, uploads=uploads)

    s = settings.model_copy(update={"FEATURE_UPLOADS": True})
    deps = deps_for(s, store, decisions=Spy())
    await run_pipeline(PipelineRequest("u", QUERY, document_ids=("d",)), deps)
    assert seen == [True]


def sealed_result(settings, store):
    return deps_for(settings, store)


async def test_show_streams_words_then_one_final_event(settings, store):
    deps = deps_for(settings, store)
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    events = [e async for e in stream_events(res)]
    assert all(isinstance(e, TextDelta) for e in events[:-1])
    assert isinstance(events[-1], FinalEvent)
    assert sum(isinstance(e, FinalEvent) for e in events) == 1
    assert "".join(e.text for e in events[:-1]) == res.answer.text
    assert events[-1].citations == res.answer.citations


async def test_show_refuses_forged_and_edited_answers(settings, store):
    deps = deps_for(settings, store)
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    footer = res.footer
    forged = VerifiedAnswer("invented [S1]", (), ())
    with pytest.raises(ValueError):
        PipelineResult("answered", forged, footer)
    edited = dataclasses.replace(res.answer, text=res.answer.text + " extra claim")
    with pytest.raises(ValueError):
        PipelineResult("answered", edited, footer)
    fake_cit = Citation("S1", "x", "verified", None, None, None)
    swapped = dataclasses.replace(res.answer, citations=(fake_cit,))
    with pytest.raises(ValueError):
        PipelineResult("answered", swapped, footer)


async def test_non_answer_must_not_carry_an_answer(settings, store):
    deps = deps_for(settings, store)
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    with pytest.raises(ValueError):
        PipelineResult("not_found", res.answer, Footer("x", "y"))


async def test_show_raises_typeerror_on_unsealed(settings, store):
    from core.show import show

    class Fake:  # bypasses PipelineResult's own check on purpose
        outcome = "answered"
        answer = VerifiedAnswer("x", ())
        footer = Footer("d", "v")
        message_key = ""

    with pytest.raises(TypeError):
        _ = [e async for e in show(Fake())]


async def test_model_follows_plan_from_config(settings, store):
    deps = deps_for(settings, store)
    res = await run_pipeline(
        PipelineRequest("u1", "Tell me about " + QUERY, plan="student"), deps
    )
    assert res.model == settings.MODEL_STUDENT


async def test_all_citations_failed_returns_not_found_but_logs(settings, store):
    deps = deps_for(
        settings, store, llm=scripted(lambda w: "A claim from memory [S9].")
    )
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    assert res.outcome == "not_found" and res.answer is None and not res.counted
    assert res.removed and deps.citation_log.rows
    assert not deps.cache.data and deps.usage.counts == {}


async def test_prose_without_any_source_marker_is_refused(settings, store):
    deps = deps_for(
        settings, store, llm=scripted(lambda w: "Bail is a right in many cases.")
    )
    res = await run_pipeline(PipelineRequest("u1", "Tell me about " + QUERY), deps)
    assert res.outcome == "not_found" and res.answer is None and not res.counted
    assert not deps.cache.data and deps.usage.counts == {}
