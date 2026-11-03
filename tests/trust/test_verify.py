"""Tests written to BREAK the citation verifier (CLAUDE.md section 5, step 9)."""

import pytest

from core.verify import normalise, verify

GOOD = "Bail is the rule and jail the exception under Article 21 [S1]."


async def run(world, text):
    return await world.draft(text) and await verify(
        world.draft(text), world.passages, world.deps
    )


def reasons(world):
    return [r.reason for _, _, r in world.citation_log.rows]


async def test_good_citation_is_ticked_and_citation_string_untouched(world):
    ans = await verify(world.draft(GOOD), world.passages, world.deps)
    assert [c.source_id for c in ans.citations] == ["S1"]
    assert ans.citations[0].status == "verified"
    assert ans.citations[0].citation_string == "[1959] SUPP. 2 S.C.R. 986"  # as stored
    assert not ans.removed and world.citation_log.rows == []
    assert ans.sealed


# --- the four removal reasons: removed AND logged -----------------------------------
async def test_reason_not_retrieved_marker_outside_s1_s8(world):
    ans = await verify(world.draft("Bail is a right [S7]."), world.passages, world.deps)
    assert ans.citations == () and "S7" not in ans.text
    assert reasons(world) == ["not_retrieved"]
    assert "could not be verified" in ans.text


async def test_reason_not_retrieved_real_case_recalled_without_marker(world):
    text = "As held in Maneka Gandhi v. Union of India, liberty is wide. " + GOOD
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert "Maneka" not in ans.text
    assert reasons(world) == ["not_retrieved"]
    assert [c.source_id for c in ans.citations] == ["S1"]  # the good one survives


async def test_reason_not_retrieved_unmarked_scr_citation_string(world):
    ans = await verify(
        world.draft("It is settled law (1973) 4 SCC 225 that this applies."),
        world.passages,
        world.deps,
    )
    assert reasons(world) == ["not_retrieved"]
    assert "4 SCC 225" not in ans.text


async def test_reason_record_missing(world):
    world.vectors.law = [h for h in world.vectors.law if h.record_id != "rec-1"]
    ans = await verify(world.draft(GOOD), world.passages, world.deps)
    assert ans.citations == ()
    assert reasons(world) == ["record_missing"]
    assert world.citation_log.rows[0][2].record_id == "rec-1"


async def test_record_lookup_error_fails_closed_as_record_missing(world):
    world.vectors.down = True
    ans = await verify(world.draft(GOOD), world.passages, world.deps)
    assert ans.citations == () and reasons(world) == ["record_missing"]


async def test_reason_quote_not_found_wrong_words(world):
    text = 'The Court said "bail is a fundamental right of every accused" [S1].'
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert ans.citations == () and reasons(world) == ["quote_not_found"]
    assert "fundamental right of every accused" not in ans.text


async def test_reason_claim_not_supported(world):
    text = "Quantum entanglement dominates tax appeals [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert ans.citations == () and reasons(world) == ["claim_not_supported"]


# --- quote normalisation ------------------------------------------------------------
async def test_quote_with_changed_spaces_and_punctuation_still_matches(world):
    text = "It said “bail  is the rule,  jail — the exception” [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert [c.source_id for c in ans.citations] == ["S1"]
    assert world.citation_log.rows == []


async def test_quote_with_one_changed_word_fails(world):
    text = 'It said "bail is the exception, jail the rule" [S1].'
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert reasons(world) == ["quote_not_found"] and ans.citations == ()


def test_normalise_keeps_case_and_words():
    assert normalise("Bail,  is THE rule.") == "Bail is THE rule"


# --- Jev down: checks 1-3 still run; never a full tick without check 4 ---------------
async def test_jev_down_good_citation_is_only_partly(world_jev_down):
    w = world_jev_down
    ans = await verify(w.draft(GOOD), w.passages, w.deps)
    assert [(c.source_id, c.status) for c in ans.citations] == [("S1", "unchecked")]


@pytest.mark.parametrize("bad", ["S7", "S1"])
async def test_jev_down_checks_1_to_3_still_remove(world_jev_down, bad):
    w = world_jev_down
    if bad == "S1":
        w.vectors.law = []  # record gone
    ans = await verify(w.draft(f"Bail is the rule [{bad}]."), w.passages, w.deps)
    assert ans.citations == () and len(w.citation_log.rows) == 1


async def test_jev_down_wrong_quote_still_removed(world_jev_down):
    w = world_jev_down
    ans = await verify(
        w.draft('He said "totally invented words" [S1].'), w.passages, w.deps
    )
    assert ans.citations == () and reasons(w) == ["quote_not_found"]


async def test_jev_timeout_behaves_like_down(world):
    async def boom(*a, **k):
        raise TimeoutError

    world.decisions.claim_support = boom
    ans = await verify(world.draft(GOOD), world.passages, world.deps)
    assert ans.citations[0].status == "unchecked"


async def test_jev_partly_gives_partly_not_verified(world):
    async def partly(*a, **k):
        return "partly"

    world.decisions.claim_support = partly
    ans = await verify(world.draft(GOOD), world.passages, world.deps)
    assert ans.citations[0].status == "partly"


# --- structure ----------------------------------------------------------------------
async def test_no_citation_is_ever_unchecked(world):
    text = GOOD + ' Also "made up quote" [S2]. Also nonsense words here [S9].'
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert {c.status for c in ans.citations} <= {"verified", "partly", "unchecked"}
    assert all(c.source_id == "S1" for c in ans.citations)


async def test_failed_marker_stripped_but_other_citation_in_sentence_survives(world):
    ans = await verify(
        world.draft("Bail is the rule [S1, S9]."), world.passages, world.deps
    )
    assert [c.source_id for c in ans.citations] == ["S1"]
    assert "S9" not in ans.text and "[S1]" in ans.text
    assert reasons(world) == ["not_retrieved"]


async def test_note_counts_authorities(world):
    ans = await verify(world.draft("A [S7]. B [S8]."), world.passages, world.deps)
    assert "2 authorities" in ans.text and len(world.citation_log.rows) == 2


async def test_log_row_has_question_model_and_sentence(world):
    await verify(world.draft("Bail is a right [S7]."), world.passages, world.deps)
    q, model, r = world.citation_log.rows[0]
    assert (q, model) == ("q?", "fake-model") and r.sentence.startswith(
        "Bail is a right"
    )


async def test_upload_record_lookup_passes_owner_user_id(world):
    from core.contracts import Passage

    world.vectors.add_upload(
        "up-1",
        "client contract says payment due in 30 days",
        user_id="u1",
        document_id="d1",
    )
    p = Passage(
        record_id="up-1",
        text="client contract says payment due in 30 days",
        kind="upload",
        source_id="S1",
        user_id="u1",
    )
    ok = await verify(world.draft("Payment is due in 30 days [S1]."), [p], world.deps)
    assert ok.citations
    other = Passage(
        record_id="up-1", text="x", kind="upload", source_id="S1", user_id="u2"
    )
    bad = await verify(
        world.draft("Payment is due in 30 days [S1]."), [other], world.deps
    )
    assert bad.citations == ()  # another user's id cannot see the record


async def test_decision_unavailable_never_gives_verified(world):
    from adapters.decisions import DecisionUnavailable

    async def both_down(*a, **k):
        raise DecisionUnavailable("jev and gemini both failed")

    world.decisions.claim_support = both_down
    ans = await verify(world.draft(GOOD), world.passages, world.deps)
    assert [c.status for c in ans.citations] == ["unchecked"]


# --- reviewer attacks (quote bypasses, splitter, recalled cases) ---------------------
async def test_quote_containing_sentence_break_is_still_checked(world_jev_down):
    w = world_jev_down
    text = "The Court said “Bail is the rule. Therefore murder is lawful.” [S1]"
    ans = await verify(w.draft(text), w.passages, w.deps)
    assert ans.citations == () and reasons(w) == ["quote_not_found"]
    assert "murder" not in ans.text


async def test_single_quoted_text_is_checked(world_jev_down):
    w = world_jev_down
    ans = await verify(
        w.draft("It held 'bail is abolished in all cases' [S1]."), w.passages, w.deps
    )
    assert ans.citations == () and reasons(w) == ["quote_not_found"]


async def test_curly_single_quotes_are_checked(world_jev_down):
    w = world_jev_down
    ans = await verify(w.draft("It held ‘bail is abolished’ [S1]."), w.passages, w.deps)
    assert reasons(w) == ["quote_not_found"] and ans.citations == ()


async def test_mismatched_quote_marks_fail_closed(world_jev_down):
    w = world_jev_down
    ans = await verify(w.draft('It said “bail is the rule" [S1].'), w.passages, w.deps)
    assert ans.citations == () and reasons(w) == ["quote_not_found"]


async def test_unpaired_quote_mark_fails_closed(world_jev_down):
    w = world_jev_down
    ans = await verify(w.draft('It said "bail is the rule [S1].'), w.passages, w.deps)
    assert ans.citations == () and reasons(w) == ["quote_not_found"]


async def test_apostrophe_is_not_a_quote(world):
    ans = await verify(
        world.draft("The court's view: bail is the rule [S1]."),
        world.passages,
        world.deps,
    )
    assert [c.source_id for c in ans.citations] == ["S1"]


async def test_quote_must_match_whole_words(world_jev_down):
    w = world_jev_down
    await verify(w.draft('It said "ail is the rule" [S1].'), w.passages, w.deps)
    assert reasons(w) == ["quote_not_found"]


async def test_recalled_case_without_dot_is_removed(world):
    text = "In Kesavananda Bharati v State of Kerala the basic structure was held."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert "Kesavananda" not in ans.text and reasons(world) == ["not_retrieved"]


async def test_in_re_case_is_removed(world):
    await verify(
        world.draft("See In re Special Courts Bill for the rule."),
        world.passages,
        world.deps,
    )
    assert reasons(world) == ["not_retrieved"]


async def test_abbreviations_do_not_split_sentences(world):
    text = "Held in Tata Pvt. Ltd. v. Union that bail is the rule [S1]. Another point."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert reasons(world) == ["not_retrieved"]  # Tata case never retrieved
    assert "Held in Tata Pvt." not in ans.text.replace("Note", "")


async def test_paren_marker_is_parsed(world):
    ans = await verify(
        world.draft("Bail is the rule (S1)."), world.passages, world.deps
    )
    assert [c.source_id for c in ans.citations] == ["S1"]


async def test_paragraph_breaks_are_kept(world):
    text = "Bail is the rule [S1].\n\nSecond paragraph [S2]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert "\n\n" in ans.text


# --- reviewer round 2 ---
async def test_quote_in_sentence_without_marker_is_checked(world_jev_down):
    w = world_jev_down
    text = "The Court said “murder is lawful.” It follows. [S1]"
    ans = await verify(w.draft(text), w.passages, w.deps)
    assert "murder" not in ans.text
    assert "quote_not_found" in reasons(w)


async def test_uncited_quote_that_is_in_a_passage_is_still_removed_as_unmarked(world):
    """Before A137 this sentence was kept (a quote that IS in a passage passes check 3
    even with no marker). Strict removes every sentence without a marker, so the quote
    check no longer rescues it: the changed expectation is the point of A137."""
    text = (
        "The Court said \u201cbail is the rule\u201d. "
        "Bail is the rule and jail the exception [S1]."
    )
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert "The Court said" not in ans.text and "Bail is the rule" in ans.text
    assert reasons(world) == []


async def test_backtick_quotes_fail_closed(world_jev_down):
    w = world_jev_down
    ans = await verify(
        w.draft("The Court said ``murder is lawful'' [S1]."), w.passages, w.deps
    )
    assert ans.citations == () and reasons(w) == ["quote_not_found"]


@pytest.mark.parametrize("shape", ["AIR1978SC597", "1978 AIR 597", "AIR 1978 SC 597"])
async def test_unmarked_citation_string_shapes_removed(world, shape):
    ans = await verify(
        world.draft(f"Settled law is in {shape} on this point."),
        world.passages,
        world.deps,
    )
    assert reasons(world) == ["not_retrieved"] and shape not in ans.text


async def test_full_width_brackets_parse_as_markers(world):
    ans = await verify(
        world.draft("Bail is the rule ［S1］."), world.passages, world.deps
    )
    assert [c.source_id for c in ans.citations] == ["S1"]


async def test_marker_only_fragment_is_dropped_and_not_counted(world_jev_down):
    w = world_jev_down
    text = "The Court said “murder is lawful.” It follows. [S1]"
    ans = await verify(w.draft(text), w.passages, w.deps)
    assert ans.citations == ()
    assert "[S1]" not in ans.text and "murder" not in ans.text


async def test_citations_only_for_markers_in_surviving_text(world):
    text = "Bail is the rule and jail the exception [S1]. Nonsense tax words [S2]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert [c.source_id for c in ans.citations] == ["S1"]
    assert "[S2]" not in ans.text


async def test_jev_down_never_verified_never_partly(world_jev_down):
    w = world_jev_down
    ans = await verify(w.draft(GOOD), w.passages, w.deps)
    assert {c.status for c in ans.citations} == {"unchecked"}


async def test_same_source_twice_keeps_the_weakest_status(world):
    calls = iter(["supports", "partly"])

    async def mixed(*a, **k):
        return next(calls)

    world.decisions.claim_support = mixed
    text = (
        "Bail is the rule and jail the exception [S1]. "
        "Liberty is protected by Article 21 [S1]."
    )
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert [c.status for c in ans.citations] == ["partly"]
