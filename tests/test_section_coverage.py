"""scan/section_coverage.py: the arithmetic and the guards, on synthetic Acts (the real figures come from the real scan).

What these pin down: N is a lower bound taken from the highest held number that is not a straggler (or a known count), a
year filed as a section number never inflates it, a missing number whose text sits inside the chunk before it is not called
absent, a number shared by three provisions is not credited that way (CPC 9 and 11), and a missing number the Act itself
cites often is flagged foundational.
"""

from __future__ import annotations

from scan import section_coverage as sc


def chunk(n, title="x", text="", typ="section", act="IND_central_1", **kw):
    return {
        "act_id": act,
        "title": kw.get("act_title", "The Test Act, 1950"),
        "act_status": "in_force",
        "section_type": typ,
        "section_number": str(n) if n is not None else "",
        "section_title": title,
        "chunk_id": f"{act}_s{n}",
        "text": text,
    }


def test_robust_max_ignores_an_isolated_straggler_and_base_int_reads_suffixes():
    assert sc.robust_max({1, 2, 3, 4, 5, 6, 137}) == 6
    assert sc.robust_max({5}) == 5 and sc.robust_max(set()) == 0
    assert sc.base_int("376A") == 376 and sc.base_int("abc") is None


def test_title_key_matches_the_known_counts_whatever_the_title_decoration():
    t = "The Indian Penal Code, 45 of 1860 (Rep., Act 45 of 2023)"
    assert sc.title_key(t) == "indian penal code 1860"
    assert sc.title_key("The Limitation Act, 1963") == "limitation act 1963"


def test_a_missing_number_is_counted_and_a_known_count_sets_n():
    rows = [chunk(n) for n in (1, 2, 3, 5, 6, 7, 8, 9)]  # 4 missing, 8 held
    a = sc.analyse_act(rows)
    assert a["expected"] == 9 and a["missing"] == [4] and a["held"] == 8
    known = [chunk(n, act_title="The Limitation Act, 1963") for n in range(1, 11)]
    assert sc.analyse_act(known)["expected"] == 32  # the statutory count, not 10


def test_a_year_filed_as_a_section_number_does_not_inflate_n():
    rows = [chunk(n) for n in (1, 2, 3, 4)] + [chunk(1941)]
    assert sc.analyse_act(rows)["expected"] == 4


def test_text_inside_the_chunk_before_is_not_called_absent():
    body = "**33. Act.** The word act.\n\n> **1[34. Acts done by several persons**.** When a criminal act is done"
    rows = [chunk(n) for n in (30, 31, 32, 35, 36, 37)] + [chunk(33, text=body)]
    a = sc.analyse_act(rows)
    assert (
        34 in a["missing"] and 34 in a["merged"] and 34 not in a["foundational_absent"]
    )
    assert a["likely_absent_n"] == a["missing_n"] - a["merged_n"]


def test_a_number_shared_by_three_provisions_is_never_credited_as_merged():
    rows = [chunk(n) for n in (1, 2, 3, 4, 5, 6, 7, 8, 10, 12)]
    rows += [
        chunk(9, title=t) for t in ("order rule a", "order rule b", "order rule c")
    ]
    assert 9 in sc.analyse_act(rows)["collisions"]


def test_a_missing_number_the_act_cites_often_is_foundational():
    cite = "as provided in section 9 the court may order."
    rows = [
        chunk(n, text=cite if n in (2, 3, 4) else "")
        for n in (1, 2, 3, 4, 5, 6, 7, 8, 10)
    ]
    a = sc.analyse_act(rows)
    assert a["missing"] == [9] and a["foundational_absent"] == [(9, 3)]


def test_no_labels_and_stub_categories():
    blocks = [
        chunk(None, typ="section", text=f"{n}. Heading {n}. Text.")
        for n in range(1, 13)
    ]
    assert sc.analyse_act(blocks)["category"] == "no labels"
    stub = [chunk(60, text="as per section 12, section 40 and section 50.")]
    assert sc.analyse_act(stub)["category"] in ("stub", "labelled")
