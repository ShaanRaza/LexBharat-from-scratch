"""A128: the per-court embedding-model config. Pipeline step 5 (Search).

The corpus is embedded by three Voyage models, by court. A query is embedded once per model
and each vector is searched only among the courts that model built, as one dense prefetch
each in the SAME Qdrant call as the keyword half. Checked here: the registry (built from a
measured sample, nothing defaulted), the settings that resolve a court to a model, the planner,
the per-model query embedding, and the shape of the one Qdrant call. No live Qdrant or Voyage.

Not covered here, on purpose: how well rank fusion over several dense lists retrieves (that
needs a mixed corpus and is not measured; see DECISIONS A131) and latency at scale.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from adapters.qdrant import (
    DENSE_VECTOR,
    SPARSE_VECTOR,
    DenseGroup,
    QdrantStore,
    QueryVectors,
)
from adapters.voyage import FakeEmbedder, VoyageUnavailable
from core import court_id, model_plan
from core.search import embed_query
from core.settings import Settings, UnknownEmbeddingModel
from data import build_court_models

RAW = json.loads(build_court_models.OUT.read_text())
V2 = "legal_corpus_v2"
V1 = "legal_corpus_v1"
MODELS = {"voyage-4", "voyage-4-lite", "voyage-4-large"}


def _settings(**over) -> Settings:
    return Settings(_env_file=None, **over)


# --- the registry ---------------------------------------------------------------------------
def test_the_registry_is_what_the_builder_makes_from_the_committed_sample():
    assert (
        json.dumps(build_court_models.build(), indent=1) + "\n"
        == build_court_models.OUT.read_text()
    )


def test_every_registered_code_is_a_known_court_prefix_and_every_model_is_one_of_three():
    known = set(court_id.load().by_code)
    for name, col in RAW["collections"].items():
        for code, c in col["courts"].items():
            assert code in known, (name, code)
            assert c["model"] in MODELS
        assert set(col["courts"]).isdisjoint(col["not_registered"])
        assert (
            set(col["courts"]) | set(col["not_registered"]) == known
        )  # every code is one or the other


def test_a_court_is_registered_only_with_a_sample_and_a_unique_majority():
    for col in RAW["collections"].values():
        for code, c in col["courts"].items():
            s = c["sample"]
            assert s["n"] >= RAW["min_sample"], code
            assert s["voyage-4"] + s["voyage-4-lite"] + s["voyage-4-large"] == s["n"]
            top = sorted((s[m] for m in MODELS), reverse=True)
            assert top[0] > top[1], f"{code}: a tie is refused, not broken"
            assert s[c["model"]] == top[0] and c["outside_majority"] == s["n"] - top[0]


def test_the_measured_mismatch_share_is_the_one_a128_cites():
    """7.6% of sampled chunks sit outside their court's majority model (DATA-GAPS 13)."""
    outside = n = 0
    for col in RAW["collections"].values():
        for c in col["courts"].values():
            outside += c["outside_majority"]
            n += c["sample"]["n"]
    assert 0.07 < outside / n < 0.085, outside / n


def test_the_courts_the_data_says_are_single_model_resolve_to_that_model():
    s = _settings()
    assert s.embed_model_for(V2, "INSC") == "voyage-4-large"  # 23 of 23
    assert s.embed_model_for(V2, "KLHC") == "voyage-4"  # 83% voyage-4
    assert s.embed_model_for(V2, "JHHC") == "voyage-4-large"  # 0 of 54 are voyage-4
    assert s.embed_model_for(V1, "HCBM") == "voyage-4"
    assert (
        s.embed_model_for(V2, "HCBM") == "voyage-4-lite"
    )  # the same court, the other collection


# --- settings: nothing is defaulted ---------------------------------------------------------
def test_a_collection_with_one_recorded_model_ignores_the_per_court_table():
    s = _settings()
    assert s.embed_model_for("kanoon_v1") == "voyage-4-large"
    assert (
        s.embed_model_for("kanoon_v1", "KLHC") == "voyage-4-large"
    )  # a court code changes nothing


def test_a_per_court_collection_must_be_asked_about_a_court():
    with pytest.raises(UnknownEmbeddingModel):
        _settings().embed_model_for(V2)


@pytest.mark.parametrize("code", ["WBCHCP", "XXHC", "", "NCLT", "kerala"])
def test_a_court_or_source_that_is_not_registered_is_refused_never_defaulted(code):
    with pytest.raises(UnknownEmbeddingModel):
        _settings().embed_model_for(V2, code)


def test_a_collection_nobody_recorded_is_still_refused():
    for name in ("acts_india", "user_documents", "kerala_v2_fix_typo", ""):
        with pytest.raises(UnknownEmbeddingModel):
            _settings().embed_model_for(name, "KLHC")


def test_an_explicit_collection_override_beats_the_per_court_table():
    s = _settings(VOYAGE_EMBED_MODELS={V1: "voyage-4"})
    assert (
        s.embed_model_for(V1) == "voyage-4"
    )  # the measurement path (evals) keeps working
    assert model_plan.plan_for(s, V1) is None


def test_the_table_can_be_replaced_from_the_environment(monkeypatch):
    monkeypatch.setenv(
        "VOYAGE_COURT_MODELS",
        json.dumps({"launch": {"INSC": "voyage-4-large", "KLHC": "voyage-4"}}),
    )
    s = Settings(_env_file=None)
    assert s.embed_model_for("launch", "KLHC") == "voyage-4"
    with pytest.raises(UnknownEmbeddingModel):
        s.embed_model_for(V2, "KLHC")  # replaced, not merged


# --- the planner -----------------------------------------------------------------------------
def test_a_single_model_collection_has_no_plan_so_nothing_changes():
    assert model_plan.plan_for(_settings(), "kanoon_v1") is None
    assert model_plan.plan_for(_settings(), "never-recorded") is None


def test_the_plan_is_one_group_per_model_and_every_court_is_in_exactly_one():
    plan = model_plan.plan_for(_settings(), V2)
    assert {g.model for g in plan} == MODELS and len(plan) == 3
    seen = [c for g in plan for c in g.codes]
    assert sorted(seen) == sorted(RAW["collections"][V2]["courts"]) and len(
        seen
    ) == len(set(seen))
    for g in plan:
        assert all(_settings().embed_model_for(V2, c) == g.model for c in g.codes)
        assert list(g.codes) == sorted(g.codes) and g.embed_code == g.codes[0]
    assert [len(g.codes) for g in plan] == sorted(
        (len(g.codes) for g in plan), reverse=True
    )


def test_records_with_no_court_are_a_registered_group_of_their_own():
    s = _settings(
        VOYAGE_COURT_MODELS={
            "launch": {
                "INSC": "voyage-4-large",
                "NO_COURT": "voyage-4-large",
                "KLHC": "voyage-4",
            }
        }
    )
    plan = model_plan.plan_for(s, "launch")
    big = next(g for g in plan if g.model == "voyage-4-large")
    assert big.codes == ("INSC",) and big.no_court is True
    assert s.embed_model_for("launch", big.embed_code) == "voyage-4-large"
    only_acts = model_plan.plan_for(
        _settings(VOYAGE_COURT_MODELS={"x": {"NO_COURT": "voyage-4"}}), "x"
    )
    assert (
        only_acts[0].codes == ()
        and only_acts[0].no_court
        and only_acts[0].embed_code == "NO_COURT"
    )


def test_codes_present_in_a_collection_but_not_registered_are_reported():
    s = _settings()
    present = {"KLHC": 3_000_000, "WBCHCP": 7_908, "": 74_484, "NCLT": 5}
    assert model_plan.unregistered(s, V2, present) == {
        "WBCHCP": 7_908,
        "NO_COURT": 74_484,
        "NCLT": 5,
    }
    assert (
        model_plan.unregistered(s, "kanoon_v1", present) == {}
    )  # single-model: nothing to register


# --- embedding the query: once per model, concurrently ---------------------------------------
class Recorder:
    """An embedder that records what it was asked and answers a vector named by the model."""

    def __init__(self, settings, down_for=()):
        self.s, self.calls, self.down_for, self.in_flight, self.peak = (
            settings,
            [],
            set(down_for),
            0,
            0,
        )

    async def embed(self, text, collection, input_type, *, court_code=None):
        model = self.s.embed_model_for(
            collection, court_code
        )  # refuses what the adapter refuses
        self.calls.append((text, collection, input_type, court_code, model))
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        await asyncio.sleep(0)
        self.in_flight -= 1
        if model in self.down_for:
            raise VoyageUnavailable("down")
        return [float(len(model))]


def _deps(collection, embedder, settings):
    return SimpleNamespace(
        embedder=embedder,
        settings=settings.model_copy(update={"CORPUS_COLLECTION": collection}),
    )


async def test_a_single_model_collection_is_embedded_once_as_before():
    s = _settings()
    rec = Recorder(s)
    out = await embed_query("bail", _deps("kanoon_v1", rec, s))
    assert out == [float(len("voyage-4-large"))] and len(rec.calls) == 1
    assert rec.calls[0][2:4] == ("query", None)  # a query, and no court named


async def test_a_per_court_collection_is_embedded_once_per_model_concurrently():
    s = _settings()
    rec = Recorder(s)
    out = await embed_query("bail", _deps(V2, rec, s))
    assert isinstance(out, QueryVectors) and len(out.groups) == 3
    assert sorted(c[4] for c in rec.calls) == sorted(MODELS) and all(
        c[2] == "query" for c in rec.calls
    )
    assert (
        rec.peak == 3
    )  # all three were in flight together: the cost is the slowest, not the sum
    for g in out.groups:  # each group carries the vector of ITS model and ITS courts
        assert g.vector == [float(len(s.embed_model_for(V2, g.codes[0])))]
        assert all(
            s.embed_model_for(V2, c) == s.embed_model_for(V2, g.codes[0])
            for c in g.codes
        )


async def test_any_model_being_down_means_keyword_only_not_a_half_matched_search():
    s = _settings()
    assert (
        await embed_query("bail", _deps(V2, Recorder(s, down_for={"voyage-4-lite"}), s))
        is None
    )
    assert (
        await embed_query(
            "bail", _deps("kanoon_v1", Recorder(s, down_for={"voyage-4-large"}), s)
        )
        is None
    )


async def test_an_unregistered_court_is_an_error_not_an_outage():
    s = _settings(VOYAGE_COURT_MODELS={"launch": {"KLHC": "voyage-4"}})
    bad = _settings(
        VOYAGE_COURT_MODELS={"launch": {"KLHC": "voyage-4"}}, VOYAGE_EMBED_MODELS={}
    )
    rec = Recorder(bad)
    deps = _deps("launch", rec, s)
    deps.embedder = rec
    ok = await embed_query("bail", deps)
    assert isinstance(ok, QueryVectors)
    # a plan that names a code the embedder's settings do not know: raised, not swallowed
    rec2 = Recorder(_settings(VOYAGE_COURT_MODELS={"launch": {}}))
    with pytest.raises(UnknownEmbeddingModel):
        await embed_query("bail", _deps("launch", rec2, s))


async def test_the_real_fake_embedder_and_the_pipeline_default_still_work():
    s = _settings()
    out = await embed_query("bail", _deps("kanoon_v1", FakeEmbedder(), s))
    assert isinstance(out, list) and len(out) == 64


# --- the Qdrant call ------------------------------------------------------------------------------
def _point(i):
    return SimpleNamespace(id=i, score=0.5, payload={"chunk_id": f"c{i}", "text": "t"})


class FakeClient:
    def __init__(self):
        self.queries, self.scrolls = [], []

    async def query_points(self, collection, **kw):
        self.queries.append((collection, kw))
        return SimpleNamespace(points=[_point(1)])

    async def scroll(self, collection, **kw):
        self.scrolls.append((collection, kw))
        return [_point(2)], None


def _store(client):
    return QdrantStore(
        Settings(_env_file=None), sparse_encoder=lambda t: ([1], [1.0]), client=client
    )


def _qv():
    return QueryVectors(
        (
            DenseGroup([1.0, 0.0], ("APHC", "BRHC")),
            DenseGroup([0.0, 1.0], ("KLHC",)),
            DenseGroup([0.5, 0.5], ("INSC",), no_court=True),
        )
    )


def _codes(flt):
    for c in flt.must:
        if getattr(c, "key", None) == "court_code":
            return sorted(c.match.any)
        if getattr(c, "should", None):
            return sorted(
                next(
                    x for x in c.should if getattr(x, "key", None) == "court_code"
                ).match.any
            )
    return None


async def test_several_models_are_still_one_qdrant_call_with_a_dense_prefetch_each():
    c = FakeClient()
    await _store(c).search(V2, _qv(), "bail", {}, 50)
    assert len(c.queries) == 1 and not c.scrolls  # no extra round trips
    (_, kw) = c.queries[0]
    dense = [p for p in kw["prefetch"] if p.using == DENSE_VECTOR]
    sparse = [p for p in kw["prefetch"] if p.using == SPARSE_VECTOR]
    assert (
        len(dense) == 3
        and len(sparse) == 1
        and kw["query"].fusion.value == "rrf"
        and kw["limit"] == 50
    )
    assert [p.query for p in dense] == [
        [1.0, 0.0],
        [0.0, 1.0],
        [0.5, 0.5],
    ]  # each vector with ITS courts
    assert [_codes(p.filter) for p in dense] == [["APHC", "BRHC"], ["KLHC"], ["INSC"]]
    assert (
        sparse[0].filter.must == []
    )  # the keyword half is not restricted by court code


def _all_code_lists(flt):
    """Every court_code list anywhere in a filter, however nested."""
    out = []
    for c in list(getattr(flt, "must", None) or []) + list(
        getattr(flt, "should", None) or []
    ):
        if hasattr(c, "should") or hasattr(c, "must"):
            out += _all_code_lists(c)
        elif getattr(c, "key", None) == "court_code":
            out.append(sorted(c.match.any))
    return out


async def test_the_group_filter_is_added_to_the_callers_filter_not_in_place_of_it():
    c = FakeClient()
    await _store(c).search(V2, _qv(), "bail", {"court": "High Court of Kerala"}, 50)
    (_, kw) = c.queries[0]
    groups = [["APHC", "BRHC"], ["KLHC"], ["INSC"]]
    for p, g in zip([p for p in kw["prefetch"] if p.using == DENSE_VECTOR], groups):
        assert (
            len(p.filter.must) == 2
        )  # the caller's court-label branch AND the group's courts
        lists = _all_code_lists(p.filter)
        assert (
            g in lists and ["KLHC"] in lists
        )  # the label branch brings KLHC; the group brings its own


async def test_the_no_court_group_also_matches_records_with_no_court_code():
    from qdrant_client import models

    c = FakeClient()
    await _store(c).search(V2, _qv(), "bail", {}, 50)
    (_, kw) = c.queries[0]
    last = [p for p in kw["prefetch"] if p.using == DENSE_VECTOR][2]
    (nested,) = last.filter.must
    kinds = {type(x) for x in nested.should}
    assert kinds == {
        models.FieldCondition,
        models.IsEmptyCondition,
    }  # the courts OR no court code at all


async def test_one_unrestricted_vector_is_the_ordinary_search_unchanged():
    c = FakeClient()
    await _store(c).search("kanoon_v1", [0.1, 0.2], "bail", {}, 50)
    (_, kw) = c.queries[0]
    assert [p.using for p in kw["prefetch"]] == [DENSE_VECTOR, SPARSE_VECTOR]
    assert kw["prefetch"][0].filter.must == []  # no court restriction


async def test_voyage_down_runs_the_keyword_half_alone_even_for_a_per_court_collection():
    c = FakeClient()
    await _store(c).search(V2, None, "bail", {}, 50)
    (_, kw) = c.queries[0]
    assert [p.using for p in kw["prefetch"]] == [SPARSE_VECTOR]


async def test_dense_only_with_several_models_fuses_the_groups_by_rank_without_the_keyword_half():
    c = FakeClient()
    await _store(c).search(V2, _qv(), "bail", {}, 20, mode="dense")
    (_, kw) = c.queries[0]
    assert [p.using for p in kw["prefetch"]] == [DENSE_VECTOR] * 3 and kw[
        "query"
    ].fusion.value == "rrf"
    c2 = FakeClient()
    await _store(c2).search(
        V2, QueryVectors((DenseGroup([1.0], ("KLHC",)),)), "bail", {}, 20, mode="dense"
    )
    (_, kw2) = c2.queries[0]
    assert (
        "prefetch" not in kw2
        and kw2["using"] == DENSE_VECTOR
        and _codes(kw2["query_filter"]) == ["KLHC"]
    )


async def test_sparse_only_ignores_the_model_groups():
    c = FakeClient()
    await _store(c).search(V2, _qv(), "bail", {}, 20, mode="sparse")
    (_, kw) = c.queries[0]
    assert kw["using"] == SPARSE_VECTOR and "prefetch" not in kw


async def test_a_named_section_with_several_models_is_one_call_ranked_by_stored_order():
    """Not verified for ranking quality: with several models there is no single vector."""
    c = FakeClient()
    await _store(c).search(V2, _qv(), "x", {"section_number": "302"}, 20)
    assert not c.queries and len(c.scrolls) == 1
    c2 = FakeClient()
    await _store(c2).search(
        V2, QueryVectors((DenseGroup([1.0, 2.0]),)), "x", {"section_number": "302"}, 20
    )
    (_, kw) = c2.queries[0]
    assert kw["using"] == DENSE_VECTOR and kw["query"] == [
        1.0,
        2.0,
    ]  # one group: ranked as before


# --- the adapter asks for the right model per court ---------------------------------------------------
async def test_the_adapter_embeds_a_court_with_that_courts_model_and_requires_input_type():
    import httpx

    from adapters.voyage import VoyageClient

    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "data": [{"index": 0, "embedding": [0.1]}],
                "usage": {"total_tokens": 1},
            },
        )

    c = VoyageClient(
        Settings(_env_file=None, VOYAGE_API_KEY="k"),
        transport=httpx.MockTransport(handler),
    )
    await c.embed("q", V2, "query", court_code="KLHC")
    await c.embed("q", V2, "query", court_code="JHHC")
    assert [b["model"] for b in sent] == ["voyage-4", "voyage-4-large"] and {
        b["input_type"] for b in sent
    } == {"query"}
    with pytest.raises(UnknownEmbeddingModel):
        await c.embed("q", V2, "query", court_code="WBCHCP")
    with pytest.raises(UnknownEmbeddingModel):
        await c.embed("q", V2, "query")  # a per-court collection needs a court
    with pytest.raises(TypeError):
        await c.embed("q", V2, court_code="KLHC")  # type: ignore[call-arg]
    assert len(sent) == 2  # nothing was sent for the refused calls
