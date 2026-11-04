"""The Act inventory's matching (scan/central_acts_inventory.py): how an Act is found, and how a missing one is classed.
Synthetic titles only; the real counts are in DATA-GAPS section 20."""

from __future__ import annotations

from scan import central_acts_inventory as inv


def test_a_year_quoted_inside_a_repeal_note_does_not_make_an_old_act_look_new():
    acts = {
        "IND_REP_971_1872": {
            "title": "The Indian Evidence Act, 1872, 1 of 1872 (Rep., Act 47 of 2023)",
            "year": "1872",
            "status": "repealed",
            "points": 3,
        }
    }
    assert inv.find(acts, r"indian evidence act", (1872,))
    assert not inv.find(acts, r"indian evidence act", (2023,))


def test_the_year_field_decides_and_the_title_is_read_only_when_it_is_empty():
    acts = {
        "a": {
            "title": "The Widget Act, 1950",
            "year": "None",
            "status": "in_force",
            "points": 1,
        }
    }
    assert inv.find(acts, r"widget act", (1950,))


def test_norm_drops_the_repeal_note_and_punctuation():
    got = inv.norm("The Code of Criminal Procedure, 1973 (Rep., Act 46 of 2023)")
    assert got == "the code of criminal procedure 1973"


def test_missing_acts_are_classed_by_where_they_are_absent():
    one = [("id", {})]
    assert inv.classify(one, one, one) == "present, served"
    assert inv.classify(one, one, []).startswith("INDEXING")
    assert inv.classify(one, [], []).startswith("INDEXING")
    assert inv.classify([], [], []).startswith("ACQUISITION")


def test_the_checklist_has_the_84_statutes_and_the_codes_the_owner_named():
    names = {n for n, _p, _y in inv.CHECKLIST}
    for n in (
        "Code of Criminal Procedure, 1973",
        "Indian Penal Code, 1860",
        "Bharatiya Nyaya Sanhita, 2023",
    ):
        assert n in names
    assert len(inv.CHECKLIST) == 84
