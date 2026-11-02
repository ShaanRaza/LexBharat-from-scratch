"""Step 5 duplicates: two points with the same chunk id (or the same text) must never
both reach the gate.

Why it matters: in the corpus 4,871 chunk ids sit on two points each. Without
the de-duplication in core/dedupe.py the same passage could take two of the eight
gate slots, get two source labels (S1 and S4), and an answer could cite identical
text twice with every verifier check passing."""

from __future__ import annotations

import dataclasses

from adversarial_helpers import CASE_ID, REQUEST, TEXT, make_deps

from adapters.qdrant import FakeVectorStore
from core.contracts import Passage, run_pipeline
from core.dedupe import dedupe_passages, text_key
from core.gate import gate as real_gate
from core.settings import get_settings


def P(record_id: str, text: str, score: float = 0.0, kind: str = "judgment") -> Passage:
    return Passage(record_id=record_id, text=text, score=score, kind=kind)


# --- the helper on its own -----------------------------------------------------------
def test_same_chunk_id_twice_keeps_only_the_first_copy():
    out = dedupe_passages([P("c1", "alpha beta", 0.9), P("c1", "alpha beta", 0.4)])
    assert [(p.record_id, p.score) for p in out] == [("c1", 0.9)]


def test_same_chunk_id_with_different_text_still_keeps_one():
    out = dedupe_passages([P("c1", "alpha beta", 0.9), P("c1", "gamma delta", 0.8)])
    assert [p.record_id for p in out] == ["c1"] and out[0].text == "alpha beta"


def test_same_text_under_different_chunk_ids_keeps_one():
    out = dedupe_passages([P("c1", "alpha beta", 0.9), P("c2", "alpha beta", 0.8)])
    assert [p.record_id for p in out] == ["c1"]


def test_text_that_differs_only_in_spacing_counts_as_the_same():
    out = dedupe_passages([P("c1", "alpha  beta\n gamma"), P("c2", "alpha beta gamma")])
    assert [p.record_id for p in out] == ["c1"]


def test_different_passages_all_survive_in_their_original_order():
    ps = [P("c3", "three"), P("c1", "one"), P("c2", "two")]
    assert dedupe_passages(ps) == ps


def test_empty_texts_are_not_merged_with_each_other_only_by_chunk_id():
    out = dedupe_passages([P("c1", ""), P("c2", "  "), P("c1", "")])
    assert [p.record_id for p in out] == ["c1", "c2"]
    assert text_key("") is None and text_key("  \n") is None


# --- corpus beats upload -------------------------------------------------------------
def test_corpus_copy_beats_an_uploaded_copy_even_when_the_upload_scores_higher():
    ps = [P("up-1", "alpha beta", 0.99, "upload"), P("law-1", "alpha beta", 0.40)]
    out = dedupe_passages(ps)
    assert [(p.record_id, p.kind) for p in out] == [("law-1", "judgment")]


def test_corpus_copy_beats_an_upload_with_the_same_chunk_id():
    ps = [P("c1", "uploaded words", 0.9, "upload"), P("c1", "corpus words", 0.1)]
    assert [(p.text, p.kind) for p in dedupe_passages(ps)] == [
        ("corpus words", "judgment")
    ]


def test_an_upload_that_is_not_a_duplicate_is_kept_in_score_order():
    ps = [P("up-1", "mine", 0.9, "upload"), P("law-1", "public law", 0.5)]
    assert dedupe_passages(ps) == ps


def test_two_uploaded_copies_keep_the_better_one():
    ps = [P("u1", "same", 0.9, "upload"), P("u2", "same", 0.2, "upload")]
    assert [p.record_id for p in dedupe_passages(ps)] == ["u1"]


# --- through the real pipeline -------------------------------------------------------
def duplicate_store() -> FakeVectorStore:
    """One relevant passage stored three ways: the same chunk id on two points, plus the
    same text under another chunk id. Plus one different passage."""
    store = FakeVectorStore(get_settings())
    store.add_law(CASE_ID, TEXT, title="Zorblax versus Quuxington")
    store.add_law(CASE_ID, TEXT, title="Zorblax versus Quuxington")  # same chunk id
    store.add_law("rec-adv-copy", TEXT, title="Zorblax versus Quuxington")  # same text
    store.add_law("rec-other", "Section 138 requires a notice within thirty days.")
    return store


async def test_two_points_with_one_chunk_id_never_both_reach_the_gate():
    seen: dict[str, list[Passage]] = {}

    async def spy_gate(rq, passages, deps):
        seen["in"] = list(passages)
        result = await real_gate(rq, passages, deps)
        seen["out"] = list(result.passages)
        return result

    deps = make_deps(vectors=duplicate_store(), gate=spy_gate)
    res = await run_pipeline(REQUEST, deps)

    assert res.outcome == "answered", res.error
    gate_in = seen["in"]
    assert CASE_ID in {p.record_id for p in gate_in}  # the passage did get there
    ids = [p.record_id for p in gate_in]
    assert len(ids) == len(set(ids)), f"repeated chunk id reached the gate: {ids}"
    texts = [text_key(p.text) for p in gate_in]
    assert len(texts) == len(set(texts)), "repeated text reached the gate"
    # and so the labels cannot point at the same passage twice
    labelled = [(p.source_id, p.record_id) for p in seen["out"]]
    assert len({rid for _, rid in labelled}) == len(labelled), labelled


async def test_an_uploaded_copy_of_a_corpus_passage_never_reaches_the_gate():
    """The upload scores far higher than the corpus copy (9.0 against 1.0); the corpus
    copy still wins."""
    from adapters.qdrant import FakeVectorStore as Base

    class UploadsScoreHigh(Base):
        async def search_uploads(self, *a, **k):
            hits = await super().search_uploads(*a, **k)
            return [dataclasses.replace(h, score=9.0) for h in hits]

    settings = get_settings().model_copy(update={"FEATURE_UPLOADS": True})
    store = UploadsScoreHigh(settings)
    store.add_law(
        CASE_ID, TEXT, title="Zorblax versus Quuxington", citation="(1987) 41"
    )
    store.add_upload("up-copy", TEXT, "alice", "docA")  # the user's copy of public law
    seen: dict[str, list[Passage]] = {}

    async def spy_gate(rq, passages, deps):
        seen["in"] = list(passages)
        return await real_gate(rq, passages, deps)

    deps = make_deps(settings=settings, vectors=store, gate=spy_gate)
    req = dataclasses.replace(REQUEST, user_id="alice", document_ids=("docA",))
    res = await run_pipeline(req, deps)

    assert res.outcome == "answered", res.error
    assert store.upload_queries, "the upload search must have run"
    assert [(p.record_id, p.kind) for p in seen["in"]] == [(CASE_ID, "judgment")]
    assert res.answer.citations[0].record_id == CASE_ID  # cites the corpus copy
    assert res.answer.citations[0].citation_string == "(1987) 41"
