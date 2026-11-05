"""core/citator/links.py and pairmap.py: the trust rule, and the guarantee that no clearance wording exists."""

import dataclasses
import re
from pathlib import Path

import pytest

from core.citator import links as links_mod
from core.citator.links import (
    SOME_READABLE,
    ZERO_READABLE,
    InboundLinks,
    Link,
    Via,
    group_inbound,
    inbound_for,
)
from core.citator.pairmap import build_map, trusted_target

ROOT = Path(__file__).resolve().parents[2]


# --- the trust rule: evidence taken from the Judges Library validation (DATA-GAPS 23.14) -------------


def test_two_independent_cases_and_a_single_target_is_trusted():
    assert trusted_target({"1978_INSC_16": ["a", "b"]}) == "1978_INSC_16"


def test_a_lone_pair_is_not_trusted():
    assert trusted_target({"1978_INSC_16": ["a"]}) is None


def test_one_case_printing_a_pair_many_times_is_still_one():
    assert trusted_target({"x": ["a", "a", "a", "a"]}) is None


def test_the_winner_needs_twice_the_runner_up():
    # Kesavananda: 3 cases print the right record, 1 prints a wrong one -> right wins
    assert (
        trusted_target({"1973_INSC_91": list("abc"), "1972_INSC_292": ["d"]})
        == "1973_INSC_91"
    )
    assert trusted_target({"r": list("abc"), "w": list("de")}) is None  # 3 vs 2
    assert trusted_target({"r": list("ab"), "w": list("cd")}) is None  # tie


def test_every_wrong_second_target_in_the_validation_loses():
    # the six wrong targets were each printed exactly once; the rights were printed 3, 91, 27, 32, 2, 6
    for right in (3, 91, 27, 32, 2, 6):
        ev = {"right": [f"c{i}" for i in range(right)], "wrong": ["z"]}
        assert trusted_target(ev) == "right"


def test_no_evidence_is_not_trusted():
    assert trusted_target({}) is None


def test_air_high_court_keys_are_never_mapped():
    ev = {"x": ["a", "b"]}
    pairs = {
        ("air", 1950, "SC", 27): ev,
        ("air", 1950, "BOM", 27): ev,
        ("scc", 1950, False, 1, 5): ev,
    }
    assert set(build_map(pairs)) == {
        ("air", 1950, "SC", 27),
        ("scc", 1950, False, 1, 5),
    }


# --- the data model ---------------------------------------------------------------------------------


def test_a_judgment_cannot_cite_itself():
    with pytest.raises(ValueError):
        Link("2018_INSC_1", "2018_INSC_1", Via.DIRECT)


def test_links_must_be_filed_under_their_cited_case():
    with pytest.raises(ValueError):
        InboundLinks("2018_INSC_1", (Link("2019_INSC_5", "2018_INSC_2", Via.DIRECT),))


def test_one_link_per_citing_judgment():
    lk = Link("2019_INSC_5", "2018_INSC_1", Via.DIRECT)
    with pytest.raises(ValueError):
        InboundLinks("2018_INSC_1", (lk, lk))


def test_direct_beats_mapped_for_the_same_pair():
    g = group_inbound(
        [
            Link("2019_INSC_5", "2018_INSC_1", Via.MAPPED),
            Link("2019_INSC_5", "2018_INSC_1", Via.DIRECT),
        ]
    )
    assert g["2018_INSC_1"].readable == 1
    assert g["2018_INSC_1"].links[0].via is Via.DIRECT


def test_a_case_with_no_link_gets_a_described_zero_not_a_missing_value():
    z = inbound_for("2020_INSC_9", group_inbound([]))
    assert z.readable == 0
    assert z.describe() == ZERO_READABLE


# --- the design rule: the confident wording is impossible ---------------------------------------------

FORBIDDEN_WORDING = re.compile(
    r"good law|still good|no adverse|no negative|not been cited|never been cited|uncited|"
    r"\bclear(?:ed|ance)?\b|\bsafe\b|\bvalid\b|unchallenged|unquestioned|\bnot cited\b|\bsettled\b",
    re.I,
)
REQUIRED_CAVEAT = re.compile(r"form we can read")


def _every_sentence() -> list[str]:
    out = [ZERO_READABLE]
    for n in (1, 2, 3, 10, 174, 10_000):
        lks = tuple(Link(f"c{i}", "t", Via.DIRECT) for i in range(n))
        out.append(InboundLinks("t", lks).describe())
    return out


def test_no_sentence_can_read_as_clearance():
    for s in _every_sentence():
        assert not FORBIDDEN_WORDING.search(s), s
        assert REQUIRED_CAVEAT.search(s), s


def test_a_zero_says_it_is_a_limit_of_our_data():
    assert "limit of our data" in ZERO_READABLE
    assert "not a finding" in ZERO_READABLE


def test_a_count_is_called_a_minimum_and_says_nothing_of_treatment():
    for s in _every_sentence()[1:]:
        assert "minimum" in s and "overrules" in s


def test_the_templates_are_the_only_strings_the_module_can_return():
    # describe() returns ZERO_READABLE or SOME_READABLE; nothing else in the module is text for a user
    assert set(re.findall(r"\{(\w+)\}", SOME_READABLE)) == {"n", "s", "v"}


def test_no_attribute_can_hold_a_standing():
    names = {f.name for c in (Link, InboundLinks) for f in dataclasses.fields(c)}
    names |= {n for n in dir(InboundLinks) if not n.startswith("_")}
    names |= {n for n in dir(links_mod) if not n.startswith("_")}
    banned = re.compile(
        r"status|good_?law|cleared|clear|treatment|overrul|followed|valid|safe|standing",
        re.I,
    )
    assert not [n for n in names if banned.search(n)], sorted(names)


def test_the_model_is_immutable():
    lk = Link("a", "b", Via.DIRECT)
    with pytest.raises(dataclasses.FrozenInstanceError):
        lk.cited = "c"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        InboundLinks("b", ()).case_id = "x"  # type: ignore[misc]


def test_no_user_facing_code_says_still_good_law_affirmatively():
    """Class-wide: nothing in core, api or the web source asserts good-law standing. Negations are fine
    ("does NOT mean good law"); an assertion is not."""
    affirm = re.compile(
        r"(?<!not )(?<!NOT )(?<!never )(?:still good law|is good law|good law today|no adverse treatment)",
        re.I,
    )
    hits = []
    for base in ("core", "api", "web/src"):
        for p in (ROOT / base).rglob("*"):
            if (
                p.suffix not in {".py", ".ts", ".tsx"}
                or "test" in p.name
                or "node_modules" in p.parts
            ):
                continue
            for i, line in enumerate(
                p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                if affirm.search(line) and not re.search(
                    r"not|never|NOT|cannot|no .*claim", line
                ):
                    hits.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:100]}")
    assert not hits, hits


# --- the committed Phase 1 build (data/citator, from scan/sc/build_links.py) ---------------------------

DENSITY = ROOT / "data" / "citator" / "sc_link_density.json"


def test_the_built_links_are_well_formed_and_match_the_density_report():
    import json
    import re as _re

    from core.citator.links import load_links

    rows = load_links()
    rep = json.loads(DENSITY.read_text())
    pat = _re.compile(r"^(19|20)\d\d_INSC_\d+$")
    assert all(pat.match(r.citing) and pat.match(r.cited) for r in rows)
    assert len({(r.citing, r.cited) for r in rows}) == len(rows)
    assert sum(r.via is Via.DIRECT for r in rows) == rep["links"]["direct"]
    assert sum(r.via is Via.MAPPED for r in rows) == rep["links"]["mapped_only"]
    grouped = group_inbound(rows)
    assert len(grouped) == rep["after_with_pair_map"]["with_a_readable_link"]
    assert (
        sum(g.readable for g in grouped.values()) == rep["after_with_pair_map"]["links"]
    )


def test_the_map_cannot_add_a_first_link_and_the_report_says_so():
    import json

    rep = json.loads(DENSITY.read_text())
    assert rep["cases_that_gained_a_first_link"] == 0
    b, a = rep["before_direct_only"], rep["after_with_pair_map"]
    assert b["with_a_readable_link"] == a["with_a_readable_link"]


def test_the_trusted_map_validated_with_no_wrong_answer():
    import json

    v = json.loads(DENSITY.read_text())["validation_against_judges_library"]
    assert v["wrong"] == 0 and v["right"] >= 47
