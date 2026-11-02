"""The dataset's status tail on an Act point's header never reaches the model (A105).

CLAUDE.md section 6: "in force" is not shown until the act_status conflict is settled.
The stored Act text opens "Act: <title> | India | Central | In Force"; Act points
carry no char_start/char_end, so the tail is matched and removed, not sliced off."""

import gzip
import json
import re
from pathlib import Path

import pytest

from adapters.qdrant import Hit
from core.search import hit_to_passage, strip_act_header_status
from tests.core.conftest import PRACTICE

ROOT = Path(__file__).resolve().parents[2]
STATUS = re.compile(r"in force|repealed|\|\s*india|\|\s*central|\|\s*state", re.I)
ACT = (
    "Act: The Negotiable Instruments Act, 1881 (Act 26 of 1881)"
    " | India | Central | In Force\n"
    "Chapter II: OF NOTES, BILLS AND CHEQUES | Section 6: Cheque\n\n"
    "**6. Cheque.** A cheque is a bill of exchange drawn on a specified banker."
)


def _act_hit(text: str = ACT) -> Hit:
    return Hit("IND_x_s6", text, 0.5, {"chunk_id": "IND_x_s6", "section_number": "6"})


def test_a_central_in_force_header_comes_out_with_no_status():
    p = hit_to_passage(_act_hit())
    assert p.kind == "act_section"
    assert not STATUS.search(p.text), p.text
    assert p.text.startswith(
        "Act: The Negotiable Instruments Act, 1881 (Act 26 of 1881)\n"
    )
    assert "A cheque is a bill of exchange" in p.text  # the law itself is untouched


@pytest.mark.parametrize(
    "tail", ["India | Repealed | Repealed", "India | State | In Force"]
)
def test_every_header_variant_in_the_fixtures_is_stripped(tail):
    p = hit_to_passage(_act_hit(ACT.replace("India | Central | In Force", tail)))
    assert not STATUS.search(p.text), p.text


def test_every_practice_act_point_is_stripped():
    with gzip.open(PRACTICE / "act_sections.jsonl.gz", "rt") as fh:
        rows = [json.loads(line) for line in fh]
    assert len(rows) > 100
    for r in rows:
        h = Hit(r["chunk_id"], r["text"], 0.0, {"section_number": r["section_number"]})
        first = hit_to_passage(h).text.split("\n", 1)[0]
        assert first.startswith("Act:") and "|" not in first, first


def test_a_title_containing_a_bar_cannot_hide_the_tail():
    t = "Act: The A | B Act, 1999 | India | Central | In Force\nbody"
    assert strip_act_header_status(t) == "Act: The A | B Act, 1999\nbody"


def test_the_status_wordings_are_config_the_not_checked_line_ships():
    from core.settings import Settings

    f = Settings.model_fields
    assert f["ACT_STATUS_REPEALED"].default == ""  # NEEDS-OWNER
    assert f["ACT_STATUS_IN_FORCE"].default == ""  # NEEDS-OWNER
    assert (
        f["ACT_STATUS_NOT_CHECKED"].default
        == "In-force status not checked for this Act."
    )
    assert "ACT_HEADER_STATUS_REPLACEMENT" not in f


def test_the_not_checked_line_equals_the_one_the_website_uses():
    """Two places hold the line (the web client may not import the backend, rule 3);
    this keeps them equal."""
    from core.settings import Settings

    copy = (ROOT / "web/src/lib/copy.ts").read_text()
    m = re.search(r'IN_FORCE_NOT_CHECKED\s*=\s*"([^"]+)"', copy)
    assert m and m.group(1) == Settings.model_fields["ACT_STATUS_NOT_CHECKED"].default


# --- the status the model sees is CHECKED and inside the SHOW_IN_FORCE gate ------

WORDS = {"ACT_STATUS_REPEALED": "REPEALED-MARK", "ACT_STATUS_IN_FORCE": "INFORCE-MARK"}


def _passage(tail, payload_extra, **cfg):
    from core.settings import Settings

    s = Settings(_env_file=None, **cfg)
    text = ACT.replace("India | Central | In Force", tail)
    payload = {
        "act_id": "IND_central_1",
        "title": "The X Act, 1900",
        "section_number": "6",
    }
    h = Hit("IND_x_s6", text, 0.5, payload | payload_extra)
    return hit_to_passage(h, settings=s).text


def _no_raw_header(text):
    assert not re.search(
        r"\|\s*India|\|\s*(Central|State|Repealed)\b|\|\s*In Force", text
    )
    assert "In Force" not in text and "Central |" not in text


def test_a_repealed_act_carries_the_repealed_marker_whatever_the_switch():
    for show in (False, True):
        t = _passage(
            "India | Repealed | Repealed",
            {"act_status": "repealed"},
            SHOW_IN_FORCE=show,
            **WORDS,
        )
        assert t.rstrip().endswith("REPEALED-MARK")
        assert "INFORCE-MARK" not in t
        _no_raw_header(t)


def test_every_repeal_signal_gives_the_repealed_marker():
    for extra in (
        {"act_id": "IND_REP_9", "act_status": "in_force"},
        {"is_repealed": True, "act_status": "in_force"},
        {"title": "The Y Act, 1872 (Rep., Act 47 of 2023)", "act_status": "in_force"},
    ):
        t = _passage("India | Central | In Force", extra, **WORDS)
        assert t.rstrip().endswith("REPEALED-MARK"), extra


def test_an_in_force_act_carries_no_status_while_the_switch_is_off_and_does_once_on():
    off = _passage("India | Central | In Force", {"act_status": "in_force"}, **WORDS)
    assert "INFORCE-MARK" not in off
    assert off.rstrip().endswith("In-force status not checked for this Act.")
    _no_raw_header(off)
    on = _passage(
        "India | Central | In Force",
        {"act_status": "in_force"},
        SHOW_IN_FORCE=True,
        **WORDS,
    )
    assert on.rstrip().endswith("INFORCE-MARK")
    assert "not checked" not in on
    _no_raw_header(on)


def test_a_not_checked_act_carries_the_standing_line():
    for extra in ({}, {"act_status": ""}, {"act_status": "spent"}):
        t = _passage("India | State | In Force", extra)
        assert t.rstrip().endswith("In-force status not checked for this Act."), extra
        _no_raw_header(t)


def test_an_empty_wording_adds_no_line_so_nothing_is_invented():
    t = _passage(
        "India | Repealed | Repealed", {"act_status": "repealed"}
    )  # default ""
    assert t.rstrip().endswith("drawn on a specified banker.")  # no line added
    _no_raw_header(t)


def test_without_settings_only_the_header_is_stripped():
    t = hit_to_passage(_act_hit()).text
    _no_raw_header(t)
    assert "not checked" not in t


def test_the_search_step_appends_the_checked_line(settings, store):
    import asyncio

    from adapters.voyage import FakeEmbedder
    from core.contracts import Decision, Filters, PipelineRequest, RewrittenQuery
    from core.search import search
    from tests.core.core_helpers import make_deps

    deps = make_deps(settings, store, gate=None)
    q = RewrittenQuery("cheque bill of exchange banker")
    v = asyncio.run(FakeEmbedder().embed(q.query, None))
    d = Decision("in_scope", Filters(), "normal", (), True)
    found = asyncio.run(search(PipelineRequest("u", q.query), q, d, v, deps))
    acts = [p for p in found.passages if p.kind == "act_section"]
    assert acts
    for p in acts:
        _no_raw_header(p.text)
        assert p.text.rstrip().endswith(
            ("In-force status not checked for this Act.",)
        ) or p.act_status in (
            "repealed",
            "Repealed",
        )  # repealed: empty wording, no line


def test_a_judgment_passage_is_unaffected():
    body = "The Court held that Act: x | India | Central | In Force is a quoted string."
    header = "Case: A versus B (1959)\nSection: SECTION\n\n"
    h = Hit(
        "J1",
        header + body,
        0.5,
        {"chunk_id": "J1", "char_start": 0, "char_end": len(body)},
    )
    p = hit_to_passage(h)
    assert p.kind == "judgment" and p.text == body  # sliced by offsets, nothing matched
    assert hit_to_passage(Hit("J2", header + body, 0.5, {"chunk_id": "J2"})).text == (
        header + body
    )
