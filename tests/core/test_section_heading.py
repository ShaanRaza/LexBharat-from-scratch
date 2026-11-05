"""The one parser that reads a section number from a chunk's own heading (core/section_heading.py), pipeline step 5."""

import pytest

from core.section_heading import own_section, parse_heading

HEAD = "Act: X | India | Central | In Force\nChapter V: A | Section 3: Wrong label\n"


def p(body, st=None):
    return parse_heading(HEAD + body, st)


@pytest.mark.parametrize(
    "body,want",
    [
        ("**139. Return of income.—** (1) Every person", "139"),
        (" **115BBB. Tax on income from units** .—(1)", "115BBB"),
        (" > 4[ **2. Definitions.—** In this Act", "2"),
        (" > **2[90. Application to set aside sale.—**", "90"),
        (" 21A. Right to education.—The State", "21A"),
        (" Section 12. Powers.—The Board may", "12"),
        (
            " ## CHAPTER XIV _.—Of Specific Legacies_  **142. Specific legacy defined.—** Where",
            "142",
        ),
    ],
)
def test_a_heading_is_read_with_its_letter_suffix_and_decoration(body, want):
    assert p(body) == (want, "section")


@pytest.mark.parametrize(
    "body",
    [
        " ( _a_ ) the validity of any loan or advance",  # a continuation
        " (1) At any time after an arrear",
        " existing sections we have made amendments to meet case law",
        " 1. Ins. by Act 21 of 2021, s. 5 (w.e.f. 23-8-2021).",  # a footnote item
        " > 3. The proviso ins. by s. 37, _ibid_ ., (w.e.f. 19-9-2018).",
        " 27. In section 347, for sub-section ( _1_ ), the following shall be substituted",
        "",  # no body at all
    ],
)
def test_no_number_when_the_body_does_not_open_with_a_heading(body):
    assert p(body) == (None, "none")


def test_orders_rules_and_schedule_articles_are_kept_apart_from_sections():
    assert p("ORDER XXXIX  TEMPORARY INJUNCTIONS  rule 1. Cases in which") == (
        "Order XXXIX Rule 1",
        "order_rule",
    )
    assert p("anything", "schedule")[1] == "schedule"
    assert p(
        " 63. By a mortgagee **—**\n|---|---|\n|(a) for foreclosure|Thirty years|"
    ) == ("Schedule Article 63", "schedule")


def test_the_label_and_the_header_line_are_never_read():
    # the header says Section 3, the label says 3, the BODY says 139: the body wins
    out = parse_heading(HEAD + "**139. Return of income.—** (1)")
    assert out == ("139", "section")


def test_own_section_prefers_the_payload_field_then_the_supplement_heading_then_the_text():
    body = HEAD + "**139. Return of income.—**"
    # 1. body_section / body_kind, when the collection carries them
    assert own_section({"body_section": "11", "body_kind": "section"}, body) == (
        "11",
        "section",
        "body_section",
    )
    # a continuation: body_section present and empty -> no heading of its own
    assert own_section({"body_section": None}, body)[0] is None
    # 2. a supplement chunk: the Act's own number, Orders apart
    sup = {
        "source_kind": "supplement_indiacode",
        "heading_section": "Order VII Rule 11",
    }
    assert own_section(sup, "") == (
        "Order VII Rule 11",
        "order_rule",
        "heading_section",
    )
    assert own_section(
        {"source_kind": "supplement_indiacode", "heading_section": "115BBB"}, ""
    ) == ("115BBB", "section", "heading_section")
    # 3. the text
    assert own_section({}, body) == ("139", "section", "text")
