"""body_section: the section a chunk is about, read from its own first heading (A186)."""

import pytest

from data.body_section import parse_body_section

HEAD = "Act: X | India | Central | In Force\nChapter V: A | Section 3: Wrong label\n"


def p(body, st=None):
    return parse_body_section(HEAD + body, st)


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
        (" XIII. It shall be lawful for the Judge", "XIII"),
    ],
)
def test_a_heading_is_read_with_its_letter_suffix_and_decoration(body, want):
    assert p(body) == (want, "section")


@pytest.mark.parametrize(
    "body",
    [
        " ( _a_ ) the validity of any loan or advance",  # continuation
        " (1) At any time after an arrear",
        " existing sections we have made amendments to meet case law",
        " 1. Ins. by Act 21 of 2021, s. 5 (w.e.f. 23-8-2021).",  # footnote item
        " > 3. The proviso ins. by s. 37, _ibid_ ., (w.e.f. 19-9-2018).",
        ' 16. Section 67—Omit "for a patent"',
        " 27. In section 347, for sub-section ( _1_ ), the following shall be substituted",
        "",
    ],
)
def test_continuations_footnotes_and_amendment_instructions_are_not_sections(body):
    assert p(body) == (None, "none")


def test_orders_rules_and_schedule_articles_are_not_sections():
    assert p("ORDER XXXIX  TEMPORARY INJUNCTIONS  rule 1. Cases in which") == (
        "Order XXXIX Rule 1",
        "order_rule",
    )
    assert (
        p(" **THE FIRST SCHEDULE**\n\n1. Foo") == (None, "schedule")
        or p(" **THE FIRST SCHEDULE**\n\n1. Foo")[1] == "schedule"
    )
    assert p("anything", "schedule")[1] == "schedule"
    assert p(
        " 63. By a mortgagee **—**\n|---|---|\n|(a) for foreclosure|Thirty years|"
    ) == ("Schedule Article 63", "schedule")


def test_a_multi_line_chapter_title_before_the_heading_is_skipped():
    body = "\n## CHAPTER XI\n\n## APPOINTMENT AND QUALIFICATIONS OF DIRECTORS\n\n**149. Company to have Board of Directors.** —( _1_ ) Every"
    assert p(body) == ("149", "section")
    body = "\n## CHAPTER III\n\nINCOMES WHICH DO NOT FORM PART OF TOTAL INCOME\n\n**10. Incomes not included in total income** .—In computing"
    assert p(body) == ("10", "section")


# ---- the payload writer's pure part (data/add_body_section.py) -----------------------------
from data.add_body_section import compute  # noqa: E402


def _pt(i, idx, label, body, **kw):
    pl = {
        "act_id": "A",
        "section_number": label,
        "chunk_index": idx,
        "source_kind": "dataset",
        "section_type": "section",
        "text": HEAD + body,
        **kw,
    }
    return {"id": i, "payload": pl}


def test_a_continuation_inherits_only_from_the_same_label_and_a_judgment_is_skipped():
    pts = [
        _pt(1, 0, "7", "**7. Powers.—** (1) The Board may"),
        _pt(2, 1, "7", "( _a_ ) any other matter"),  # continuation of 7
        _pt(
            3, 2, "8", "( _b_ ) a stray piece under another label"
        ),  # different label: no inheritance
        {"id": 4, "payload": {"chunk_id": "2019_INSC_1_000", "text": "judgment"}},
    ]
    f = compute(pts)
    assert f[1]["body_section"] == "7" and f[1]["series_inherited"] is False
    assert (
        f[2]["body_section"] is None
        and f[2]["series_section"] == "7"
        and f[2]["series_inherited"] is True
    )
    assert f[3]["series_section"] is None and f[3]["series_inherited"] is False
    assert 4 not in f


def test_supplement_chunks_take_their_printed_number():
    base = {
        "act_id": "S",
        "source_kind": "supplement_indiacode",
        "text": "x",
        "chunk_index": 0,
    }
    pts = [
        {
            "id": 1,
            "payload": {**base, "section_type": "section", "section_number": "11"},
        },
        {
            "id": 2,
            "payload": {
                **base,
                "section_type": "rule",
                "section_number": "11",
                "order_number": "VII",
            },
        },
    ]
    f = compute(pts)
    assert (f[1]["body_section"], f[1]["body_kind"]) == ("11", "section")
    assert (f[2]["body_section"], f[2]["body_kind"]) == (
        "Order VII Rule 11",
        "order_rule",
    )


def test_all_headings_finds_a_heading_that_is_not_first_in_the_chunk():
    from data.body_section import all_headings

    text = (
        HEAD
        + "( _8_ ) Every notification shall be laid. **9A. Anti-dumping duty on dumped articles** .—( _1_ ) Where"
    )
    assert all_headings(text, None) == ["9A"]
    text = (
        HEAD
        + "> 7 **—** [ **43. Publication of consolidated statement by the Bank.** The Bank shall"
    )
    assert all_headings(text, None) == ["43"]
    text = (
        HEAD
        + "## CHAPTER VI\n\n## **39. Punishment for failure to register.** —Whoever—"
    )
    assert all_headings(text, None) == ["39"]
    assert all_headings(HEAD + "**12.** Subs. by Act 5 of 1999, s. 3", None) == []
