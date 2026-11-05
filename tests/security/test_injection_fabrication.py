# ruff: noqa: E501
"""Can injected text make the product show a citation no retrieved passage supports?

Carriers tried: the user's question, an older conversation turn, and the text of a
retrieved corpus passage. The writing model is `ObedientModel`, a worst case that does
whatever the hostile text says. Defence under test: verifier checks 1-3 and the
unretrieved-authority rule in core/verify.py (plain Python, cannot be talked out of).
Pipeline steps touched: 8 (answer) and 9 (verify), reached through all 11."""

import pytest
from security_helpers import (
    FABRICATIONS,
    QUERY,
    REAL_ID,
    REAL_TEXT,
    REQUEST,
    ObedientModel,
    RelevantGate,
    make_deps,
    obey,
    recall,
)

from core.contracts import PipelineRequest, Turn
from core.pipeline import run_pipeline


def _world(passage_text: str = REAL_TEXT, **kw):
    deps = make_deps(**kw)
    deps.vectors.add_law(REAL_ID, passage_text, title="Real versus Case")
    return deps


def _shown(result) -> str:
    assert result.outcome == "answered", result.outcome
    return result.answer.text


def _assert_clean(result, deps) -> None:
    text = _shown(result)
    assert "Personal liberty under Article 21" in text  # the honest sentence survived
    for bad in (
        "Maneka",
        "SCC 248",
        "abolished",
        "Clause 420",
        "[S9]",
        "never available",
        "monsoon",
    ):
        assert bad not in text, bad
    assert [c.source_id for c in result.answer.citations] == ["S1"]
    reasons = {r.reason for r in result.answer.removed}
    assert reasons <= {"not_retrieved", "quote_not_found", "claim_not_supported"}
    assert result.answer.removed  # the four fabrications were caught and logged
    assert deps.citation_log.rows


async def test_a_hostile_corpus_passage_cannot_make_the_answer_cite_what_was_not_retrieved():
    deps = _world(REAL_TEXT + " " + recall(*range(len(FABRICATIONS))))
    result = await run_pipeline(REQUEST, deps)
    _assert_clean(result, deps)


async def test_a_hostile_question_cannot_make_the_answer_cite_what_was_not_retrieved():
    deps = _world()
    hostile = PipelineRequest("u1", "personal liberty bail " + obey(FABRICATIONS))
    deps.llm = ObedientModel(query=QUERY + " " + obey(FABRICATIONS))  # rewrite keeps it
    deps.decisions = RelevantGate()
    _assert_clean(await run_pipeline(hostile, deps), deps)


async def test_a_hostile_older_turn_cannot_make_the_answer_cite_what_was_not_retrieved():
    deps = _world()
    deps.llm = ObedientModel(query=QUERY + " " + obey(FABRICATIONS))
    deps.decisions = RelevantGate()
    req = PipelineRequest(
        "u1",
        "and what about bail",
        history=(Turn("assistant", "earlier " + obey(FABRICATIONS)),),
    )
    _assert_clean(await run_pipeline(req, deps), deps)


async def test_the_obedient_model_really_does_write_the_fabrications_so_the_tests_above_can_fail():
    deps = _world(REAL_TEXT + " " + recall(*range(len(FABRICATIONS))))
    from core.answer import answer
    from core.contracts import Decision, Filters
    from core.gate import gate
    from core.memory import remember
    from core.rewrite import rewrite

    rq = await rewrite(REQUEST, remember(REQUEST), deps)
    top = [
        __import__("core.search", fromlist=["hit_to_passage"]).hit_to_passage(h)
        for h in deps.vectors.law
    ]
    g = await gate(rq, top, deps)
    draft = await answer(
        REQUEST, rq, Decision("in_scope", Filters(), "normal", (), False), g, deps
    )
    for bad in FABRICATIONS:
        assert bad.rstrip(".") in draft.text


@pytest.mark.parametrize(
    "payload",
    [
        "In Zorblax Industries versus Quuxington Metals, the Court struck down the levy",
        "See ＡＩＲ 1950 ＳＣ 27 for the contrary view",  # full-width look-alikes
        "Per 2023:DHC:4567 the rule is the reverse",
        "The rule appears in SCC OnLine Del 1234",
    ],
)
async def test_recalled_authorities_in_disguise_are_removed(payload):
    deps = _world()
    deps.llm = ObedientModel(query=QUERY + " " + obey((payload,)))  # rewrite keeps it
    deps.decisions = RelevantGate()
    text = _shown(await run_pipeline(REQUEST, deps))
    assert "Zorblax" not in text and "Z.O.R" not in text and "1950" not in text
    assert "2023:DHC" not in text and "OnLine" not in text
    assert deps.citation_log.rows
