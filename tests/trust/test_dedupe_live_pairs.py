# ruff: noqa: E501
"""A126 x A71: both live copies of a chunk id are kept in the corpus, so a query can retrieve
BOTH. Only one may reach the gate.

Pipeline step: 5 (Search) and the hand-off to 6 (re-rank) and 7 (gate). No verifier check is
touched.

A126 (amended) keeps both copies of a chunk id where both are live: 211 of 211 sampled live
pairs hold the same text under two different models, and nothing free says which is which.
So one question can retrieve both, as two separate POINTS with different point ids. If they
both reached the gate they would take two of the 10 re-rank slots and two of the eight
S1-S8 slots for ONE passage, crowding out a genuinely different authority, with nothing on
screen to say so.

A71 (core/dedupe.py) drops them. What it keys on is checked here against the REAL path,
not the in-memory fake: `FakeVectorStore.add_law` sets the record id to the chunk id by
construction, so a test built on it cannot tell a point id from a chunk id. These tests go
through the real QdrantStore with a fake Qdrant CLIENT, so the mapping from a stored point
(point id 2740437415798525250, payload chunk_id KLHC010348322009_001) to the record id is
the real one. The pair is a real group from the corpus (tests/fixtures).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from adversarial_helpers import make_deps

from adapters.llm import FakeLLM
from adapters.qdrant import QdrantStore
from core.contracts import PipelineRequest, run_pipeline
from core.gate import gate as real_gate
from core.settings import get_settings
from test_dedupe import spy  # the gate spy: what the gate was given, and what it kept

PAIR = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "live_live_duplicate_pair.json").read_text()
)
CHUNK_ID = PAIR["chunk_id"]
ID_A, ID_B = PAIR["point_ids"]
QUERY = "review petition allegation land"  # words both passages contain, so the stand-in rater passes both
OTHER = {
    "chunk_id": "KLHC010999992015_004",
    "case_id": "KLHC010999992015",
    "title": "RP/9/2015 of A Vs B",
    "text": "A review petition lies only for an error apparent on the face of the record, and it cannot be used to reargue an allegation already decided on the land and easement claimed.",
    "court": "High Court of Kerala",
}


def _point(pid, score, payload):
    return SimpleNamespace(id=pid, score=score, payload=dict(payload))


class FakeQdrantClient:
    """Answers a query with the two real copies and one different authority, the way
    Qdrant would after A126: separate points, the SAME chunk id, identical text."""

    def __init__(self, order=("a", "b"), scores=(0.61, 0.83), drop_chunk_id=False):
        self.calls = 0
        payload = dict(PAIR["payload"])
        if drop_chunk_id:
            payload.pop("chunk_id")  # the key the first de-duplication rule uses
        pts = {
            "a": _point(ID_A, scores[0], payload),  # the copy from the mismatched model
            "b": _point(ID_B, scores[1], payload),  # the copy from the matching model
        }
        self._points = [pts[k] for k in order] + [_point(7, 0.40, OTHER)]

    async def query_points(self, collection, **kw):
        self.calls += 1
        return SimpleNamespace(points=list(self._points))

    async def scroll(self, collection, **kw):
        """What QdrantStore.get_record asks (limit 1, filter on chunk_id): Qdrant returns
        ONE of the matching points, here whichever comes first."""
        want = kw["scroll_filter"].must[0].match.value
        hit = [p for p in self._points if p.payload.get("chunk_id") == want]
        return hit[: kw.get("limit", 1)], None


def _store(client) -> QdrantStore:
    return QdrantStore(
        get_settings(), sparse_encoder=lambda text: ([1], [1.0]), client=client
    )


def _llm() -> FakeLLM:
    """A scripted writer that quotes a clean span of the real passage as [S1], so the
    stand-in claim check has something to support."""

    def respond(prompt: str, system: str) -> str:
        if prompt.startswith("Turn the user's"):
            return json.dumps({"query": QUERY})
        return "The review petition is filed on the allegation that the Tahsildarhad closed off a way [S1]."

    return FakeLLM(respond)


REQUEST = PipelineRequest("u1", QUERY)  # the stand-in rater scores word overlap with the question


# --- the real mapping: a point id is NOT the record id ------------------------------------
async def test_two_points_with_different_ids_get_the_same_record_id_from_the_real_store():
    hits = await _store(FakeQdrantClient()).search("kanoon_v1", [0.1] * 4, QUERY, {}, 50)
    ids = [h.record_id for h in hits]
    assert ids.count(CHUNK_ID) == 2, ids  # the record id is the chunk id, not the point id
    assert str(ID_A) not in ids and str(ID_B) not in ids
    assert PAIR["cosine_between_copies"] < 0.99  # a different-model pair, as A126 says


# --- step 5 on its own --------------------------------------------------------------------
async def test_search_keeps_one_copy_of_the_pair_and_it_is_the_higher_scoring_one():
    from core.search import search
    from core.contracts import Decision, Filters, RewrittenQuery

    deps = make_deps(vectors=_store(FakeQdrantClient(scores=(0.61, 0.83))))
    rq = RewrittenQuery(query=QUERY)
    res = await search(REQUEST, rq, Decision("in_scope", Filters(), "normal"), [0.1] * 4, deps)
    assert [p.record_id for p in res.passages].count(CHUNK_ID) == 1
    kept = next(p for p in res.passages if p.record_id == CHUNK_ID)
    assert kept.score == 0.83  # the copy that matches the query model usually scores higher
    assert len(res.passages) == 2  # the pair collapsed to one; the other authority is still there


async def test_the_lower_scoring_copy_arriving_first_does_not_win():
    from core.search import search
    from core.contracts import Decision, Filters, RewrittenQuery

    deps = make_deps(vectors=_store(FakeQdrantClient(order=("a", "b"), scores=(0.61, 0.83))))
    rq = RewrittenQuery(query=QUERY)
    res = await search(REQUEST, rq, Decision("in_scope", Filters(), "normal"), [0.1] * 4, deps)
    assert next(p for p in res.passages if p.record_id == CHUNK_ID).score == 0.83


# --- end to end: what reaches the gate ----------------------------------------------------
async def test_only_one_copy_of_a_live_live_pair_reaches_the_gate_and_the_other_authority_is_kept():
    spy_gate, seen = spy()
    deps = make_deps(vectors=_store(FakeQdrantClient()), llm=_llm(), gate=spy_gate)
    res = await run_pipeline(REQUEST, deps)

    assert res.outcome == "answered", res.error
    gate_in = [p.record_id for p in seen["in"]]
    assert gate_in.count(CHUNK_ID) == 1, f"both copies reached the gate: {gate_in}"
    assert OTHER["chunk_id"] in gate_in  # the different authority was not crowded out
    labelled = [(p.source_id, p.record_id) for p in seen["out"]]
    assert len({rid for _, rid in labelled}) == len(labelled), labelled  # no S1 and S4 for one passage
    assert [rid for _, rid in labelled].count(CHUNK_ID) <= 1


async def test_the_second_rule_catches_the_pair_even_if_the_chunk_id_is_missing():
    """Defence in depth: with no chunk_id in the payload the record id falls back to the
    POINT id (different for the two copies), so rule 1 cannot match. Same text inside the
    same case is rule 2, and it does."""
    client = FakeQdrantClient(drop_chunk_id=True)
    hits = await _store(client).search("kanoon_v1", [0.1] * 4, QUERY, {}, 50)
    assert len({h.record_id for h in hits}) == 3  # three distinct record ids: rule 1 is blind here
    spy_gate, seen = spy()
    deps = make_deps(vectors=_store(FakeQdrantClient(drop_chunk_id=True)), llm=_llm(), gate=spy_gate)
    await run_pipeline(REQUEST, deps)  # the answer itself is not the point: with no chunk_id the
    # verifier cannot resolve the record (record_missing), which is correct and not under test
    same_case = [p for p in seen["in"] if p.case_id == PAIR["payload"]["case_id"]]
    assert len(same_case) == 1, [p.record_id for p in seen["in"]]


async def test_the_real_gate_is_what_the_spy_wraps():
    """The spy calls the real gate; it records what went in and what came out."""
    spy_gate, seen = spy()
    deps = make_deps(vectors=_store(FakeQdrantClient()), llm=_llm(), gate=spy_gate)
    await run_pipeline(REQUEST, deps)
    assert seen["in"] and spy_gate is not real_gate


# --- the verifier's lookup: which copy comes back does not matter ----------------------------
async def test_get_record_returns_the_same_text_whichever_copy_qdrant_returns_first():
    """A126 says check 2 resolves a chunk id to one record either way and check 3 matches
    against text that is identical across copies. This is the real QdrantStore.get_record,
    with each copy in turn first."""
    got = []
    for order in (("a", "b"), ("b", "a")):
        rec = await _store(FakeQdrantClient(order=order)).get_record("kanoon_v1", CHUNK_ID)
        got.append(rec)
    assert all(r is not None and r.record_id == CHUNK_ID for r in got)
    assert got[0].text == got[1].text == PAIR["payload"]["text"]
