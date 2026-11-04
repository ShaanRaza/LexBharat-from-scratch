"""DECISIONS A144: the two search defects the fence fix exposed, fixed as classes.

Bug B (step 3, decide): a year that is part of an Act's title ("CrPC 1973") must never
become year_from/year_to. Bug A (step 5, search): a section number is read inside its
own Act, and a search never returns nothing because of a filter it could not scope.

The real figures that motivated this: with the decision layer working, 38 of 100
questions came back not_found, 37 with zero passages, because "section 11" matched 1,413
points across unrelated Acts and the year of the Act excluded the rest.
"""

from __future__ import annotations

import json

import pytest
from core_helpers import make_deps

from adapters.decisions import FakeDecisions, GeminiDecider
from adapters.llm import FakeLLM
from adapters.qdrant import FakeVectorStore
from core import llm_schemas
from core.act_ids import plain_section, resolve_act, year_names_an_act
from core.contracts import (
    SEARCH_TOP_K,
    Decision,
    Filters,
    Passage,
    PipelineRequest,
    RewrittenQuery,
)
from core.decide import decide
from core.gate import gate
from core.search import search
from core.verify import verify

CPC = "IND_central_2191"  # the Code of Civil Procedure, 1908, in the served collection


# ----------------------------------------------------------------------------------------
# Bug B: a year inside an Act's title is not a judgment year
# ----------------------------------------------------------------------------------------
ACT_TITLE_YEARS = [
    # (question, the Act the decider names, the year in its title)
    (
        "What does Section 438 of the Code of Criminal Procedure, 1973 say?",
        "Code of Criminal Procedure, 1973",
        1973,
    ),
    ("Explain CrPC 1973 section 438", "CrPC", 1973),
    (
        "Punishment under the Indian Penal Code, 1860 for murder",
        "Indian Penal Code, 1860",
        1860,
    ),
    ("IPC 1860 section 302", "Indian Penal Code", 1860),
    ("Section 65B of the Indian Evidence Act, 1872", "Indian Evidence Act, 1872", 1872),
    (
        "Consideration under the Indian Contract Act 1872",
        "Indian Contract Act, 1872",
        1872,
    ),
    ("Duties of directors under the Companies Act, 2013", "Companies Act, 2013", 2013),
    (
        "Section 103 of the Bharatiya Nyaya Sanhita, 2023",
        "Bharatiya Nyaya Sanhita, 2023",
        2023,
    ),
    ("BNS 2023 murder", "BNS", 2023),
]


@pytest.mark.parametrize("question,act,year", ACT_TITLE_YEARS)
def test_an_act_title_year_is_never_a_judgment_year(question, act, year):
    assert year_names_an_act(question, year, act)


@pytest.mark.parametrize("question,act,year", ACT_TITLE_YEARS)
async def test_decide_drops_an_act_title_year_however_it_arrived(
    settings, store, question, act, year
):
    """Three ways the year reaches the filters: the decider returns it as a judgment
    year, the rewrite step's regex or model put it in rq.year, or both."""
    wrong = Filters(act=act, year_from=year, year_to=year)

    class Mistaken(FakeDecisions):
        async def decide(self, query, *, uploads=False):
            return Decision("in_scope", wrong, "normal", (), False)

    deps = make_deps(settings, store, gate, verify, decisions=Mistaken())
    d = await decide(RewrittenQuery(question, act=act, year=year), deps)
    assert d.filters.year_from is None and d.filters.year_to is None
    assert d.filters.act == act  # the Act itself is kept; only the year is dropped


async def test_the_rewrite_years_alone_are_also_dropped(settings, store):
    deps = make_deps(settings, store, gate, verify, decisions=FakeDecisions())
    for question, act, year in ACT_TITLE_YEARS:
        d = await decide(RewrittenQuery(question, act=act, year=year), deps)
        assert (d.filters.year_from, d.filters.year_to) == (None, None), question


@pytest.mark.parametrize(
    "question,act,year",
    [
        (
            "Supreme Court judgments after 2015 on section 138 of the Negotiable Instruments Act",
            "Negotiable Instruments Act",
            2015,
        ),
        (
            "Bail decisions in 2019 under section 438 of the Code of Criminal Procedure, 1973",
            "Code of Criminal Procedure, 1973",
            2019,
        ),
        ("Companies Act, 2013 amendments since 2019", "Companies Act, 2013", 2019),
        (
            "Cases decided in 2018 applying the Indian Contract Act, 1872",
            "Indian Contract Act, 1872",
            2018,
        ),
    ],
)
async def test_a_year_the_user_really_wants_judgments_from_is_kept(
    settings, store, question, act, year
):
    deps = make_deps(settings, store, gate, verify, decisions=FakeDecisions())
    d = await decide(RewrittenQuery(question, act=act, year=year), deps)
    assert (d.filters.year_from, d.filters.year_to) == (year, year)


async def test_the_gemini_decider_carries_the_act_year_the_prompt_asks_for(settings):
    reply = {
        "scope": "in_scope",
        "safety": "normal",
        "act": "Code of Criminal Procedure, 1973",
        "act_year": 1973,
        "section": "438",
    }
    llm = FakeLLM(json.dumps(reply))
    d = await GeminiDecider(llm, settings).decide(
        "What does section 438 CrPC 1973 say?"
    )
    assert d.filters.act_year == 1973 and d.filters.year_from is None
    assert llm.schemas == [llm_schemas.DECIDE]
    assert "act_year" in llm_schemas.DECIDE["properties"]


def test_the_prompts_tell_the_model_an_act_title_year_is_not_a_judgment_year():
    from pathlib import Path

    prompts = Path(__file__).resolve().parents[2] / "core" / "prompts"
    decide_txt = (prompts / "decide.txt").read_text()
    assert "act_year" in decide_txt and "NOT a judgment year" in decide_txt
    assert "dates the Act" in (prompts / "rewrite.txt").read_text()


# ----------------------------------------------------------------------------------------
# Bug A: the section filter is scoped to its Act, in layers
# ----------------------------------------------------------------------------------------
@pytest.fixture
def law(settings) -> FakeVectorStore:
    """Section 11 exists in many unrelated Acts (the real collection has 1,413 such
    points), section 438 only in other Acts than the one the user names, and there
    are judgments with years."""
    s = FakeVectorStore(settings)
    s.add_law(
        "cpc-11",
        "res judicata no court shall try any suit",
        act_id=CPC,
        section_number="11",
        title="Code of Civil Procedure, 1908",
        year=1908,
    )
    s.add_law(
        "cpc-9",
        "courts to try all civil suits unless barred",
        act_id=CPC,
        section_number="9",
        title="Code of Civil Procedure, 1908",
        year=1908,
    )
    for i in range(30):  # section 11 of thirty unrelated Acts
        s.add_law(
            f"other-11-{i}",
            f"section eleven of unrelated act {i} res judicata",
            act_id=f"IND_central_9{i:03d}",
            section_number="11",
            title=f"Unrelated Act {i}",
            year=1950 + i,
        )
    s.add_law(
        "ipc-438",
        "other act section 438 text about bail",
        act_id="IND_central_9900",
        section_number="438",
        title="Some Other Act",
        year=1950,
    )
    s.add_law(
        "j-2019",
        "bail anticipatory judgment of the court",
        case_id="J1",
        court="x",
        year=2019,
    )
    s.add_law(
        "j-1973",
        "bail anticipatory judgment from the seventies",
        case_id="J2",
        court="x",
        year=1973,
    )
    s.add_law(
        "j-2010",
        "bail anticipatory judgment from 2010",
        case_id="J3",
        court="x",
        year=2010,
    )
    s.add_law(
        "nia-138",
        "dishonour of cheque for insufficiency of funds",
        act_id="IND_central_2189",
        section_number="138",
        title="The Negotiable Instruments Act, 1881",
        year=1881,
    )
    return s


async def _run(settings, law, filters, query="res judicata"):
    deps = make_deps(settings, law, gate, verify)
    dec = Decision("in_scope", filters, "normal")
    return await search(
        PipelineRequest("u", "x"), RewrittenQuery(query), dec, [0.0], deps
    )


async def test_section_11_is_read_only_in_the_act_the_user_named(settings, law):
    r = await _run(
        settings, law, Filters(act="Code of Civil Procedure, 1908", section="11")
    )
    assert r.scope == "act+section"
    assert [p.record_id for p in r.passages] == ["cpc-11"]  # one point, not thirty-one


async def test_a_resolved_act_with_a_section_it_does_not_have_falls_back_to_the_act(
    settings, law
):
    r = await _run(
        settings, law, Filters(act="Code of Civil Procedure, 1908", section="9999")
    )
    assert r.scope == "act" and r.passages
    assert {p.act_slug for p in r.passages} == {CPC}


async def test_an_act_with_no_section_named_never_scopes_the_search(settings, law):
    """ "Bail under the Negotiable Instruments Act" must still bring the case law about
    it: naming an Act is not a request to read only that Act."""
    r = await _run(
        settings,
        law,
        Filters(act="Negotiable Instruments Act"),
        "bail anticipatory judgment",
    )
    assert r.scope == "unfiltered"
    assert {"j-2019", "j-1973", "j-2010"} <= {p.record_id for p in r.passages}


async def test_an_act_that_does_not_resolve_makes_the_section_a_ranking_signal_not_a_filter(
    settings, law
):
    # the Code of Criminal Procedure, 1973 is not in the served collection: it cannot be scoped
    assert resolve_act("Code of Criminal Procedure, 1973") == ()
    r = await _run(
        settings,
        law,
        Filters(act="Code of Criminal Procedure, 1973", section="438"),
        "bail anticipatory",
    )
    assert r.scope == "section signal"
    ids = {p.record_id for p in r.passages}
    assert "ipc-438" in ids  # the section-number match is in
    assert {
        "j-2019",
        "j-1973",
        "j-2010",
    } <= ids  # and nothing was excluded for lack of it
    assert len(r.passages) <= SEARCH_TOP_K


async def test_a_search_never_returns_nothing_because_of_a_filter_it_could_not_scope(
    settings, law
):
    cases = [
        Filters(
            act="Constitution of India", section="Article 21"
        ),  # not a section, not stored
        Filters(act="Constitution of India", section="Article 14"),
        Filters(act="Code of Civil Procedure, 1908", section="Order VII Rule 11"),
        Filters(
            act="Nonexistent Act", section="777"
        ),  # unresolved act, no such section anywhere
        Filters(section="156(3)"),
        Filters(case_number="CRL.A. 1/2099"),  # no such case
        Filters(
            act="Code of Criminal Procedure, 1973",
            section="438",
            year_from=1973,
            year_to=1973,
        ),
    ]
    for f in cases:
        r = await _run(settings, law, f, "bail anticipatory judgment")
        assert r.passages, f


async def test_a_section_that_is_not_a_plain_number_is_never_a_hard_section_filter(
    settings, law
):
    assert (
        plain_section("Article 21") is None
        and plain_section("Order VII Rule 11") is None
    )
    # resolved Act: the Act alone (the Order is in the Code), never a section filter
    r = await _run(
        settings,
        law,
        Filters(act="Code of Civil Procedure, 1908", section="Order VII Rule 11"),
    )
    assert r.scope == "act" and {p.act_slug for p in r.passages} == {CPC}
    # unresolved Act: nothing to scope to, so the ordinary search
    r = await _run(
        settings, law, Filters(act="Constitution of India", section="Article 21")
    )
    assert r.scope == "unfiltered" and len(r.passages) > 1


async def test_a_case_number_filter_holds_while_it_finds_something(settings):
    s = FakeVectorStore(settings)
    s.add_law(
        "c1", "judgment text one", case_id="A", case_number="W.P. 5/2020", year=2020
    )
    s.add_law(
        "c2", "judgment text two", case_id="B", case_number="W.P. 6/2020", year=2020
    )
    r = await _run(settings, s, Filters(case_number="W.P. 5/2020"), "judgment text")
    assert r.scope == "case number" and [p.record_id for p in r.passages] == ["c1"]


async def test_the_year_filter_dates_judgments_and_never_an_acts_enactment_year(
    settings, law
):
    r = await _run(
        settings,
        law,
        Filters(year_from=2015, year_to=2025),
        "bail anticipatory dishonour cheque",
    )
    ids = {p.record_id for p in r.passages}
    assert "j-2019" in ids  # a judgment in range stays
    assert "j-1973" not in ids and "j-2010" not in ids  # judgments out of range go
    assert "nia-138" in ids  # section 138, enacted 1881, is not a judgment: it stays


def test_the_resolver_never_guesses():
    assert resolve_act("Code of Civil Procedure, 1908") == (CPC,)
    assert resolve_act("CPC") == (CPC,)
    assert (
        resolve_act("Code of Civil Procedure, 1999") == ()
    )  # a year the index does not hold
    assert resolve_act("Constitution of India") == ()
    assert resolve_act(None) == () and resolve_act("") == ()


def test_the_act_index_covers_what_the_served_collection_holds():
    from core.act_ids import load_index

    idx = load_index()
    assert (
        sum(len(v) for v in idx.by_key.values()) == 1568
    )  # data/build_act_ids.py --check keeps it current


def test_every_alias_that_names_a_stored_act_resolves_to_exactly_one():
    from core.act_ids import ALIASES

    missing = []
    for alias in ALIASES:
        got = resolve_act(alias)
        if len(got) != 1:
            missing.append((alias, got))
    # the Code of Criminal Procedure is not in the served collection (DATA-GAPS section 20)
    assert sorted(missing) == [("cr pc", ()), ("crpc", ())]


def test_a_year_is_a_judgment_year_when_nothing_ties_it_to_an_act():
    assert not year_names_an_act("bail decisions in 2019", 2019, None)
    assert not year_names_an_act("FIR 2019 quashing", 2019, None)


def test_passage_type_is_unchanged():
    assert Passage("r", "t").kind == "judgment"
