"""The answer prompt must keep its no-outside-authority rules."""

from pathlib import Path

PROMPT = Path(__file__).resolve().parents[2] / "core" / "prompts" / "answer.txt"


def test_answer_prompt_forbids_outside_authorities_and_requires_source_ids():
    t = " ".join(PROMPT.read_text().split())
    assert "Do NOT name, cite or describe any case, Act or section that is not" in t
    assert "S1-S8" in t
    # A137: every sentence ends in a marker, and says an unmarked one is deleted
    assert "Every sentence you write must end with the source id of the passage" in t
    assert "A sentence with no source id will be deleted" in t


def test_answer_prompt_has_no_literal_source_id_example():
    """The prompt once said 'for example [S2]'; with only S1 kept the model copied it, and
    check 1 correctly removed a citation to a passage that does not exist, so a correct
    answer came back not_found (q010, q036, q075). The template must carry no literal
    [S<n>] at all; the only ids the model sees are the ones printed on the passages."""
    import re

    assert re.search(r"\[S\d+\]", PROMPT.read_text()) is None


def test_answer_prompt_says_one_passage_can_hold_several_sections():
    """The chunker appends an amended section to the chunk before it, so a passage can hold
    two sections. Shown IPC 33 and 34 in one chunk, the model cited the second as [S2]
    though only S1 existed. The prompt must say a passage keeps its one id."""
    t = " ".join(PROMPT.read_text().split())
    assert "One passage can hold more than one section or provision" in t
    assert "never by a new number" in t


def test_the_built_prompt_shows_only_the_labels_that_exist():
    from core.answer import build_prompt
    from core.contracts import GateResult, Passage, RewrittenQuery

    p = Passage(
        source_id="S1",
        record_id="r1",
        kind="act_section",
        title="The Test Act",
        text="Section text.",
        citation_string=None,
        score=1.0,
    )
    prompt = build_prompt(
        RewrittenQuery("what does it say"),
        GateResult(passages=(p,), confidence=1.0),
        [],
    )
    assert "[S1]" in prompt
    assert not any(f"[S{n}]" in prompt for n in range(2, 10))
