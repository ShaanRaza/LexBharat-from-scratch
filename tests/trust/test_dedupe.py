"""Step 5 duplicates: two points with the same chunk id must never both reach the gate,
and identical text from two different documents must always both survive.

Why it matters: in the corpus 4,871 chunk ids sit on two points each. Without
the de-duplication in core/dedupe.py the same passage could take two of the eight
gate slots, get two source labels (S1 and S4), and an answer could cite identical
text twice with every verifier check passing. The opposite mistake is just as bad:
short titles, repealed placeholders and definitions repeat word for word across state
adaptations of a central Act, and merging those would let an answer cite the wrong
Act."""

from __future__ import annotations

import dataclasses

from adversarial_helpers import CASE_ID, REQUEST, TEXT, make_deps

from adapters.qdrant import FakeVectorStore
from core.contracts import Passage, run_pipeline
from core.dedupe import dedupe_passages, source_document, text_key
from core.gate import gate as real_gate
from core.settings import get_settings

DEFINITION = "In this Act, unless the context otherwise requires, bail means release."


def P(record_id: str, text: str, score: float = 0.0, kind: str = "judgment", **kw):
    return Passage(record_id=record_id, text=text, score=score, kind=kind, **kw)


def J(record_id: str, text: str, case_id: str | None, score: float = 0.0) -> Passage:
    return P(record_id, text, score, "judgment", case_id=case_id)


def A(record_id: str, text: str, act: str | None, score: float = 0.0) -> Passage:
    return P(record_id, text, score, "act_section", act_slug=act, section="2")


# --- same chunk id ----------------------------------------------------------------
def test_same_chunk_id_twice_keeps_only_the_first_copy():
    out = dedupe_passages([P("c1", "alpha beta", 0.9), P("c1", "alpha beta", 0.4)])
    assert [(p.record_id, p.score) for p in out] == [("c1", 0.9)]


def test_same_chunk_id_with_different_text_still_keeps_one():
    out = dedupe_passages([P("c1", "alpha beta", 0.9), P("c1", "gamma delta", 0.8)])
    assert [p.record_id for p in out] == ["c1"] and out[0].text == "alpha beta"


def test_same_chunk_id_is_dropped_even_when_the_document_is_unknown():
    out = dedupe_passages([J("c1", "x", None, 0.9), J("c1", "x", None, 0.1)])
    assert len(out) == 1


# --- same text, same document: dropped --------------------------------------------
def test_same_text_in_the_same_case_keeps_one():
    ps = [J("c1", "alpha beta", "case-1", 0.9), J("c2", "alpha beta", "case-1", 0.8)]
    assert [p.record_id for p in dedupe_passages(ps)] == ["c1"]


def test_same_text_in_the_same_act_keeps_one():
    ps = [A("s1", "Short title.", "IND_1", 0.9), A("s2", "Short title.", "IND_1", 0.8)]
    assert [p.record_id for p in dedupe_passages(ps)] == ["s1"]


def test_text_that_differs_only_in_spacing_counts_as_the_same():
    ps = [
        J("c1", "alpha  beta\n gamma", "case-1"),
        J("c2", "alpha beta gamma", "case-1"),
    ]
    assert [p.record_id for p in dedupe_passages(ps)] == ["c1"]


# --- same text, different documents: both survive ---------------------------------
def test_identical_provisions_in_two_different_acts_both_survive():
    """The real pattern: a state adaptation repeats a central Act's wording verbatim."""
    ps = [
        A("central-s2", DEFINITION, "IND_central_1", 0.9),
        A("state-s2", DEFINITION, "IND_state_7", 0.8),
    ]
    assert dedupe_passages(ps) == ps


def test_repealed_placeholders_in_different_acts_all_survive():
    ps = [A(f"{a}-s9", "Repealed.", f"IND_{a}") for a in "abc"]
    assert dedupe_passages(ps) == ps


def test_identical_text_in_two_different_cases_both_survive():
    text = "The appeal is dismissed."
    ps = [J("c1", text, "case-1", 0.9), J("c2", text, "case-2", 0.8)]
    assert dedupe_passages(ps) == ps


def test_identical_text_in_a_case_and_in_an_act_both_survive():
    ps = [J("c1", "Short title.", "case-1"), A("s1", "Short title.", "IND_1")]
    assert dedupe_passages(ps) == ps


def test_identical_text_with_an_unknown_document_is_never_merged_on_text():
    ps = [J("c1", "alpha beta", None, 0.9), J("c2", "alpha beta", None, 0.8)]
    ps.append(A("s1", "alpha beta", None))
    assert dedupe_passages(ps) == ps
    assert source_document(ps[0]) is None and source_document(ps[2]) is None


def test_different_passages_all_survive_in_their_original_order():
    ps = [J("c3", "three", "k"), J("c1", "one", "k"), J("c2", "two", "k")]
    assert dedupe_passages(ps) == ps


def test_empty_texts_are_not_merged_with_each_other_only_by_chunk_id():
    out = dedupe_passages([J("c1", "", "k"), J("c2", "  ", "k"), J("c1", "", "k")])
    assert [p.record_id for p in out] == ["c1", "c2"]
    assert text_key("") is None and text_key("  \n") is None


# --- uploads ----------------------------------------------------------------------
def test_corpus_copy_beats_an_upload_with_the_same_chunk_id():
    ps = [P("c1", "uploaded words", 0.9, "upload"), P("c1", "corpus words", 0.1)]
    out = dedupe_passages(ps)
    assert [(p.text, p.kind) for p in out] == [("corpus words", "judgment")]


def test_an_upload_with_a_different_id_is_a_different_document_and_survives():
    ps = [
        P("up-1", "alpha beta", 0.99, "upload"),
        J("law-1", "alpha beta", "case-1", 0.4),
    ]
    assert dedupe_passages(ps) == ps


def test_two_uploads_with_identical_text_both_survive():
    ps = [P("u1", "same", 0.9, "upload"), P("u2", "same", 0.2, "upload")]
    assert dedupe_passages(ps) == ps


# --- through the real pipeline ----------------------------------------------------
def spy():
    seen: dict[str, list[Passage]] = {}

    async def spy_gate(rq, passages, deps):
        seen["in"] = list(passages)
        result = await real_gate(rq, passages, deps)
        seen["out"] = list(result.passages)
        return result

    return spy_gate, seen


def duplicate_store() -> FakeVectorStore:
    """One relevant passage stored three ways: the same chunk id on two points, and the
    same text under another chunk id in the SAME case. Plus the same text in a
    DIFFERENT case, which must survive."""
    store = FakeVectorStore(get_settings())
    store.add_law(CASE_ID, TEXT, case_id="case-1", title="Zorblax v Quuxington")
    store.add_law(CASE_ID, TEXT, case_id="case-1", title="Zorblax v Quuxington")
    store.add_law("rec-adv-copy", TEXT, case_id="case-1", title="Zorblax v Quuxington")
    store.add_law("rec-other-case", TEXT, case_id="case-2", title="Another v Case")
    store.add_law("rec-other", "Section 138 requires a notice within thirty days.")
    return store


async def test_two_points_with_one_chunk_id_never_both_reach_the_gate():
    spy_gate, seen = spy()
    deps = make_deps(vectors=duplicate_store(), gate=spy_gate)
    res = await run_pipeline(REQUEST, deps)

    assert res.outcome == "answered", res.error
    ids = [p.record_id for p in seen["in"]]
    assert CASE_ID in ids  # the passage did get there
    assert len(ids) == len(set(ids)), f"repeated chunk id reached the gate: {ids}"
    keyed = [(source_document(p), text_key(p.text)) for p in seen["in"]]
    keyed = [k for k in keyed if k[0]]
    assert len(keyed) == len(set(keyed)), "same text twice in one case reached the gate"
    assert "rec-adv-copy" not in ids  # same text, same case: dropped
    assert "rec-other-case" in ids  # same text, different case: kept
    labelled = [(p.source_id, p.record_id) for p in seen["out"]]
    assert len({rid for _, rid in labelled}) == len(labelled), labelled


async def test_identical_provisions_of_two_acts_both_reach_the_gate():
    """Built from the real Acts pattern: same words, different act_id. A third copy
    inside one of the Acts is a repeat and is dropped."""
    store = FakeVectorStore(get_settings())
    kw = {"section_number": "2"}
    store.add_law("central-s2", TEXT, act_id="IND_central_1", title="Central Act", **kw)
    store.add_law("state-s2", TEXT, act_id="IND_state_7", title="State Act", **kw)
    store.add_law("state-s2-b", TEXT, act_id="IND_state_7", title="State Act", **kw)
    spy_gate, seen = spy()
    deps = make_deps(vectors=store, gate=spy_gate)
    res = await run_pipeline(REQUEST, deps)

    assert res.outcome == "answered", res.error
    assert {p.record_id for p in seen["in"]} == {"central-s2", "state-s2"}
    assert {p.act_slug for p in seen["in"]} == {"IND_central_1", "IND_state_7"}
    assert {p.act_slug for p in seen["out"]} == {"IND_central_1", "IND_state_7"}


async def test_an_upload_sharing_a_corpus_chunk_id_never_reaches_the_gate():
    """The upload scores far higher (9.0 against 1.0); the corpus copy still wins."""

    class UploadsScoreHigh(FakeVectorStore):
        async def search_uploads(self, *a, **k):
            hits = await super().search_uploads(*a, **k)
            return [dataclasses.replace(h, score=9.0) for h in hits]

    settings = get_settings().model_copy(update={"FEATURE_UPLOADS": True})
    store = UploadsScoreHigh(settings)
    store.add_law(
        CASE_ID, TEXT, case_id="case-1", title="Zorblax v Q", citation="(1987) 41"
    )
    store.add_upload(
        CASE_ID, TEXT, "alice", "docA"
    )  # same chunk id as the corpus record
    spy_gate, seen = spy()
    deps = make_deps(settings=settings, vectors=store, gate=spy_gate)
    req = dataclasses.replace(REQUEST, user_id="alice", document_ids=("docA",))
    res = await run_pipeline(req, deps)

    assert res.outcome == "answered", res.error
    assert store.upload_queries, "the upload search must have run"
    assert [(p.record_id, p.kind) for p in seen["in"]] == [(CASE_ID, "judgment")]
    assert res.answer.citations[0].citation_string == "(1987) 41"
