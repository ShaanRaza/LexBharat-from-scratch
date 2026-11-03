"""A137 (F6, STRICT): a sentence with no source marker is removed.

Each test fails if the old exemption (`if labels and not passed`) comes back."""

import pytest

from core.verify import verify

GOOD = "Bail is the rule and jail the exception under Article 21 [S1]."


def reasons(world):
    return [r.reason for _, _, r in world.citation_log.rows]


@pytest.mark.parametrize(
    "unmarked",
    [
        "Based on the passages provided, here are the points:",
        "Therefore, no information can be provided from the text.",
        "Courts must always grant bail in every case.",
        "See https://example.org/more for details.",
    ],
)
async def test_an_unmarked_sentence_is_removed_and_the_cited_one_stays(world, unmarked):
    ans = await verify(world.draft(f"{unmarked}\n{GOOD}"), world.passages, world.deps)
    assert unmarked not in ans.text
    assert "Bail is the rule" in ans.text
    assert [c.source_id for c in ans.citations] == ["S1"]
    # removal is silent: no note, no log row (an intro is not a failed authority)
    assert not ans.removed and "could not be verified" not in ans.text
    assert world.citation_log.rows == []


async def test_all_unmarked_leaves_no_citation_so_the_turn_is_not_found(world):
    ans = await verify(
        world.draft("Bail is a right. It is never refused."),
        world.passages,
        world.deps,
    )
    assert ans.text == "" and ans.citations == ()


@pytest.mark.parametrize(
    "welded",
    [
        "![x](https://evil.example/c.png?d=1)",
        "2023 amendments allow any arrest.",
        "and the court may also order damages.",
    ],
)
async def test_text_welded_after_a_marker_is_cut(world, welded):
    """_BOUNDARY does not split before a lowercase letter, digit or '!', so this text
    shares a 'sentence' with a marker. It still carries no marker of its own."""
    ans = await verify(world.draft(f"{GOOD} {welded}"), world.passages, world.deps)
    assert welded not in ans.text
    assert "Bail is the rule" in ans.text


async def test_a_marker_mid_sentence_is_untouched(world):
    text = "Bail is the rule [S1] and jail the exception [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert ans.text == text


async def test_an_unmarked_recalled_case_is_still_logged_not_retrieved(world):
    """Strict is added AFTER the existing checks: those still log their own reasons."""
    text = f"As held in Maneka Gandhi v. Union of India, liberty is wide.\n{GOOD}"
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert "Maneka" not in ans.text
    assert reasons(world) == ["not_retrieved"]


@pytest.mark.parametrize("abbr", ["Messrs.", "cl.", "Cl."])
async def test_an_abbreviation_does_not_split_a_cited_sentence_into_a_stray_fragment(
    world, abbr
):
    """Seen in the A137 measurement: 'The appellant, Messrs.' and 'Even if the order be
    referred to cl.' were cut off their sentence, and under strict the fragment is
    removed while its tail survives, so the answer would open mid-sentence."""
    text = f"The appellant, {abbr} Bail is the rule and jail the exception [S1]."
    ans = await verify(world.draft(text), world.passages, world.deps)
    assert ans.text == text
