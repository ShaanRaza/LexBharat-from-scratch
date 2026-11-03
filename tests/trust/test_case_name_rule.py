"""Verifier check 1, case names: rule f (decisions A116, A117).

A written case name is accepted as retrieved only if EVERY word of it appears, in order,
inside ONE retrieved case name, and at least one word is not generic. These tests fail
if the old test (one word either side of "v") comes back."""

import json
from pathlib import Path

import pytest

import core.verify as v
from core.contracts import Passage
from core.verify import _unretrieved_authority

SMITH = Passage(
    record_id="r1",
    source_id="S1",
    title="SMITH AND CO. versus UNION OF INDIA",
    text="The appeal of Smith and Co. v. Union of India was dismissed with costs.",
)
SARUP = Passage(
    record_id="r2",
    source_id="S1",
    title="M/S. SARUPCHAND HUKAMCHAND & CO. versus UNION OF INDIA AND OTHERS",
    text="The assessee, a firm, challenged the levy.",
)
KERALA = Passage(
    record_id="r3",
    source_id="S1",
    title="STATE OF KERALA versus UNION OF INDIA",
    text="A dispute between the State and the Union.",
)


def flagged(sentence: str, *passages: Passage) -> bool:
    return _unretrieved_authority(sentence, list(passages))


# ---- MUST CATCH ----------------------------------------------------------------------
def test_the_zorblax_case_is_caught():
    """A112: an invented firm sharing only 'Co. v. Union' with a retrieved case."""
    assert flagged(
        "The leading authority is Zorblax Holdings and Co. v. Union of India.", SMITH
    )
    assert flagged(
        "The leading authority is Zorblax Holdings & Co. v. Union of India.", SMITH
    )


@pytest.mark.parametrize(
    "name",
    [
        "Zorblax & Ors. v. State of Kerala",
        "Quillfeather Ltd. v. Union of India",
        "Marmaduke & Anr. v. State of Bihar",
    ],
)
def test_an_invented_name_with_a_realistic_suffix_is_caught(name):
    for p in (SMITH, SARUP, KERALA):
        assert flagged(f"The leading authority is {name}.", p), (name, p.title)


def test_party_swapped_names_are_caught():
    assert flagged("See Union of India v. Smith and Co. on this.", SMITH)
    assert flagged("The point is settled in Union of India v. State of Kerala.", KERALA)


def test_a_swapped_name_the_old_two_word_key_ACCEPTED_is_caught():
    """The old test compared only the words beside the v, so 'Union of India v. State of
    Kerala' passed whenever any retrieved text held 'India v. State' (here, a different
    case). The whole name does not appear, in order, in any one retrieved case name."""
    other = Passage(
        record_id="r5",
        source_id="S2",
        title="RAMAN versus SOMEONE",
        text="The Court also noted Union of India v. State of Bihar in passing.",
    )
    assert flagged(
        "See Union of India v. State of Kerala on this point.", KERALA, other
    )
    assert not flagged(
        "See Union of India v. State of Bihar on this point.", KERALA, other
    )


@pytest.mark.parametrize("name", ["State v. Union", "Union v. State", "State v. State"])
def test_a_name_made_only_of_generic_words_is_caught(name):
    """'State v. Union' names no case; an ordered match would accept it from any longer
    name that contains those words, so only an exact run can verify it."""
    assert flagged(f"The rule comes from {name}.", KERALA, SMITH)


def test_an_invented_name_is_caught_whatever_the_surface_form():
    for written in (
        "Zorblax & Ors. v. State of Kerala",
        "Zorblax And Ors. V. State Of Kerala",
        "zorblax & ors. v. state of kerala",
        "ZORBLAX & ORS. V. STATE OF KERALA",
        "Zorblax & Ors. versus State of Kerala",
    ):
        assert flagged(f"As held in {written}, the point is settled.", KERALA), written


# ---- MUST STILL PASS: legitimate shortenings, which the old test stripped ------------
@pytest.mark.parametrize(
    "written",
    [
        "Smith and Co. v. Union of India",  # in full
        "Smith v. Union of India",  # surname only
        "Smith & Co. v. Union of India",
        "M/s Smith and Co. v. Union of India",
    ],
)
def test_a_legitimate_shortening_of_a_retrieved_case_passes(written):
    assert not flagged(f"The leading authority is {written}.", SMITH), written


def test_dropping_ors_or_the_firm_suffix_still_passes():
    assert not flagged("See Sarupchand Hukamchand v. Union of India.", SARUP)
    assert not flagged("See Sarupchand v. Union of India and Others.", SARUP)
    assert not flagged("See M/s Sarupchand Hukamchand & Co. v. Union of India.", SARUP)


SMITH_CITED = Passage(
    record_id="r1",
    source_id="S1",
    title=SMITH.title,
    text=SMITH.text,
    citation_string="AIR 1960 SC 1",
)


def test_a_name_inside_a_sentence_is_not_stretched_into_the_prose():
    """The name stops at the comma and at a reporter citation; 'the Court' after it is
    not part of it."""
    for s in (
        "In Smith and Co. v. Union of India, the Court held that the levy stood.",
        "Smith and Co. v. Union of India AIR 1960 SC 1 is the authority.",  # cited
        "The Court in Smith and Co. v. Union of India decided it so.",
        "(Smith and Co. v. Union of India) is on point.",
    ):
        assert not flagged(s, SMITH_CITED), s


def test_a_slip_of_a_letter_or_an_abbreviation_still_passes():
    assert not flagged("See Sarupchnad Hukamchand & Co. v. Union of India.", SARUP)
    assert not flagged("See Smith and Company v. Union of India.", SMITH)


def test_a_name_that_appears_in_a_passages_text_passes_even_if_the_title_differs():
    p = Passage(
        record_id="r4",
        source_id="S2",
        title="RAMAN versus SOMEONE ELSE",
        text="The Court followed Ravi Shankar Sharma v. Dinesh Mehta in this respect.",
    )
    assert not flagged("As held in Ravi Shankar Sharma v. Dinesh Mehta, it follows.", p)
    assert flagged("As held in Ravi Shankar Sharma v. Dinesh Verma, it follows.", p)


# ---- the generic list is data, not typed ------------------------------------------
def test_the_generic_word_list_is_derived_from_titles_and_matches_the_file():
    """Regenerate it from the same titles and compare: nobody can widen it by hand."""
    from evals import title_rules as tr
    from evals.title_keys import default_records

    recs = tr.build(default_records())
    derived = sorted(tr.generic_words(recs, 0.01))
    doc = json.loads(Path(v._GENERIC_FILE).read_text())
    assert doc["share"] == 0.01 and doc["words"] == derived
    assert {"state", "union", "ltd", "ors"} <= set(doc["words"])


def test_with_no_generic_list_the_check_fails_closed(monkeypatch):
    """No list would make every word distinctive, so 'State v. Union' would pass."""
    v._generic_words.cache_clear()
    monkeypatch.setattr(v, "_GENERIC_FILE", Path("/nonexistent/generic.json"))
    try:
        with pytest.raises(RuntimeError):
            flagged("The rule comes from Smith v. Jones.", SMITH)
    finally:
        monkeypatch.undo()
        v._generic_words.cache_clear()


def test_the_citation_shape_tests_are_untouched():
    assert flagged("This is settled in AIR 1973 SC 1461 on bail.", SMITH)
    assert flagged("This is settled in (1973) 4 SCC 225 on bail.", SMITH)
    assert flagged("This is settled in MANU/SC/0133/1973 on bail.", SMITH)
    assert flagged("The point arose In re Zorblax Holdings long ago.", SMITH)


def test_stripping_m_s_never_leaves_a_name_unchecked():
    """'M/s' is ignored on the written name, but not when it IS the whole left party:
    that would leave nothing to check and the name would pass unexamined."""
    assert flagged("See M/s v. Others and Union on this point.", SMITH)
    assert flagged("See Messrs v. Zorblax Holdings on this point.", SMITH)


# ---- the digit / punctuation exemption (A120) ----------------------------------------
VELLUM = Passage(
    record_id="r6",
    source_id="S1",
    title="VELLUM LTD versus 1 VEDANTA LIMITED",
    text="The tenancy dispute was decided on the facts.",
)


def test_a_numbered_respondent_is_examined():
    """'X v. 1 Vedanta Limited': a digit on ONE side used to skip the whole name."""
    assert flagged("The leading authority is Zorblax v. 1 Vedanta Limited.", SMITH)
    assert not flagged("The leading authority is Vellum v. 1 Vedanta Limited.", VELLUM)


def test_a_numbered_left_party_is_examined():
    """'Ward No 16 2 v. X': a number before the v used to skip the whole name."""
    assert flagged("See Ward No 16 2 v. Zorblax Holdings on this point.", SMITH)


def test_a_bare_punctuation_side_is_looked_past():
    """'State v. & Ors.': the '&' is skipped and the name is checked from 'Ors.' on.
    It has no distinctive word, so only an exact run in a retrieved name can pass it."""
    assert flagged("The point is settled in State v. & Ors. on bail.", SMITH)
    assert flagged("See Zorblax & v. Ors. on this point.", SMITH)


def test_two_bare_numbers_are_still_not_a_case_name():
    """A number on BOTH sides ('Article 14 v. 19', 'Article 14 v. Article 19') stays
    exempt: that is a comparison of provisions, not a case."""
    assert not flagged("Article 14 v. 19 is a matter of equality in law.", SMITH)
    assert not flagged("Article 14 v. Article 19 is a common framing.", SMITH)
