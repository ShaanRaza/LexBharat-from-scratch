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
