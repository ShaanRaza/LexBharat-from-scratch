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
def test_in_force_only_when_act_status_says_so_and_the_switch_is_on(status):
    on = read_act_status("IND_central_1", "A Act, 2000", status, show_in_force=True)
    assert on.status == "in_force"


@pytest.mark.parametrize("status", ["in_force", "in force", "In Force", "IN-FORCE"])
def test_the_switch_is_off_by_default_so_nothing_reads_in_force(status):
    """A181: until the count resolves the act_status conflict, never 'in force'."""
    off = read_act_status("IND_central_1", "A Act, 2000", status)
    assert off.status == "not_checked" and off.basis == ("in_force_withheld",)
    # explicit off is the same, and repealed is never hidden by the switch
    assert (
        read_act_status("x", "A", status, show_in_force=False).status == "not_checked"
    )
    assert read_act_status("IND_REP_1", "A", status).status == "repealed"
    assert read_act_status("x", "A", "repealed").status == "repealed"


@pytest.mark.parametrize(
    "flag", [True, "true", "True", " TRUE ", "t", "1", 1, 1.0, "yes"]
)
def test_the_is_repealed_flag_alone_makes_an_act_repealed(flag):
    r = read_act_status("IND_central_1", "A Act, 2000", None, flag)
    assert r.status == "repealed" and r.basis == ("is_repealed",)


@pytest.mark.parametrize(
    "flag", [False, None, "", "false", "False", "0", 0, "no", [], {}]
)
def test_a_false_or_missing_flag_neither_hides_nor_proves_anything(flag):
    assert read_act_status("IND_central_1", "A", None, flag).status == "not_checked"
    # it never makes an Act in force, and never overrides another repealed signal
    assert (
        read_act_status("x", "A", "in_force", flag, show_in_force=True).status
        == "in_force"
    )
    assert read_act_status("IND_REP_1", "A", None, flag).status == "repealed"


def test_the_flag_beats_an_in_force_status_and_is_reported_as_a_conflict():
    r = read_act_status("IND_central_1", "A", "in_force", True, show_in_force=True)
    assert r.status == "repealed" and r.conflict is True and r.basis == ("is_repealed",)


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
    assert (
        read_act_status("IND_central_1", title, "in_force", show_in_force=True).status
        == "not_checked"
    )
    # but the other two signals still win: unclear text does not hide a clear one
    assert (
        read_act_status("IND_REP_1_1900", title, "in_force", show_in_force=True).status
        == "repealed"
    )
    assert read_act_status("IND_central_1", title, "repealed").status == "repealed"


def test_a_title_that_merely_contains_the_letters_is_left_alone():
    for t in (
        "The Representation of the People Act, 1951",
        "Repealing and Amending Act, 1950",
    ):
        assert (
            read_act_status("IND_central_1", t, "in_force", show_in_force=True).status
            == "in_force"
        )


def test_missing_or_odd_types_never_raise():
    for args in ((None, None, None), (5, 5, 5), ([], {}, ()), ("IND_REP_", b"x", None)):
        read_act_status(*args)


def test_conflict_is_reported_and_basis_lists_the_signals():
    r = read_act_status("IND_REP_1_1900", CLEAN, "in_force", show_in_force=True)
    assert r.status == "repealed" and r.conflict is True
    assert set(r.basis) == {"id_prefix", "title_marker"}


def test_counts_each_act_once_and_report_what_the_switch_withholds():
    rows = [
        {"act_id": "IND_central_A", "title": "x", "act_status": "in_force"},
        {"act_id": "IND_central_A", "title": "x", "act_status": "repealed"},  # ignored
        {"act_id": "IND_REP_B", "title": "y", "act_status": None},
        {"act_id": "IND_central_C", "title": CLEAN, "act_status": None},
        {"act_id": "IND_central_D", "title": "z", "act_status": "repealed"},
        {"act_id": "IND_state_E", "title": "z", "act_status": None},
        {"act_id": "IND_state_F", "title": "z (Repealed)", "act_status": "in_force"},
        {"act_id": "IND_REP_G", "title": "z", "act_status": "in_force"},
        {"act_id": "IND_central_H", "title": "z", "act_status": None,
         "is_repealed": True},
        {"act_id": "IND_state_I", "title": "z", "act_status": "in_force",
         "is_repealed": False},
        {"title": "no id"},
    ]  # fmt: skip
    c = count_acts(rows)  # the switch is off
    assert c["acts"] == 9
    assert c["shown"] == {"repealed": 5, "in_force": 0, "not_checked": 4}
    assert c["withheld_in_force"] == 2  # A and I would read in force with the switch on
    assert c["repealed_by_signal"] == {
        "act_status": 1, "is_repealed": 1, "id_prefix": 2, "title_marker": 1,
    }  # fmt: skip
    assert c["is_repealed_flag"] == {"missing": 7, "true": 1, "false": 1}
    assert c["in_force_but_marked_repealed"] == 1 and c["skipped_no_id"] == 1
    assert c["unclear_title_marker"] == 1
    assert c["act_status_values"] == {"(empty)": 4, "in_force": 4, "repealed": 1}
    assert c["by_id_kind"]["state"] == {"in_force": 2, "(empty)": 1}
    on = count_acts(rows, show_in_force=True)
    assert on["shown"] == {"repealed": 5, "in_force": 2, "not_checked": 2}


def test_the_flag_agreeing_with_the_other_signals_is_measured():
    rows = [
        {"act_id": "IND_REP_1", "title": "x", "act_status": "repealed",
         "is_repealed": True},
        {"act_id": "IND_REP_2", "title": "x", "act_status": "repealed",
         "is_repealed": False},
        {"act_id": "IND_central_3", "title": "x", "act_status": None,
         "is_repealed": True},
    ]  # fmt: skip
    c = count_acts(rows)
    assert c["repealed_by_other_signal_but_flag_not_true"] == 1


def test_the_practice_fixture_reads_as_the_data_says():
    path = Path(__file__).parents[1] / "fixtures/practice/act_sections.jsonl.gz"
    rows = [json.loads(line) for line in gzip.open(path, "rt")]
    c = count_acts(rows)
    assert c["acts"] == 7
    assert c["shown"] == {"repealed": 2, "in_force": 0, "not_checked": 5}
    assert c["withheld_in_force"] == 5
    # all four repeal signals agree on both repealed Acts in the fixture, and the flag
    # missed none of them
    assert c["repealed_by_signal"] == {
        "act_status": 2, "is_repealed": 2, "id_prefix": 2, "title_marker": 2,
    }  # fmt: skip
    assert c["repealed_by_other_signal_but_flag_not_true"] == 0
    assert c["in_force_but_marked_repealed"] == 0
