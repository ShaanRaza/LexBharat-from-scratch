"""Answer provenance (O11, O12, O14): the pipeline records whether an upload or a
remembered matter fact shaped the answer, writes it in step 11, and never caches or
shares such an answer."""

from __future__ import annotations

from test_pipeline import QUERY, deps_for

from core.contracts import AnswerProvenance, PipelineRequest, run_pipeline


async def _run(settings, store, **req):
    deps = deps_for(settings, store)
    res = await run_pipeline(
        PipelineRequest("u1", "Tell me about " + QUERY, **req), deps
    )
    assert res.outcome == "answered", res.error
    return res, deps


async def test_plain_public_answer_is_shareable(settings, store):
    res, deps = await _run(settings, store)
    assert res.provenance == AnswerProvenance(False, False)
    assert res.provenance.shareable
    saved_request, saved = deps.store.saved[0]
    assert saved.provenance.shareable  # the flag reaches the Save step


async def test_matter_fact_flags_the_answer_and_blocks_sharing(settings, store):
    res, deps = await _run(settings, store, matter_facts=("I act for the petitioner",))
    assert res.provenance.shaped_by_matter_fact
    assert not res.provenance.shareable
    assert deps.store.saved[0][1].provenance.shaped_by_matter_fact


async def test_matter_fact_answer_is_never_cached_or_served_from_cache(settings, store):
    deps = deps_for(settings, store)
    q = "Tell me about " + QUERY
    await run_pipeline(PipelineRequest("u1", q, matter_facts=("secret fact",)), deps)
    # Another user asking the same question must not be served that answer from cache.
    other = await run_pipeline(PipelineRequest("u2", q), deps)
    assert not other.cache_hit
    assert not other.provenance.shaped_by_matter_fact


async def test_upload_chat_is_upload_shaped_even_with_no_upload_passage(
    settings, store
):
    res, _ = await _run(settings, store, document_ids=("d1",))
    assert res.provenance.shaped_by_upload
    assert not res.provenance.shareable


def test_flags_have_no_default_in_the_database():
    """The migration drops the default so a save cannot forget to set the flags."""
    import re
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2] / "migrations/versions/0006_matters.py"
    ).read_text()
    assert re.search(r"alter_column\(\"messages\", col, server_default=None\)", text)
