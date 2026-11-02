"""The dataset's status tail on an Act point's header never reaches the model (A105).

CLAUDE.md section 6: "in force" is not shown until the act_status conflict is settled.
The stored Act text opens "Act: <title> | India | Central | In Force"; Act points
carry no char_start/char_end, so the tail is matched and removed, not sliced off."""

import gzip
import json
import re

import pytest

from adapters.qdrant import Hit
from core.search import hit_to_passage, strip_act_header_status
from tests.core.conftest import PRACTICE

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


def test_the_replacement_is_config_and_empty_by_default():
    from core.settings import Settings

    assert Settings.model_fields["ACT_HEADER_STATUS_REPLACEMENT"].default == ""
    out = strip_act_header_status(ACT, "status not checked")
    assert out.splitlines()[0].endswith("(Act 26 of 1881) status not checked")


def test_the_search_step_passes_the_configured_replacement(settings, store):
    import asyncio

    from adapters.voyage import FakeEmbedder
    from core.contracts import Decision, Filters, PipelineRequest, RewrittenQuery
    from core.search import search
    from tests.core.core_helpers import make_deps

    s = settings.model_copy(update={"ACT_HEADER_STATUS_REPLACEMENT": "REPL"})
    deps = make_deps(s, store, gate=None)
    q = RewrittenQuery("cheque bill of exchange banker")
    v = asyncio.run(FakeEmbedder().embed(q.query, None))
    d = Decision("in_scope", Filters(), "normal", (), True)
    found = asyncio.run(search(PipelineRequest("u", q.query), q, d, v, deps))
    acts = [p for p in found.passages if p.kind == "act_section"]
    assert acts and all(p.text.split("\n", 1)[0].endswith("REPL") for p in acts)
    assert not any(STATUS.search(p.text.split("\n", 1)[0]) for p in acts)


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
