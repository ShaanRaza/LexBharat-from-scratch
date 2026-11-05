"""High Court identifiers (A124): a neutral citation read from the judgment header,
and a case reference built from fields. Synthetic fixtures: the practice fixtures hold
no High Court record."""

import re

import pytest

import core.hc_citation as hc
from adapters.qdrant import Hit
from core.hc_citation import case_reference, extract_neutral_citation
from core.search import hit_to_passage
from core.settings import Settings

DELHI = "Delhi High Court"
HEADER = "$~\n* IN THE HIGH COURT OF DELHI AT NEW DELHI\n"


def _judgment(header_cite: str = "", body_cite: str = "") -> str:
    head = HEADER + (f"Neutral Citation: {header_cite}\n" if header_cite else "")
    body = "The petitioner relies on the decision reported as " + body_cite + "."
    return head + "x" * 900 + "\n" + (body if body_cite else "No other authority.")


# ---- a neutral citation ------------------------
def test_a_header_neutral_citation_is_extracted():
    r = extract_neutral_citation(_judgment("2021:DHC:1234"), DELHI, "04-03-2021")
    assert (r.citation, r.reason) == ("2021:DHC:1234", "ok")


@pytest.mark.parametrize(
    "cite,court,date",
    [
        ("2022:KER:5678", "Kerala High Court", "2022-07-01"),
        ("2023:DHC:1234-DB", DELHI, "12-01-2023"),
        ("2023:AHC-LKO:123", "Allahabad High Court", "05/02/2023"),
    ],
)
def test_the_variants_are_extracted_exactly_as_printed(cite, court, date):
    assert extract_neutral_citation(HEADER + cite, court, date).citation == cite


def test_a_citation_only_in_the_body_is_NOT_extracted():
    """The trap: the judgment cites another case. The first neutral citation anywhere
    in the text is not necessarily this one's."""
    text = _judgment(body_cite="2021:DHC:9999")
    r = extract_neutral_citation(text, DELHI, "04-03-2021")
    assert (r.citation, r.reason) == (None, "body_only")


def test_a_header_citation_wins_over_a_body_one():
    r = extract_neutral_citation(
        _judgment("2021:DHC:1234", "2021:DHC:9999"), DELHI, "04-03-2021"
    )
    assert r.citation == "2021:DHC:1234"


def test_a_mismatched_year_is_rejected():
    r = extract_neutral_citation(_judgment("2019:DHC:1234"), DELHI, "04-03-2021")
    assert (r.citation, r.reason) == (None, "year_mismatch")


def test_a_mismatched_court_is_rejected():
    r = extract_neutral_citation(_judgment("2021:KER:1234"), DELHI, "04-03-2021")
    assert (r.citation, r.reason) == (None, "court_mismatch")


def test_a_court_that_is_not_a_high_court_is_rejected():
    r = extract_neutral_citation(
        _judgment("2021:DHC:1234"), "Delhi District Court", "04-03-2021"
    )
    assert r.citation is None


def test_an_unknown_code_a_missing_date_or_court_is_rejected_never_guessed():
    assert (
        extract_neutral_citation(_judgment("2021:ZZZ:1"), DELHI, "04-03-2021").reason
        == "unknown_court_code"
    )
    assert extract_neutral_citation(_judgment("2021:DHC:1"), DELHI, "").reason == (
        "no_date"
    )
    assert extract_neutral_citation(
        _judgment("2021:DHC:1"), "", "04-03-2021"
    ).reason == ("no_court")


def test_two_different_citations_in_the_header_are_ambiguous_and_rejected():
    text = HEADER + "Impugned: 2020:DHC:77\nThis: 2021:DHC:1234\n"
    assert extract_neutral_citation(text, DELHI, "04-03-2021").reason == "ambiguous"


def test_a_citation_just_past_the_header_region_is_the_body():
    text = "x" * hc.HEADER_CHARS + " 2021:DHC:1234"
    assert extract_neutral_citation(text, DELHI, "04-03-2021").reason == "body_only"


def test_with_no_court_table_the_check_fails_closed(monkeypatch):
    hc._courts.cache_clear()
    monkeypatch.setattr(hc, "_COURTS_FILE", hc._COURTS_FILE.with_name("absent.json"))
    try:
        with pytest.raises(RuntimeError):
            extract_neutral_citation(_judgment("2021:DHC:1234"), DELHI, "04-03-2021")
    finally:
        monkeypatch.undo()
        hc._courts.cache_clear()


# ---- the case reference ------------------------
def test_a_case_reference_is_built_from_the_three_fields():
    assert case_reference("CRL.A. 123/2019", DELHI, "04-03-2021") == (
        "CRL.A. 123/2019, Delhi High Court, decided 4 March 2021"
    )


@pytest.mark.parametrize(
    "num,court,when",
    [
        ("", DELHI, "04-03-2021"),
        (None, DELHI, "04-03-2021"),
        ("CRL.A. 123/2019", "", "04-03-2021"),
        ("CRL.A. 123/2019", None, "04-03-2021"),
        ("CRL.A. 123/2019", DELHI, ""),
        ("CRL.A. 123/2019", DELHI, "31-02-2021"),
        ("CRL.A. 123/2019", DELHI, "not a date"),
        ("see above", DELHI, "04-03-2021"),  # no digit
        ("123", DELHI, "04-03-2021"),  # no letters
        ("x" * 80 + "1", DELHI, "04-03-2021"),  # too long
        ("CRL.A. 123/2019", "Court 12", "04-03-2021"),
    ],
)
def test_a_record_missing_or_garbling_any_field_emits_nothing(num, court, when):
    assert case_reference(num, court, when) is None


@pytest.mark.parametrize(
    "num", ["2021 DelHC 123", "2021:DHC:123", "AIR 1978 SC 597", "(2019) 4 SCC 12"]
)
def test_a_stored_case_number_that_looks_like_a_citation_emits_nothing(num):
    assert case_reference(num, DELHI, "04-03-2021") is None


def test_a_case_reference_never_looks_like_a_published_citation():
    from core.verify import _CITATION_SHAPES

    for num in ("CRL.A. 123/2019", "W.P.(C) 4567/2020", "FAO 55/2018", "CS(OS) 8/2022"):
        ref = case_reference(num, DELHI, "04-03-2021")
        assert ref and ref.endswith("decided 4 March 2021")
        assert not hc.NEUTRAL.search(ref)
        assert not any(s.search(ref) for s in _CITATION_SHAPES), ref
        assert not re.search(r"\b\d{4}\s+[A-Za-z]+\s+\d+\b", ref), ref  # 2021 DelHC 123


# ---- where it goes: hit_to_passage ------------------------
def _hit(payload, text, cs=0):
    return Hit(
        record_id="hc1",
        text="Case: X v. Y\nSection: BODY\n" + text,
        payload={"char_start": cs, "char_end": cs + len(text), **payload},
    )


def test_a_supreme_court_stored_citation_is_unchanged():
    stored = "[1959] SUPP. 2 S.C.R. 986"
    p = hit_to_passage(
        _hit(
            {
                "citation": stored,
                "court": "Supreme Court of India",
                "case_number": "CA 12/1959",
                "decision_date": "05-05-1959",
            },
            "2021:DHC:1234 appears here",
        )
    )
    assert p.citation_string == stored
    assert p.neutral_citation is None and p.case_reference is None


def test_a_high_court_hit_gets_a_neutral_citation_in_its_own_field():
    p = hit_to_passage(
        _hit(
            {
                "court": DELHI,
                "case_number": "CRL.A. 1/2019",
                "decision_date": "04-03-2021",
            },
            _judgment("2021:DHC:1234"),
        )
    )
    assert p.neutral_citation == "2021:DHC:1234"
    assert p.citation_string is None  # never overloaded
    assert p.case_reference is None  # only when there is no neutral citation


def test_a_high_court_hit_without_one_gets_a_case_reference():
    p = hit_to_passage(
        _hit(
            {
                "court": DELHI,
                "case_number": "CRL.A. 123/2019",
                "decision_date": "04-03-2021",
            },
            _judgment(body_cite="2021:DHC:9999"),
        )
    )
    assert p.neutral_citation is None
    assert p.citation_string is None
    assert p.case_reference == "CRL.A. 123/2019, Delhi High Court, decided 4 March 2021"


def test_a_middle_chunk_never_yields_a_neutral_citation():
    p = hit_to_passage(
        _hit(
            {"court": DELHI, "case_number": "", "decision_date": "04-03-2021"},
            "2021:DHC:1234 " + "x" * 50,
            cs=5000,
        )
    )
    assert p.neutral_citation is None


def test_the_label_is_a_setting_not_code():
    assert "not a published citation" in Settings().CASE_REFERENCE_LABEL
    assert "built from the record" not in open(hc.__file__).read()
