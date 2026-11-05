"""The supplement chunker (lane D): India Code PDFs -> section records, dry run only.

These tests use small invented page text, not the owner's PDFs, so they run anywhere. They
guard the three promises that matter: a supplement record can never be mistaken for a dataset
record, nothing is ever marked in force, and Acts held for review emit nothing."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from data import build_supplement_chunks as b
from data import supplement_hold as h


# ---- page furniture and footnotes -------------------------------------------------------
def test_watermark_page_number_and_footnote_are_split_off():
    page = "\n".join(
        [
            "    1. Short title.—This Act may be called the Test Act, 1900.   e",
            "                                od",
            "    Extent.—It extends to 2[ 3***] India.",
            "                                                       7",
            "2. Subs. by Act 9 of 1999, s. 3, for “old”.",
            "continued footnote text",
        ]
    )
    body, notes, dropped = b.split_page(page, constitution=False)
    assert body == [
        "    1. Short title.—This Act may be called the Test Act, 1900.",
        "    Extent.—It extends to 2[ 3***] India.",
    ]
    assert notes == {
        2: "2. Subs. by Act 9 of 1999, s. 3, for “old”. continued footnote text"
    }
    assert dropped["watermark_lines"] == 1 and dropped["page_numbers"] == 1


def test_clean_body_strips_footnote_markers_but_keeps_brackets_and_figures():
    assert b.clean_body(
        "It extends to 2[the whole of India] and 4*** Act 9 of 1872."
    ) == ("It extends to [the whole of India] and *** Act 9 of 1872.")


@pytest.mark.parametrize(
    "line,label",
    [
        ("    16. Undue influence defined.—(1) A contract", "16"),
        ("    [16.“Undue influence” defined.—(1) A contract", "16"),
        ("    20.Agreement void where both parties.—Where", "20"),
        ("       334. 4[Reservation of seats.—x", "334"),
        ("    1 [73-A. Power of Central Government.—(1) The", "73A"),
        ("   *[239A. Creation of local Legislatures.—", "239A"),
    ],
)
def test_section_labels_are_recognised_in_the_shapes_the_pdfs_print(line, label):
    m = b.LABEL.match(line)
    assert m and m.group(1).replace("-", "") == label


def test_a_number_inside_a_figure_is_not_a_section_label():
    assert not b.LABEL.match("      1,234 rupees were paid")
    assert not b.LABEL.match("    (1) In this section 3.5 per cent")


# ---- statuses --------------------------------------------------------------------------
def _rec(line, *more):
    r = b.Rec("9", "section")
    r.lines = [line, *more]
    return r


def test_repealed_and_omitted_are_stored_as_such_never_as_live():
    assert (
        b.status_of(
            _rec(
                "2. [Repeal of enactments.] Rep. by the Repealing Act, 1891 (12 of 1891)"
            )
        )
        == "repealed"
    )
    assert (
        b.status_of(_rec("79.[Transfer of ownership.]Rep. by s. 65, Act 3 of 1930"))
        == "repealed"
    )
    assert b.status_of(_rec("60. [Omitted.] by Act 22 of 2002, s. 8")) == "omitted"
    assert (
        b.status_of(_rec("7. Short title.—This Act may be called the Test Act."))
        == b.STATUS
    )


def test_no_record_is_ever_marked_in_force():
    assert b.STATUS == "not_checked"
    spec = ("testact", "t.pdf", "The Test Act, 1900", "1", "1900", "sections")
    a = {
        "spec": spec,
        "source_url": "https://indiacode.gov.in/act/x",
        "as_of": "2026-01-01",
        "as_of_basis": "printed",
    }
    r = b.Rec("1", "section", pages={0})
    r.lines = ["1. Short title.—This Act may be called the Test Act, 1900."]
    p = b.payload(
        a, r, "Short title", "This Act may be called the Test Act, 1900.", 0, 1
    )
    assert p["act_status"] == "not_checked" and p["section_status"] == "not_checked"
    assert "in_force" not in json.dumps(p).lower().replace("in_force_not", "")
    assert "In Force" not in p["text"]


# ---- identity --------------------------------------------------------------------------
def test_supplement_ids_use_the_prefix_the_dataset_never_uses():
    assert b.PREFIX == "IND_SUPP_"
    for kind, extra in (
        ("section", {}),
        ("article", {}),
        ("rule", {"order": "VII"}),
        ("schedule", {}),
    ):
        r = b.Rec("11", kind, **extra)
        assert b.chunk_id("cpc1908", r).startswith("IND_SUPP_cpc1908_")
    assert b.chunk_id("cpc1908", b.Rec("11", "rule", order="VII")) != b.chunk_id(
        "cpc1908", b.Rec("11", "rule", order="XLI")
    )  # rule 11 of two Orders must not collide
    assert b.chunk_id("cpc1908", b.Rec("11", "rule", order="VII")) != b.chunk_id(
        "cpc1908", b.Rec("11", "section")
    )  # nor with section 11


def test_every_act_has_a_distinct_slug_and_the_script_has_no_network_or_vendor_import():
    slugs = [a[0] for a in b.ACTS]
    assert len(slugs) == len(set(slugs)) == 9
    src = Path(b.__file__).read_text(encoding="utf-8")
    for banned in (
        "import urllib",
        "import requests",
        "qdrant",
        "voyageai",
        "import httpx",
        "socket",
    ):
        assert banned not in src.replace("Qdrant", "").replace("`kanoon_v1`", ""), (
            banned
        )


def test_ason_date_is_read_per_act_and_missing_date_is_marked():
    m = b.ASON.search("The Hindu Marriage Act, 1955\n [As on the 15th April, 2026]")
    assert m and (m.group(1), m.group(2), m.group(3)) == ("15", "April", "2026")
    assert (
        b.ASON.search("THE INDIAN CONTRACT ACT, 1872\nARRANGEMENT OF SECTIONS") is None
    )


# ---- the held-off Acts -----------------------------------------------------------------
PAYLOAD = {
    "act_id": "IND_state_6796",
    "chunk_id": "IND_state_6796_s438",
    "state": "dadra-nagar-haveli",
    "jurisdiction": "state",
    "act_status": "in_force",
    "text": "x",
}


def test_the_shipped_hold_list_is_off_and_emits_nothing():
    entries = h.load_hold()
    assert {e["slug"] for e in entries} == {
        "crpc1973",
        "gratuity1972",
        "consumer1986",
        "eca1923",
    }
    for e in entries:
        assert not h.servable(e)
        assert e["proposed"]["status"] == "UNREVIEWED" and e["repealed_by"] == ""
        assert list(h.records_for(e, [PAYLOAD])) == []
        with pytest.raises(h.HeldBack):
            h.to_supplement_record(PAYLOAD, e)


@pytest.mark.parametrize(
    "missing", ["repealed_by", "reviewed_by", "reviewed_on", "serve"]
)
def test_each_missing_review_field_alone_keeps_the_act_off(missing):
    e = copy.deepcopy(h.load_hold()[0])
    e.update(
        repealed_by="The Bharatiya Nagarik Suraksha Sanhita, 2023",
        reviewed_by="A. Advocate",
        reviewed_on="2026-11-10",
        serve=True,
    )
    assert h.servable(e)
    e[missing] = False if missing == "serve" else ""
    assert not h.servable(e)
    assert list(h.records_for(e, [PAYLOAD])) == []


def test_a_fully_reviewed_act_is_emitted_as_repealed_central_with_the_new_prefix():
    e = copy.deepcopy(h.load_hold()[0])
    e.update(
        repealed_by="The Bharatiya Nagarik Suraksha Sanhita, 2023",
        reviewed_by="A. Advocate",
        reviewed_on="2026-11-10",
        serve=True,
        canonical_act_ids=["IND_state_6796"],
    )
    other = {**PAYLOAD, "act_id": "IND_state_9999", "chunk_id": "IND_state_9999_s438"}
    out = list(h.records_for(e, [PAYLOAD, other]))
    assert len(out) == 1  # one canonical copy, not 14
    r = out[0]
    assert (
        r["chunk_id"] == "IND_SUPP_crpc1973_s438" and r["act_id"] == "IND_SUPP_crpc1973"
    )
    assert r["state"] == "central" and r["act_status"] == "repealed"
    assert (
        r["repealed_by"] == e["repealed_by"]
        and r["copied_from_act_id"] == "IND_state_6796"
    )


# ---- splitting oversize records (A183) ----------------------------------------------------
def test_split_body_is_lossless_and_respects_the_limit():
    body = "\n".join(
        [
            f"({i}) A clause about thing {i} that runs on for a while to take up room. "
            * 3
            for i in range(1, 40)
        ]
    )
    parts = b.split_body(body, 500)
    assert "".join(parts) == body and len(parts) > 3
    assert all(len(p) <= 500 for p in parts)
    assert all(
        p.lstrip().startswith("(") for p in parts[1:]
    )  # cut at a sub-clause, not mid-sentence


def test_one_huge_line_is_cut_at_sentence_ends():
    body = "Sentence number one is here. " * 200
    parts = b.split_body(body, 300)
    assert "".join(parts) == body and all(len(p) <= 300 for p in parts)
    assert all(p.rstrip().endswith(".") for p in parts[:-1])


def test_split_payload_keeps_parent_part_number_and_stores_notes_once():
    p = {
        "chunk_id": "IND_SUPP_x_s1",
        "text": "Act: T | India | Central | Status not checked\nSection 1: H\n"
        + ("(1) text here. \n" * 200),
        "amendment_notes": ["1. Subs. by Act"],
        "amendment_count": 1,
        "state_amendment_text": "state",
    }
    parts = b.split_payload(p, 600)
    assert len(parts) > 2 and all(len(q["text"]) <= 600 for q in parts)
    assert [q["part_number"] for q in parts] == list(range(1, len(parts) + 1))
    assert {q["parent_id"] for q in parts} == {"IND_SUPP_x_s1"}
    assert parts[0]["amendment_notes"] and not any(
        q["amendment_notes"] for q in parts[1:]
    )
    assert len({q["chunk_id"] for q in parts}) == len(parts)
    rebuilt = "".join(q["text"].split("\n", 2)[2] for q in parts)
    assert rebuilt == p["text"].split("\n", 2)[2]


def test_an_unsplit_record_keeps_its_own_id():
    p = {
        "chunk_id": "IND_SUPP_x_s2",
        "text": "H1\nH2\nshort body",
        "amendment_notes": [],
    }
    (q,) = b.split_payload(p, 600)
    assert (
        q["chunk_id"] == "IND_SUPP_x_s2"
        and q["part_number"] == 1
        and q["total_parts"] == 1
    )
