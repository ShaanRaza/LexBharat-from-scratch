"""The citation verifier (step 9). These tests guard the trust promise (rule 6).

Each of the four removal reasons must remove the citation AND be reported so the caller
can log it. Checks 1-3 must still run with Jev off, down, or too slow.
"""

from __future__ import annotations

import dataclasses

import pytest
from core_helpers import ARNESH_TEXT, make_corpus, make_settings

from adapters.jev import DecisionAdapter, FakeDecisionBackend
from core.constants import (
    CLAIM_NOT_SUPPORTED,
    NOT_RETRIEVED,
    QUOTE_NOT_FOUND,
    RECORD_MISSING,
)
from core.models import Source
from core.show import UnverifiedAnswerError, show
from core.verify import (
    extract_quotes,
    normalise,
    parse_draft,
    quote_in_record,
    verify_answer,
)


def src(source_id: str, record_id: str, text: str) -> Source:
    return Source(source_id, record_id, f"{record_id}#0", text, 1, 0.9, "answers", 0.9)


S1 = src("S1", "sc-2014-arnesh", ARNESH_TEXT)
S2 = src("S2", "act-crpc-438", "anticipatory bail section 438 arrest non-bailable")


def adapter(primary=None, fallback=None, **settings) -> DecisionAdapter:
    return DecisionAdapter(
        primary or FakeDecisionBackend(),
        fallback or FakeDecisionBackend(),
        make_settings(**settings),
    )


# ---------------- parsing ----------------


def test_markers_are_stripped_and_offsets_point_at_the_sentence_end():
    clean, cites = parse_draft("Arrest needs care [S1]. Bail is possible [S2].")
    assert clean == "Arrest needs care. Bail is possible."
    assert [c.source_id for c in cites] == ["S1", "S2"]
    assert clean[: cites[0].offset] == "Arrest needs care"
    assert cites[0].sentence == "Arrest needs care"
    assert cites[1].sentence == "Bail is possible"


def test_multiple_ids_in_one_marker_and_adjacent_markers():
    _, cites = parse_draft("Both apply [S1, S2] and also [S3][S4].")
    assert [c.source_id for c in cites] == ["S1", "S2", "S3", "S4"]


def test_marker_placed_after_the_full_stop_still_binds_to_that_sentence():
    _, cites = parse_draft("First point. Second point. [S1]")
    assert cites[0].sentence == "Second point"


def test_abbreviations_do_not_split_sentences():
    _, cites = parse_draft("In State v. Union the court held X [S1].")
    assert cites[0].sentence == "In State v. Union the court held X"


def test_a_made_up_big_number_is_still_parsed_so_check_1_can_reject_it():
    _, cites = parse_draft("Something [S12].")
    assert cites[0].source_id == "S12"


# ---------------- quote normalisation (check 3 helpers) ----------------


def test_normalise_ignores_case_whitespace_and_punctuation():
    assert normalise("The  Court's\n\t'Bail'!") == normalise("the court s bail")


def test_curly_and_straight_quotes_are_both_extracted():
    sentence = 'It said "care and caution" and “scars forever”.'
    assert extract_quotes(sentence) == ["care and caution", "scars forever"]


def test_quote_matches_across_case_and_spacing_differences():
    assert quote_in_record("CARE   and\ncaution", ARNESH_TEXT)
    assert quote_in_record("care and caution,", ARNESH_TEXT)


def test_quote_must_match_whole_words_not_fragments():
    assert not quote_in_record("care and caut", ARNESH_TEXT)


def test_quote_words_must_be_in_order():
    assert not quote_in_record("caution and care", ARNESH_TEXT)


def test_ellipsis_quote_checks_every_piece():
    assert quote_in_record("power to arrest ... care and caution", ARNESH_TEXT)
    assert not quote_in_record("power to arrest ... never happens", ARNESH_TEXT)


# ---------------- the happy path ----------------


async def test_good_citation_is_kept_and_marked_verified():
    out = await verify_answer(
        'The "power to arrest must be exercised with care" [S1].',
        (S1,),
        make_corpus(),
        adapter(),
    )
    assert [c.status for c in out.citations] == ["verified"]
    assert out.removed == ()
    assert out.total_cited == 1
    assert "[S1]" not in out.text


# ---------------- check 1: retrieved this turn ----------------


async def test_invented_source_id_is_removed_as_not_retrieved():
    out = await verify_answer("A case exists [S9].", (S1,), make_corpus(), adapter())
    assert out.citations == ()
    assert [(r.source_id, r.reason) for r in out.removed] == [("S9", NOT_RETRIEVED)]


async def test_real_record_that_was_not_retrieved_this_turn_is_removed():
    # sc-2019-siddharam REALLY exists in the corpus, but was not given to the model
    # (only S1 was). The model "remembered" it. It must fail check 1.
    store = make_corpus()
    assert await store.get_record("sc-2019-siddharam") is not None
    out = await verify_answer("Remembered case [S2].", (S1,), store, adapter())
    assert out.removed[0].reason == NOT_RETRIEVED


# ---------------- check 2: record exists ----------------


async def test_missing_record_is_removed_as_record_missing():
    store = make_corpus()
    store.hide_record("sc-2014-arnesh")
    out = await verify_answer("Arrest needs care [S1].", (S1,), store, adapter())
    assert out.citations == ()
    assert out.removed[0].reason == RECORD_MISSING


# ---------------- check 3: quotes ----------------


async def test_wrong_quote_is_removed_as_quote_not_found():
    out = await verify_answer(
        'The court said "arrest is always forbidden" [S1].',
        (S1,),
        make_corpus(),
        adapter(),
    )
    assert out.citations == ()
    assert out.removed[0].reason == QUOTE_NOT_FOUND


async def test_quote_with_different_case_spacing_and_curly_marks_still_passes():
    out = await verify_answer(
        "It said “CARE  and\ncaution” [S1].", (S1,), make_corpus(), adapter()
    )
    assert out.removed == ()
    assert len(out.citations) == 1


async def test_one_bad_quote_in_a_sentence_fails_the_citation():
    out = await verify_answer(
        'It said "care and caution" and "totally invented words" [S1].',
        (S1,),
        make_corpus(),
        adapter(),
    )
    assert out.removed[0].reason == QUOTE_NOT_FOUND


async def test_quote_is_checked_against_the_whole_record_not_just_the_chunk():
    # The chunk shown to the model is short, but the record has more text.
    short = src("S1", "sc-2014-arnesh", "The power to arrest must be exercised.")
    always_supports = FakeDecisionBackend(claim_fn=lambda s, p: ("supports", 0.9))
    out = await verify_answer(
        'Scars: "casts scars forever" [S1].',
        (short,),
        make_corpus(),
        adapter(always_supports),
    )
    assert out.removed == ()


# ---------------- check 4: claim supported ----------------


async def test_unsupported_claim_is_removed_as_claim_not_supported():
    jev = FakeDecisionBackend(claim_fn=lambda s, p: ("does_not_support", 0.9))
    out = await verify_answer(
        "Arrest needs care [S1].", (S1,), make_corpus(), adapter(jev)
    )
    assert out.citations == ()
    assert out.removed[0].reason == CLAIM_NOT_SUPPORTED
    assert out.unverified_sentences == ("Arrest needs care",)


async def test_partly_supported_is_kept_with_a_warning_status():
    jev = FakeDecisionBackend(claim_fn=lambda s, p: ("partly", 0.7))
    out = await verify_answer(
        "Arrest needs care [S1].", (S1,), make_corpus(), adapter(jev)
    )
    assert [c.status for c in out.citations] == ["partly"]


async def test_check_4_is_not_run_for_citations_that_already_failed():
    jev = FakeDecisionBackend()
    await verify_answer(
        'Fake case [S9]. Wrong "quote x" [S1].', (S1,), make_corpus(), adapter(jev)
    )
    assert jev.calls == []  # no claim_support call was wasted


# ---------------- Jev up / down / slow: checks 1-3 always run ----------------


async def test_checks_1_to_3_run_with_jev_switched_off():
    jev = FakeDecisionBackend()
    out = await verify_answer(
        "Fake [S9].", (S1,), make_corpus(), adapter(jev, JEV_ENABLED_CLAIM=False)
    )
    assert out.removed[0].reason == NOT_RETRIEVED
    assert jev.calls == []


async def test_jev_down_falls_back_to_gemini_for_check_4():
    fallback = FakeDecisionBackend()
    out = await verify_answer(
        "Arrest needs care [S1].",
        (S1,),
        make_corpus(),
        adapter(FakeDecisionBackend(down=True), fallback),
    )
    assert out.citations[0].status == "verified"
    assert out.citations[0].support_source == "fallback"
    assert fallback.calls


async def test_jev_too_slow_falls_back_to_gemini():
    slow = FakeDecisionBackend(delay_s=0.5)
    out = await verify_answer(
        "Arrest needs care [S1].",
        (S1,),
        make_corpus(),
        adapter(slow, JEV_TIMEOUT_MS=20),
    )
    assert out.citations[0].support_source == "fallback"


async def test_checks_1_to_3_still_remove_bad_citations_when_everything_is_down():
    both_down = adapter(FakeDecisionBackend(down=True), FakeDecisionBackend(down=True))
    out = await verify_answer(
        'Invented [S9]. Bad "quote zzz" [S1]. Fine [S1].',
        (S1,),
        make_corpus(),
        both_down,
    )
    assert {r.reason for r in out.removed} == {NOT_RETRIEVED, QUOTE_NOT_FOUND}


async def test_if_check_4_cannot_run_a_citation_is_never_shown_as_verified():
    both_down = adapter(FakeDecisionBackend(down=True), FakeDecisionBackend(down=True))
    out = await verify_answer(
        "Arrest needs care [S1].", (S1,), make_corpus(), both_down
    )
    assert [c.status for c in out.citations] == ["unchecked"]


async def test_upload_chat_never_sends_text_to_jev():
    jev = FakeDecisionBackend()
    fallback = FakeDecisionBackend()
    await verify_answer(
        "Arrest needs care [S1].",
        (S1,),
        make_corpus(),
        adapter(jev, fallback),
        is_upload_chat=True,
    )
    assert jev.calls == []
    assert fallback.calls


# ---------------- the seal: verification cannot be skipped ----------------


async def test_show_refuses_an_answer_that_never_went_through_the_verifier(settings):
    from core.models import VerifiedAnswer

    fake = VerifiedAnswer("Trust me.", (), (), (), 0)
    with pytest.raises(UnverifiedAnswerError):
        show(fake, {}, settings)


async def test_show_refuses_a_verified_answer_that_was_edited_afterwards(settings):
    out = await verify_answer(
        "Arrest needs care [S1].", (S1,), make_corpus(), adapter()
    )
    tampered = dataclasses.replace(out, text="Something the verifier never saw.")
    with pytest.raises(UnverifiedAnswerError):
        show(tampered, {}, settings)


async def test_show_accepts_the_verifiers_own_output(settings):
    out = await verify_answer(
        "Arrest needs care [S1].", (S1,), make_corpus(), adapter()
    )
    records = {"sc-2014-arnesh": await make_corpus().get_record("sc-2014-arnesh")}
    final = show(out, records, settings)
    assert final.citations[0].citation_string == "(2014) 8 SCC 273"
    assert final.citations[0].citation_string_label == "as recorded in the dataset"
