# ruff: noqa: E501
"""Attacks on the citation verifier (core/verify.py) and the seal. Written to BREAK it.

Secure behaviour is asserted. Where the code is weak the test is xfail(strict=True)
with a BREAK reason, never "fixed" in the implementation."""

from __future__ import annotations

import dataclasses
import re
import unicodedata

import pytest

from adapters.decisions import DecisionUnavailable
from core import contracts
from core.cache import dump_result, load_result
from core.contracts import (
    Citation,
    Footer,
    Passage,
    PipelineResult,
    VerifiedAnswer,
)
from core.settings import get_settings
from core.verify import seal_answer, verify

GOOD = "Bail is the rule and jail the exception under Article 21 [S1]."
MARKER = re.compile(r"[\[(]\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*[\])]", re.IGNORECASE)


async def run(world, text, passages=None):
    return await verify(world.draft(text), passages or world.passages, world.deps)


def shown_labels(ans) -> set[str]:
    return {
        lab.upper()
        for m in MARKER.finditer(ans.text)
        for lab in re.split(r"\s*[,;]\s*", m.group(1))
    }


# ---- check 1: a label that was never in S1-S8 -----------------------------------
@pytest.mark.parametrize(
    "marker",
    [
        "[S9]", "[S0]", "[S01]", "[S10]", "[S１]", "[S٣]", "[S१]", "(S9)", "[s9]",
        "［S9］", "（S9）", "[S1, S9]", "[S9, S1]", "[S2;S9]", "[S99999999999999999999]",
        "[ S9 ]", "[S9 , S9]",
    ],
)  # fmt: skip
async def test_a_label_outside_the_gated_set_never_becomes_a_citation(world, marker):
    ans = await run(world, f"Bail is the rule and jail the exception {marker}.")
    assert {c.source_id for c in ans.citations} <= {"S1", "S2"}
    assert shown_labels(ans) <= {"S1", "S2"}  # no stray marker survives in the text
    assert ans.sealed


async def test_both_labels_in_one_marker_keep_only_the_real_one(world):
    ans = await run(
        world, "Bail is the rule and jail the exception under Article 21 [S1, S9]."
    )
    assert [c.source_id for c in ans.citations] == ["S1"]
    assert "S9" not in ans.text and "[S1]" in ans.text


@pytest.mark.parametrize(
    "marker", ["[S​1]", "[S­1]", "[S‍1]", "[​S1]", "[S1​]",
              "[S﻿1]", "[S⁠ 1]"],
)  # fmt: skip
async def test_an_invisible_character_inside_a_marker_cannot_mint_a_citation(
    world, marker
):
    """The marker does not parse, so it is just text: it must not be a Citation."""
    ans = await run(world, f"Bail is the rule and jail the exception {marker}.")
    assert ans.citations == ()
    assert ans.sealed


async def test_markers_inside_a_quotation_are_not_a_free_pass(world):
    ans = await run(world, 'The Court said "see [S1] for bail" under Article 21.')
    assert ans.citations == () and "see [S1]" not in ans.text


async def test_a_record_that_exists_in_the_store_but_was_not_gated_is_not_citable(
    world,
):
    world.vectors.add_law("rec-3", "Totally different text about contracts.")
    ans = await run(world, "Contracts need consideration [S3].")
    assert ans.citations == () and "rec-3" not in ans.text
    assert [r.reason for _, _, r in world.citation_log.rows] == ["not_retrieved"]


async def test_a_passage_with_no_label_cannot_be_cited_by_any_marker(world):
    unlabeled = [dataclasses.replace(p, source_id="") for p in world.passages]
    ans = await run(world, GOOD, unlabeled)
    assert ans.citations == ()


async def test_passages_are_immutable_so_a_gate_result_cannot_be_relabelled(world):
    with pytest.raises(dataclasses.FrozenInstanceError):
        world.passages[0].source_id = "S9"  # type: ignore[misc]


async def test_duplicate_markers_do_not_duplicate_or_upgrade_a_citation(world):
    text = "Bail is the rule [S1]. Jail is the exception under Article 21 [S1][S1]."
    ans = await run(world, text)
    assert [c.source_id for c in ans.citations] == ["S1"]


# ---- check 2/3: records and quotes ----------------------------------------------------
@pytest.mark.parametrize(
    "fake_quote",
    [
        "bаil is the rule",  # Cyrillic a
        "ba­il is the rule",  # soft hyphen
        "ba​il is the rule",  # zero-width space
        "BAIL is the rule",  # case is kept
        "ail is the rule",  # partial word
        "bail is the rule and always will be",  # extra words
        "jail the bail",  # words in the wrong order
    ],
)
async def test_a_quote_that_is_not_in_the_record_is_removed(world, fake_quote):
    ans = await run(world, f'The Court held "{fake_quote}" under Article 21 [S1].')
    assert ans.citations == () and fake_quote not in ans.text
    assert [r.reason for _, _, r in world.citation_log.rows] == ["quote_not_found"]


async def test_a_real_quote_still_passes_so_the_tests_above_mean_something(world):
    ans = await run(world, 'The Court held "bail is the rule" under Article 21 [S1].')
    assert [c.source_id for c in ans.citations] == ["S1"]


QUOTE_BREAK = pytest.mark.xfail(
    strict=True,
    reason='BREAK: quotation marks other than "" “” ‘’ are not recognised as quotes '
    "(_QUOTE_SPAN, core/verify.py:~96), so a fabricated «guillemet» / 「CJK」 / ‹single› "
    "quotation skips check 3 and is ticked",
)


@pytest.mark.parametrize(
    "quoted",
    [
        "\u201ejail is never allowed for any accused\u201c",  # unbalanced: caught
        pytest.param("«jail is never allowed for any accused»", marks=QUOTE_BREAK),
        pytest.param("「jail is never allowed for any accused」", marks=QUOTE_BREAK),
        pytest.param("‹jail is never allowed for any accused›", marks=QUOTE_BREAK),
        pytest.param("『jail is never allowed for any accused』", marks=QUOTE_BREAK),
    ],
)
async def test_a_fabricated_quotation_in_other_quotation_marks_is_removed(
    world, quoted
):
    ans = await run(world, f"The Court held {quoted} under Article 21 [S1].")
    assert ans.citations == ()


async def test_a_quote_that_spans_two_records_is_not_found_in_either(world):
    # First half is S1's text, second half is S2's: no single record holds the quote.
    ans = await run(
        world,
        'The Court held "bail is the rule, jail the exception. The appeal is dismissed '
        'with costs" [S1].',
    )
    assert ans.citations == ()


async def test_a_deleted_record_cannot_be_cited_even_though_the_passage_text_is_in_hand(
    world,
):
    world.vectors.law = [h for h in world.vectors.law if h.record_id != "rec-1"]
    ans = await run(world, GOOD)
    assert ans.citations == ()
    assert [r.reason for _, _, r in world.citation_log.rows] == ["record_missing"]


async def test_the_store_being_down_means_not_verified_not_verified_anyway(world):
    world.vectors.down = True
    ans = await run(world, GOOD)
    assert ans.citations == ()


# ---- the decider (check 4) is outside our control: it must fail closed ---------------
class YesMan:
    """A decider that approves everything."""

    async def claim_support(self, sentence, passage):
        return "supports"

    async def rate_passage(self, q, p):
        return "answers", 1.0

    async def decide(self, q, *, uploads=False):  # pragma: no cover
        raise NotImplementedError


class Garbage:
    def __init__(self, value):
        self.value = value

    async def claim_support(self, sentence, passage):
        return self.value


async def test_a_yes_man_decider_still_cannot_rescue_checks_one_to_three(world):
    world.decisions = YesMan()
    ans = await run(
        world,
        "Bail is a right [S9]. "
        'The Court said "jail is never allowed" [S1]. '
        "As held in Maneka Gandhi v. Union of India, liberty is wide.",
    )
    assert ans.citations == ()
    assert {r.reason for _, _, r in world.citation_log.rows} >= {
        "not_retrieved",
        "quote_not_found",
    }


async def test_a_yes_man_decider_is_the_known_limit_of_check_four(world):
    """Documented, not a bug in checks 1-3: if the decider approves an unquoted claim
    that the passage does not make, the tick follows the decider. The tick never meant
    'the summary is right' (CLAUDE.md section 5)."""
    world.decisions = YesMan()
    ans = await run(world, "Bail is a fundamental right of every accused person [S1].")
    assert [c.status for c in ans.citations] == ["verified"]


@pytest.mark.parametrize(
    "value", [None, "SUPPORTS", "maybe", "", 1, True, "does_not_support"]
)
async def test_a_garbage_decider_answer_removes_the_citation(world, value):
    world.decisions = Garbage(value)
    ans = await run(world, GOOD)
    assert ans.citations == ()
    assert [r.reason for _, _, r in world.citation_log.rows] == ["claim_not_supported"]


async def test_decider_down_never_yields_a_tick(world_jev_down):
    w = world_jev_down
    ans = await run(w, GOOD)
    assert [c.status for c in ans.citations] == ["unchecked"]
    assert all(c.status != "verified" for c in ans.citations)


async def test_a_decider_that_times_out_is_unchecked_not_verified(world):
    class Slow:
        async def claim_support(self, sentence, passage):
            raise TimeoutError

    world.decisions = Slow()
    ans = await run(world, GOOD)
    assert [c.status for c in ans.citations] == ["unchecked"]


async def test_a_decider_that_crashes_stops_the_answer_instead_of_passing_it(world):
    class Boom:
        async def claim_support(self, sentence, passage):
            raise RuntimeError("model gateway exploded")

    world.decisions = Boom()
    with pytest.raises(RuntimeError):
        await run(world, GOOD)  # the pipeline turns this into outcome "error"
    assert DecisionUnavailable  # (the only exception treated as 'unchecked')


# ---- recalled authorities: obfuscation of a real case name ------------------------------
CASE_BREAK = pytest.mark.xfail(
    strict=True,
    reason="BREAK: the case-name shape (core/verify.py _CITATION_SHAPES, the v./vs. "
    "regex) is case-, space- and ASCII-sensitive and runs per sentence: 'Vs.'/'V.', a "
    "line break inside the name, zero-width characters, all-lower-case and look-alike "
    "letters hide a recalled case from check 1 (no marker needed)",
)


@pytest.mark.parametrize(
    "case",
    [
        "Maneka Gandhi v. Union of India",
        "Maneka Gandhi vs. Union of India",
        "Maneka Gandhi versus Union of India",
        "Maneka Gandhi v Union of India",
        "Maneka\u00a0Gandhi v. Union of India",
        "Maneka Gandhi v.\u00a0Union of India",
        "Maneka Gandhi  v.  Union of India",
        pytest.param("Maneka Gandhi V. Union of India", marks=CASE_BREAK),
        pytest.param("Maneka Gandhi Vs. Union of India", marks=CASE_BREAK),
        pytest.param("Maneka Gandhi\nv.\nUnion of India", marks=CASE_BREAK),
        pytest.param("Maneka Gandhi v.\nUnion of India", marks=CASE_BREAK),
        pytest.param("Maneka Gandhi v\u200b. Union of India", marks=CASE_BREAK),
        pytest.param("Maneka Gandhi v.\u200bUnion of India", marks=CASE_BREAK),
        pytest.param("Maneka Gandhi \u200bv. Union of India", marks=CASE_BREAK),
        pytest.param("maneka gandhi v. union of india", marks=CASE_BREAK),
        pytest.param("Maneka Gandhi v\u0455. Union of India", marks=CASE_BREAK),
        pytest.param("Maneka Gandhi \uff56. Union of India", marks=CASE_BREAK),
    ],
)
async def test_a_recalled_case_named_in_plain_text_is_removed(world, case):
    ans = await run(world, f"As held in {case}, liberty is wide.")
    flat = unicodedata.normalize("NFKC", ans.text).replace("\u200b", "").lower()
    assert "gandhi" not in flat


CITE_BREAK = pytest.mark.xfail(
    strict=True,
    reason="BREAK: _CITATION_SHAPES (core/verify.py:~100) has no pattern for this "
    "spelling, so an unmarked recalled citation string stays in the answer",
)


@pytest.mark.parametrize(
    "cite",
    [
        "(1973) 4 SCC 225",
        "AIR 1973 SC 1461",
        "AIR1973SC1461",
        "1973 AIR 1461",
        "[1973] 4 SCR 225",
        "air 1973 sc 1461",
        "2019 SCC OnLine SC 1234",
        pytest.param("A.I.R. 1973 S.C. 1461", marks=CITE_BREAK),
        pytest.param("(1973) 4 S.C.C. 225", marks=CITE_BREAK),
        pytest.param("( 1973 ) 4 SCC 225", marks=CITE_BREAK),
        pytest.param("(1973)4SCC225", marks=CITE_BREAK),
        pytest.param("AIR 1973 Supreme Court 1461", marks=CITE_BREAK),
        pytest.param("MANU/SC/0133/1973", marks=CITE_BREAK),
        pytest.param("1973 (4) SCC 225", marks=CITE_BREAK),
    ],
)
async def test_an_unmarked_recalled_citation_string_is_removed(world, cite):
    ans = await run(world, f"The rule is settled law in {cite} on this point.")
    assert cite not in ans.text


# ---- the seal: forgery, reuse, key games ----------------------------------------------
def good_sealed():
    return seal_answer("Bail is the rule [S1].", [], [])


def forged_citation(status="verified"):
    return Citation("S1", "rec-1", status, "(1978) 1 SCC 248", None, None)


def test_a_seal_copied_onto_a_stronger_citation_is_rejected():
    weak = seal_answer("Text [S1].", [forged_citation("unchecked")], [])
    strong = dataclasses.replace(weak, citations=(forged_citation("verified"),))
    assert not contracts.is_sealed(strong)  # same seal bytes, tick upgraded


def test_removed_citations_cannot_be_erased_after_sealing():
    from core.contracts import RemovedCitation

    rem = (RemovedCitation("S9", None, "not_retrieved", "x"),)
    a = seal_answer("Text.", [], rem)
    assert not contracts.is_sealed(dataclasses.replace(a, removed=()))


SEAL_TYPE_BREAK = pytest.mark.xfail(
    strict=True,
    reason="BREAK (low): is_sealed() RAISES TypeError (hmac.compare_digest, "
    "core/verify.py:403) for a non-bytes seal instead of returning False; fails closed "
    "by exception, but the contract says it returns a bool",
)


@pytest.mark.parametrize(
    "seal",
    [
        b"",
        b"\x00" * 32,
        b"x",
        pytest.param(None, marks=SEAL_TYPE_BREAK),
        pytest.param("str-seal", marks=SEAL_TYPE_BREAK),
        pytest.param(0, marks=SEAL_TYPE_BREAK),
    ],
)
def test_empty_short_or_wrongly_typed_seals_are_rejected(seal):
    a = good_sealed()
    try:
        forged = dataclasses.replace(a, _seal=seal)
    except TypeError:  # pragma: no cover
        return
    assert not contracts.is_sealed(forged)


def test_a_seal_from_another_answer_is_rejected():
    a, b = good_sealed(), seal_answer("Other text [S1].", [], [])
    assert not contracts.is_sealed(dataclasses.replace(a, _seal=b._seal))


def test_a_truncated_or_extended_seal_is_rejected():
    a = good_sealed()
    for forged in (a._seal[:-1], a._seal + b"\x00", a._seal[1:] + a._seal[:1]):
        assert not contracts.is_sealed(dataclasses.replace(a, _seal=forged))


def test_the_seal_does_not_survive_a_key_change(monkeypatch):
    a = good_sealed()
    monkeypatch.setenv("SEAL_KEY", "rotated-key")
    get_settings.cache_clear()
    assert not contracts.is_sealed(a)
    monkeypatch.setenv("SEAL_KEY", "test-only-seal-key")
    get_settings.cache_clear()
    assert contracts.is_sealed(a)  # and comes back with the right key


def test_with_no_key_nothing_is_sealed_or_accepted(monkeypatch):
    a = good_sealed()
    monkeypatch.setenv("SEAL_KEY", "")
    get_settings.cache_clear()
    assert not contracts.is_sealed(a)
    with pytest.raises(RuntimeError):
        seal_answer("x", [], [])
    with pytest.raises(ValueError):  # and a result cannot be built around it
        PipelineResult("answered", a, Footer("2026-08-31", "v"))


def test_the_seal_checker_cannot_be_replaced_by_a_look_alike():
    def evil(answer):  # pragma: no cover
        return True

    evil.__module__ = "core.verify"  # impersonate the verifier
    with pytest.raises(RuntimeError):
        contracts.register_seal_checker(evil)
    assert not contracts.is_sealed(VerifiedAnswer("x", (), ()))


def test_a_look_alike_object_is_not_a_sealed_answer():
    class Duck:
        text, citations, removed, sealed = "x [S1]", (), (), True
        _seal = b"anything"

    assert not contracts.is_sealed(Duck())


@pytest.mark.xfail(
    strict=True,
    reason="BREAK (low): is_sealed() uses isinstance, so a VerifiedAnswer SUBCLASS whose "
    "`text` changes between the seal check and the read passes show() with different "
    "text (time-of-check/time-of-use; core/contracts.py is_sealed, core/show.py)",
)
async def test_a_stateful_subclass_cannot_show_different_text_than_was_sealed():
    from core.show import show

    sealed_ans = seal_answer("Sealed text [S1].", [], [])

    class Shifty(VerifiedAnswer):
        reads = 0

        @property  # type: ignore[override]
        def text(self):  # noqa: D401
            Shifty.reads += 1
            return "Sealed text [S1]." if Shifty.reads == 1 else "EVIL text [S1]."

        @text.setter
        def text(self, value):
            pass

    forged = Shifty("Sealed text [S1].", (), (), _seal=sealed_ans._seal)
    result = object.__new__(PipelineResult)
    for f in dataclasses.fields(PipelineResult):
        object.__setattr__(result, f.name, None)
    object.__setattr__(result, "outcome", "answered")
    object.__setattr__(result, "answer", forged)
    object.__setattr__(result, "footer", Footer("2026-08-31", "v"))
    object.__setattr__(result, "message_key", "")
    streamed = "".join([e.text async for e in show(result) if hasattr(e, "text")])
    assert "EVIL" not in streamed


async def test_a_tampered_cache_entry_is_a_miss_not_an_answer(world):
    ans = await run(world, GOOD)
    res = PipelineResult("answered", ans, Footer("2026-08-31", "v2026.08"))
    import json

    raw = dump_result(res)
    assert load_result(raw, res.footer) is not None  # control: untouched loads
    d = json.loads(raw)
    tampered = [
        {**d, "text": d["text"] + " Extra claim [S1]."},
        {**d, "citations": [{**d["citations"][0], "status": "verified",
                             "record_id": "rec-evil"}]},
        {**d, "removed": []} if d["removed"] else {**d, "removed": [
            {"source_id": "S9", "record_id": None, "reason": "not_retrieved",
             "sentence": "x"}]},
        {**d, "seal": "00" * 32},
        {k: v for k, v in d.items() if k != "seal"},
    ]  # fmt: skip
    for t in tampered:
        assert load_result(json.dumps(t), res.footer) is None


async def test_a_cache_entry_sealed_under_an_old_key_is_a_miss(world, monkeypatch):
    ans = await run(world, GOOD)
    res = PipelineResult("answered", ans, Footer("2026-08-31", "v2026.08"))
    raw = dump_result(res)
    monkeypatch.setenv("SEAL_KEY", "rotated-key")
    get_settings.cache_clear()
    assert load_result(raw, res.footer) is None


def test_passage_is_a_frozen_value_and_cannot_be_given_a_label_later():
    p = Passage(record_id="r", text="t")
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.source_id = "S1"  # type: ignore[misc]
