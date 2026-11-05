"""A157: a curly U+2019 between two letters is an apostrophe, not a stray quote mark.

Every other quote-like mark keeps failing closed. Each test fails if the exemption is
widened (to a mark at a word edge, beside a digit or space, or beside a real quote)."""

import pytest

from core.verify import _unbalanced_quotes, verify

CLAIM = "bail is the rule, jail the exception"  # in the S1 passage, word for word


def kept(ans):
    return [c.source_id for c in ans.citations]


async def test_possessive_in_a_sentence_with_no_real_quote_passes_check_3(world):
    text = "The Court’s view is that bail is the rule and jail the exception [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert kept(ans) == ["S1"] and "Court’s view" in ans.text
    assert not ans.removed


@pytest.mark.parametrize(
    "sentence",
    [
        "The nation’s bail law and the cheque’s drawer are separate topics.",
        "The Court’s and the State’s positions differ.",
    ],
)
def test_possessives_alone_are_balanced(sentence):
    assert not _unbalanced_quotes(sentence)


@pytest.mark.parametrize(
    "sentence",
    [
        "The Court called it ’bail is the rule’ in terms.",  # ’…’ around a phrase
        "The judges’ view was that bail is the rule.",  # ’ at the end of a word
        "He said ’tis the rule and bail follows.",  # ’ at the start of a word
        "Section 138’s notice period is thirty days.",  # next to a digit
        "Section 138’ is the notice rule.",  # digit before, space after
        "The rule ’ applies to bail.",  # next to a space
        "Bail is the rule.’",  # at the very end
        "’Bail is the rule.",  # at the very start
        "The nation’s rule is that ’bail is the rule.",  # possessive + stray mark
        "The nation’s rule is that bail is the rule.’",  # possessive + stray at end
    ],
)
def test_every_other_use_of_the_curly_mark_still_fails_closed(sentence):
    assert _unbalanced_quotes(sentence)


async def test_possessive_plus_a_stray_mark_is_removed_by_verify(world):
    text = "The Court’s view is that ’bail is the rule and jail the exception [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert kept(ans) == []


async def test_possessive_plus_a_quoted_span_in_the_passage_passes(world):
    text = f"The Court’s view is “{CLAIM}” [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert kept(ans) == ["S1"] and CLAIM in ans.text
    assert not ans.removed


async def test_possessive_plus_a_quoted_span_not_in_the_passage_fails_check_3(world):
    text = "The Court’s view is “bail is never granted in any case” [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert kept(ans) == []
    assert [r.reason for r in ans.removed] == ["quote_not_found"]


async def test_possessive_beside_a_curly_single_quoted_span_stays_strict(world):
    # a ‘…’ span can close on a letter-flanked mark, so the count is not relaxed here
    text = f"The nation’s Court wrote ‘{CLAIM}’ [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert _unbalanced_quotes("The nation’s Court wrote ‘x’ here.")
    assert kept(ans) == []


async def test_case_is_still_compared_exactly(world):
    text = "The Court’s view is “Bail is the rule, jail the exception” [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert kept(ans) == []  # capital B: not in the passage


async def test_a_real_single_curly_quotation_is_still_checked_against_the_passage(
    world,
):
    bad = "The Court said ‘bail is never granted in any case’ [S1]."
    good = f"The Court said ‘{CLAIM}’ [S1]."
    assert kept(await verify(world.draft(bad), world.passages, world.deps)) == []
    assert kept(await verify(world.draft(good), world.passages, world.deps)) == ["S1"]
