"""The three-way in-force reading (decision A180): repealed on any one of three signals,
in force only on act_status, everything else (and anything unclear) not checked."""

import gzip
import json
from pathlib import Path

import pytest

from core.act_status import count_acts, read_act_status

CLEAN = "The Indian Penal Code, 45 of 1860 (Rep., Act 45 of 2023)"


@pytest.mark.parametrize(
    "act_id,title,status",
    [
        ("IND_central_1", "A Act, 1900", "repealed"),  # act_status alone
        ("IND_central_1", "A Act, 1900", " Repealed "),  # spelling and spaces
        ("IND_REP_659_1860", "A Act, 1860", None),  # the id prefix alone
        ("IND_REP_659_1860_s002", "A Act, 1860", ""),  # a section id works too
        ("IND_central_1", CLEAN, None),  # the title marker alone
        ("IND_central_1", CLEAN + ".", None),  # trailing full stop
        ("IND_central_1", CLEAN, "in_force"),  # disagreement: repealed wins
        ("IND_central_1", "A Act (Rep., Act 5 of 1999)  ", None),
    ],
)
def test_repealed_on_any_one_signal(act_id, title, status):
    assert read_act_status(act_id, title, status).status == "repealed"


@pytest.mark.parametrize("status", ["in_force", "in force", "In Force", "IN-FORCE"])
def test_in_force_only_when_act_status_says_so(status):
    assert read_act_status("IND_central_1", "A Act, 2000", status).status == "in_force"


@pytest.mark.parametrize(
    "status", [None, "", "  ", "spent", "unknown", "in_forcee", 1, True]
)
def test_everything_else_is_not_checked(status):
    assert (
        read_act_status("IND_central_1", "A Act, 2000", status).status == "not_checked"
    )


def test_no_other_signal_makes_an_act_in_force():
    """A real-looking id, a good title and an in_force column are not act_status."""
    for ident in ("IND_central_20062", "IND_state_16719", "", None):
        assert (
            read_act_status(ident, "The Bharatiya Nyaya Sanhita, 2023", None).status
            == "not_checked"
        )


@pytest.mark.parametrize(
    "title",
    [
        "A Act, 2000 (Rep. by Act 5 of 2001)",  # a repeal note we do not parse
        "A Act, 2000 (Repealed)",
        "A Act, 2000 (Rep., Act 5 of 20)",  # bad year
        "A Act, 2000 (Rep., Act of 2001)",  # no number
        "A Act (Rep., Act 5 of 2001) and more words",  # not at the end
        "A Act, 2000 (Rep., Act 5 of 3001)",  # year out of range
    ],
)
def test_an_unclear_repeal_note_is_unknown_not_a_guess_either_way(title):
    # not read as repealed ...
    assert read_act_status("IND_central_1", title, None).status == "not_checked"
    # ... and never allowed to stand as "in force" on the strength of act_status alone
    assert read_act_status("IND_central_1", title, "in_force").status == "not_checked"
    # but the other two signals still win: unclear text does not hide a clear one
    assert read_act_status("IND_REP_1_1900", title, "in_force").status == "repealed"
    assert read_act_status("IND_central_1", title, "repealed").status == "repealed"


def test_a_title_that_merely_contains_the_letters_is_left_alone():
    for t in (
        "The Representation of the People Act, 1951",
        "Repealing and Amending Act, 1950",
    ):
        assert read_act_status("IND_central_1", t, "in_force").status == "in_force"


def test_missing_or_odd_types_never_raise():
    for args in ((None, None, None), (5, 5, 5), ([], {}, ()), ("IND_REP_", b"x", None)):
        read_act_status(*args)


def test_conflict_is_reported_and_basis_lists_the_signals():
    r = read_act_status("IND_REP_1_1900", CLEAN, "in_force")
    assert r.status == "repealed" and r.conflict is True
    assert set(r.basis) == {"id_prefix", "title_marker"}


def test_counts_each_act_once_and_split_three_ways():
    rows = [
        {"act_id": "A", "title": "x", "act_status": "in_force"},
        {
            "act_id": "A",
            "title": "x",
            "act_status": "repealed",
        },  # second row of A: ignored
        {"act_id": "IND_REP_B", "title": "y", "act_status": None},
        {"act_id": "C", "title": CLEAN, "act_status": None},
        {"act_id": "D", "title": "z", "act_status": "repealed"},
        {"act_id": "E", "title": "z", "act_status": None},
        {"act_id": "F", "title": "z (Repealed)", "act_status": "in_force"},
        {"act_id": "IND_REP_G", "title": "z", "act_status": "in_force"},
        {"title": "no id"},
    ]
    c = count_acts(rows)
    assert (c["acts"], c["in_force"], c["repealed"], c["not_checked"]) == (7, 1, 4, 2)
    # A's second row is ignored (first row wins), so only D says repealed by act_status
    assert c["repealed_by_signal"] == {
        "act_status": 1,
        "id_prefix": 2,
        "title_marker": 1,
    }
    assert c["in_force_but_marked_repealed"] == 1 and c["skipped_no_id"] == 1
    assert c["unclear_title_marker"] == 1


def test_the_practice_fixture_reads_as_the_data_says():
    path = Path(__file__).parents[1] / "fixtures/practice/act_sections.jsonl.gz"
    rows = [json.loads(line) for line in gzip.open(path, "rt")]
    c = count_acts(rows)
    assert (c["acts"], c["in_force"], c["repealed"], c["not_checked"]) == (7, 5, 2, 0)
    # the three signals agree on both repealed Acts in the fixture
    assert c["repealed_by_signal"] == {
        "act_status": 2,
        "id_prefix": 2,
        "title_marker": 2,
    }
    assert c["in_force_but_marked_repealed"] == 0
