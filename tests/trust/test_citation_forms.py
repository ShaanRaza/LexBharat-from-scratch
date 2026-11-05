# ruff: noqa: E501
"""Citation-form detection: what MUST be caught, and what must NOT be touched.

Check 1 removes a case or citation the model recalled that was not retrieved this turn.
Widening the patterns (A.I.R., S.C.C., MANU/SC/, "1973 (4) SCC 225", Vs./V./v, line
breaks, look-alike letters) is safe only if legitimate text is left alone. This file
builds both sides from REAL strings in the dataset (tests/trust/fixtures/citation_forms.json,
made from the 20 practice judgments by build_citation_forms.py):

  MUST catch    every real AIR / SCC / SCR / "X v. Y" string found in the judgments, in
                every spelling a model or an attacker might use, when it was NOT retrieved.
  MUST NOT touch the same strings when the retrieved passage holds them (in any spelling),
                the stored citation string of a retrieved judgment, phrases that merely
                look like citations, and real sentences from the judgments themselves."""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

from core.contracts import Passage
from core.verify import _unretrieved_authority, verify

HERE = Path(__file__).parent
FORMS = json.loads(
    (HERE / "fixtures" / "citation_forms.json").read_text(encoding="utf-8")
)
JUDGMENTS = [
    json.loads(line)
    for line in gzip.open(HERE.parent / "fixtures/practice/judgments.jsonl.gz", "rt")
]

IN_TEXT_CITATIONS = (
    FORMS["in_text"]["air"] + FORMS["in_text"]["scc"] + FORMS["in_text"]["scr"]
)
UNRELATED = Passage(
    record_id="r0", source_id="S1", title="A versus B",
    text="Personal liberty under Article 21 cannot be curtailed except by procedure established by law.",
    citation_string="(1978) 1 SCC 248",
)  # fmt: skip


def spellings(cite: str) -> list[str]:
    """The ways one citation can be written."""
    undotted = re.sub(r"\.(?=[A-Za-z]\b|\s|$)", "", cite)
    dotted = re.sub(r"\b(AIR|SCC|SCR|SC)\b", lambda m: ".".join(m.group(1)) + ".", cite)
    return list(dict.fromkeys([
        cite,
        undotted,
        dotted,
        cite.lower(),
        cite.replace(" ", " "),
        cite.replace(" ", "  "),
        re.sub(r"(?<=\S) (?=\S)", " ​", cite),  # zero-width after the spaces
    ]))  # fmt: skip


def squash(s: str) -> str:
    return re.sub(r"\W", "", s).casefold()


# ---- the fixture is real and non-trivial ------------------------------------------------
def test_the_fixture_comes_from_the_dataset_and_is_big_enough_to_mean_something():
    assert len(FORMS["stored_citation_strings"]) == 20
    assert len(FORMS["in_text"]["air"]) >= 10 and len(FORMS["in_text"]["scr"]) >= 10
    assert (
        len(FORMS["in_text"]["scc"]) >= 3 and len(FORMS["in_text"]["case_names"]) >= 30
    )
    text = " ".join(j["full_text"] for j in JUDGMENTS)
    for cite in IN_TEXT_CITATIONS[:15]:  # really present in the dataset text
        assert re.sub(r"\s+", " ", cite) in re.sub(r"\s+", " ", text)


# ---- MUST CATCH ---------------------------------------------------------------------------
@pytest.mark.parametrize("cite", IN_TEXT_CITATIONS)
def test_a_recalled_real_citation_is_caught_in_every_spelling(cite):
    missed = [
        s for s in spellings(cite)
        if not _unretrieved_authority(f"The rule is settled in {s} on this point.", [UNRELATED])
    ]  # fmt: skip
    assert missed == [], f"not caught: {missed}"


@pytest.mark.parametrize("name", FORMS["in_text"]["case_names"])
def test_a_recalled_real_case_name_is_caught_in_every_spelling(name):
    left, right = re.split(r"\s+v\.?\s+", name)
    variants = [
        name,
        f"{left} Vs. {right}", f"{left} V. {right}", f"{left} vs {right}",
        f"{left}\nv.\n{right}", f"{left} v.\n{right}",
        f"{left} v​. {right}", f"{left} ​v. {right}", f"{left} v.​{right}",
        name.lower(), name.upper(),
        name.replace("v.", "ｖ.").replace(" v ", " ｖ "),
    ]  # fmt: skip
    missed = [
        v for v in variants
        if not _unretrieved_authority(f"As held in {v}, the point is settled.", [UNRELATED])
    ]  # fmt: skip
    assert missed == [], f"not caught: {missed!r}"


@pytest.mark.parametrize(
    "cite",
    [
        "A.I.R. 1973 S.C. 1461",
        "(1973) 4 S.C.C. 225",
        "( 1973 ) 4 SCC 225",
        "(1973)4SCC225",
        "AIR 1973 Supreme Court 1461",
        "MANU/SC/0133/1973",
        "1973 (4) SCC 225",
        "AIR1973SC1461",
    ],
)
async def test_end_to_end_the_whole_sentence_goes_when_a_recalled_citation_is_in_it(
    world, cite
):
    ans = await verify(
        world.draft(f"This is settled law in {cite} on bail."),
        world.passages,
        world.deps,
    )
    assert cite not in ans.text and ans.citations == ()
    assert any(r[2].reason == "not_retrieved" for r in world.citation_log.rows)


# ---- MUST NOT TOUCH -----------------------------------------------------------------------
@pytest.mark.parametrize("cite", IN_TEXT_CITATIONS)
def test_a_citation_the_retrieved_passage_holds_is_left_alone_in_every_spelling(cite):
    passage = Passage(
        record_id="r1", source_id="S1", title="X",
        text=f"The Court relied on {cite} and held that bail is the rule.",
    )  # fmt: skip
    flagged = [
        s for s in spellings(cite)
        if _unretrieved_authority(f"The Court relied on {s} here.", [passage])
    ]  # fmt: skip
    assert flagged == [], f"wrongly flagged: {flagged}"


@pytest.mark.parametrize("stored", FORMS["stored_citation_strings"])
def test_the_stored_citation_string_of_a_retrieved_judgment_is_never_flagged(stored):
    passage = Passage(
        record_id="r1",
        source_id="S1",
        title="X",
        text="Bail is the rule.",
        citation_string=stored,
    )
    flagged = [
        s
        for s in spellings(stored)
        if _unretrieved_authority(f"This follows {s}.", [passage])
    ]
    assert flagged == [], f"wrongly flagged: {flagged}"


@pytest.mark.parametrize("name", FORMS["in_text"]["case_names"])
def test_a_retrieved_case_name_is_left_alone_in_any_spelling_and_case(name):
    left, right = re.split(r"\s+v\.?\s+", name)
    passage = Passage(
        record_id="r1",
        source_id="S1",
        title="X",
        text=f"The Court followed {name} in this respect.",
    )
    for v in (
        name,
        f"{left} Vs. {right}",
        f"{left} V. {right}",
        name.lower(),
        f"{left}\nv.\n{right}",
    ):
        assert not _unretrieved_authority(
            f"As held in {v}, the point is settled.", [passage]
        ), v


@pytest.mark.parametrize("phrase", FORMS["not_citations"])
def test_phrases_that_only_look_like_citations_are_not_touched(phrase):
    assert not _unretrieved_authority(f"{phrase}.", [UNRELATED])


async def test_end_to_end_ordinary_legal_prose_survives_with_its_citation(world):
    text = "Personal liberty under Article 21 cannot be curtailed except by procedure established by law [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert [c.source_id for c in ans.citations] == ["S1"] and "Article 21" in ans.text


def _real_sentences():
    shape = re.compile(
        r"\bv\.?\s|\bvs\.?\s|\bAIR\b|\bA\.I\.R|SCC|S\.C\.R|SCR|MANU|\bIn re\b"
    )
    for j in JUDGMENTS:
        sents = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(])", j["full_text"])
        for i, s in enumerate(sents):
            if shape.search(s) and len(s) <= 600:
                yield j, s, " ".join(sents[max(0, i - 1) : i + 2])


def test_real_sentences_that_contain_citations_are_not_removed_when_their_passage_holds_them():
    """The precision test on real law: every sentence of the 20 judgments that carries a
    citation-like shape, checked against a passage that contains it. None may be flagged."""
    checked, flagged = 0, []
    for j, sentence, context in _real_sentences():
        passage = Passage(
            record_id="r",
            source_id="S1",
            text=context,
            citation_string=j["citation"],
            title=j["title"],
        )
        checked += 1
        if _unretrieved_authority(sentence, [passage]):
            flagged.append(sentence[:140])
    assert checked >= 150, f"fixture too small to mean anything: {checked}"
    assert flagged == []


def test_real_sentences_carrying_a_well_formed_citation_ARE_flagged_when_not_retrieved():
    """The other direction on real sentences: every sentence of the judgments that holds
    one of the well-formed citation strings in the fixture must be caught against an
    unrelated passage. (The dataset text is also full of OCR-garbled citations such as
    "[1982) 1 SCR 740" or "119961 2 SCC 384" and running page headers; those are not
    well-formed, and a model RECALLING a citation writes it cleanly, so they are not the
    target. They only ever appear in passages, where they are allowed.)"""
    hits, total, missed = 0, 0, []
    for _, sentence, _ in _real_sentences():
        flat = " ".join(sentence.split())
        if not any(c in flat for c in IN_TEXT_CITATIONS):
            continue
        total += 1
        if _unretrieved_authority(sentence, [UNRELATED]):
            hits += 1
        else:
            missed.append(flat[:120])
    assert total >= 20, total
    assert missed == [], missed
