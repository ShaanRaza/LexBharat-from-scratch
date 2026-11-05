"""Verifier check 1 and the neutral citations (A125).

A124 put neutral citations (2023:DHC:4567) on Passage. The verifier had no shape for
them, so a recalled one was never checked, and its haystack lacked the field they live
in, so a genuine one would have been removed. Two halves; these tests need both."""

import pytest

from core.contracts import Passage
from core.verify import _unretrieved_authority, verify
from tests.trust.conftest import JUDGMENT_TEXT

# A High Court passage as hit_to_passage builds it: the header is stripped from text,
# so the neutral citation is ONLY in its own field.
HC = Passage(
    record_id="hc-1",
    source_id="S1",
    text="The Court held that the notice was invalid for want of service.",
    title="RAMESH versus STATE",
    neutral_citation="2021:DHC:1234",
    case_reference="CRL.A. 123/2019, Delhi High Court, decided 4 March 2021",
)
SC = Passage(
    record_id="sc-1",
    source_id="S2",
    text="Bail is the rule and jail the exception.",
    title="GURBAKSH SINGH SIBBIA versus STATE OF PUNJAB",
    citation_string="[1980] 3 S.C.R. 383",
)


def _hc_in_world() -> Passage:
    """HC, but its record is one the fake store holds (rec-1)."""
    return Passage(
        record_id="rec-1",
        source_id="S1",
        text=JUDGMENT_TEXT,
        title="A versus B",
        neutral_citation="2021:DHC:1234",
    )


def flagged(sentence: str, *passages: Passage) -> bool:
    return _unretrieved_authority(sentence, list(passages))


# ---- half 1: the shape ---------------------------------------------------------------
@pytest.mark.parametrize(
    "written",
    [
        "The point is settled in 2023:DHC:4567.",
        "The point is settled in 2023:dhc:4567.",  # recalled in lower case
        "The point is settled in 2023 : DHC : 4567.",  # spaces around the colons
        "The point is settled in 2022:KER:5678.",
        "The point is settled in 2023:AHC-LKO:123.",
    ],
)
def test_a_fabricated_neutral_citation_is_caught(written):
    assert flagged(written, HC, SC)


def test_a_neutral_citation_that_is_a_prefix_of_a_real_one_is_caught():
    """'2021:DHC:123' is a substring of the genuine '2021:DHC:1234'."""
    assert flagged("See 2021:DHC:123 on this.", HC)


async def test_a_fabricated_neutral_citation_is_removed_and_logged(world):
    world.passages = [_hc_in_world()]
    text = "Bail is the rule and jail the exception, see 2023:DHC:9999 [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert "2023:DHC:9999" not in ans.text
    assert ans.citations == ()
    assert [r.reason for _, _, r in world.citation_log.rows] == ["not_retrieved"]


async def test_a_genuine_neutral_citation_survives_the_whole_verifier(world):
    world.passages = [_hc_in_world()]
    text = "Bail is the rule and jail the exception, reported as 2021:DHC:1234 [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert "2021:DHC:1234" in ans.text
    assert [c.source_id for c in ans.citations] == ["S1"]
    assert world.citation_log.rows == []


# ---- half 2: the haystack ------------------------------------------------------------
def test_a_genuine_neutral_citation_from_a_retrieved_passage_survives():
    """Its text has no header, so the field is the only place it lives."""
    assert "2021" not in HC.text
    assert not flagged("The decision is reported as 2021:DHC:1234.", HC)
    assert not flagged("The decision is reported as 2021:dhc:1234.", HC)
    assert not flagged("The decision is reported as 2021 : DHC : 1234.", HC)


def test_the_bench_suffix_does_not_make_a_genuine_citation_fail():
    assert not flagged("See 2021:DHC:1234-DB on this.", HC)


def test_a_neutral_citation_in_a_retrieved_passages_own_text_survives():
    p = Passage(
        record_id="hc-2",
        source_id="S1",
        text="Following 2020:KER:77, the petition is allowed.",
    )
    assert not flagged("The court followed 2020:KER:77 here.", p)


def test_a_case_reference_can_be_repeated_but_is_not_a_citation_shape():
    assert not flagged(
        "It is CRL.A. 123/2019, Delhi High Court, decided 4 March 2021.", HC
    )
    # nothing in the label is treated as a recalled citation, so a made-up reference
    # is not flagged for its shape
    assert not flagged(
        "It is CRL.A. 999/2020, Delhi High Court, decided 1 May 2022.", HC
    )


# ---- unchanged ---------------------------------------------------------------------
def test_a_stored_supreme_court_citation_is_unchanged():
    assert not flagged("It is reported as [1980] 3 S.C.R. 383.", SC)
    assert flagged("It is reported as [1980] 3 S.C.R. 999.", SC)
    assert flagged("This is settled in AIR 1973 SC 1461 on bail.", SC)
    assert not flagged("Bail is the rule, as the Court said.", SC)
