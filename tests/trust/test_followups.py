"""Follow-up suggestions and the "Improve my question" helper.

Both produce QUESTIONS, never answers, and neither may cite anything: citations only
come from the verifier. These tests try to smuggle a citation through (a marker, a
bracket, a quotation, a case citation, a statement dressed as a question) and check
that the pipeline itself is untouched by either helper."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from adapters.llm import FakeLLM, LLMUnavailable
from core.followups import MAX_SUGGESTIONS, clean_followups, suggest_followups
from core.improve import improve_question, safe_improvement
from core.settings import get_settings
from core.verify import _MARKER as VERIFIER_MARKER  # the verifier's own marker shape

ROOT = Path(__file__).resolve().parents[2]


class _Deps:
    def __init__(self, llm):
        self.llm = llm
        self.settings = get_settings()


GOOD = [
    "What is the difference between bail and anticipatory bail?",
    "How does a court decide whether to grant bail?",
    "Can bail be cancelled after it is granted?",
]


# ---- follow-ups: the plain-Python filter ---------------------------------------
def test_good_questions_pass_and_are_capped_at_three():
    extra = GOOD + ["Why is bail the rule?", "When does bail lapse?"]
    assert clean_followups(extra) == GOOD
    assert len(clean_followups(extra)) == MAX_SUGGESTIONS


@pytest.mark.parametrize(
    "bad",
    [
        "What does [S1] say about bail?",  # marker
        "What does (S2) hold?",
        "What do [S1, S3] say?",
        "What does ［S1］ say?",  # full-width brackets
        "What does S3 say about bail?",  # bare label
        "What is the rule [see above]?",  # any bracketed span
        'What does "bail is the rule" mean?',  # a quotation from a record
        "What did the court mean by “bail is the rule”?",
        "Does (2020) 1 SCC 1 apply?",  # case citation
        "Is AIR 1978 SC 597 still good?",
        "Does Maneka v. Union apply?",  # a case name
        "What about Maneka versus Union of India?",
        "The Supreme Court held bail is the rule?",  # a statement ending in "?"
        "Bail is the rule.",  # not a question
        "What is bail? What is jail?",  # two sentences
        "What is bail?\nAnd jail?",
        "",
        "?" * 3,
        "What " + "word " * 60 + "?",  # too long
        123,
        None,
        {"q": "What is bail?"},
    ],
)
def test_anything_that_is_not_a_short_citation_free_question_is_dropped(bad):
    assert clean_followups([bad]) == []
    assert clean_followups([bad, GOOD[0]]) == [GOOD[0]]  # only the bad one goes


@pytest.mark.parametrize("label", ["S1", "S2", "S8", "s3"])
@pytest.mark.parametrize("fmt", ["[{}]", "({})", "[{}, S2]", "[ {} ]"])
def test_every_marker_shape_the_verifier_recognises_is_dropped(label, fmt):
    marker = fmt.format(label)
    assert VERIFIER_MARKER.search(marker)  # it IS a verifier marker
    assert clean_followups([f"What does {marker} say?"]) == []


def test_duplicates_are_removed():
    assert clean_followups([GOOD[0], GOOD[0].upper(), GOOD[1]]) == [GOOD[0], GOOD[1]]


# ---- follow-ups: the model call --------------------------------------------------
async def test_suggestions_are_filtered_after_the_model_and_never_see_labels():
    seen: list[str] = []

    def respond(prompt: str, system: str) -> str:
        seen.append(prompt)
        return json.dumps(
            {
                "questions": [
                    GOOD[0],
                    "What does [S1] hold?",
                    "Bail is the rule.",
                    GOOD[1],
                ]
            }
        )

    out = await suggest_followups(
        "What is bail?", "Bail is the rule [S1]. Jail is the exception (S2).",
        _Deps(FakeLLM(respond)),
    )  # fmt: skip
    assert out == [GOOD[0], GOOD[1]]
    assert not re.search(r"\[S\d\]|\(S\d\)", seen[0])  # the model never sees S-labels


@pytest.mark.parametrize(
    "reply", ["not json", "{}", '{"questions": "x"}', "[]", "null"]
)
async def test_junk_from_the_model_gives_no_suggestions(reply):
    assert await suggest_followups("q", "a", _Deps(FakeLLM(reply))) == []


async def test_model_down_gives_no_suggestions_not_an_error():
    class Down:
        async def complete(self, *a, **k):
            raise LLMUnavailable("down")

    assert await suggest_followups("q", "a", _Deps(Down())) == []


# ---- improve my question ---------------------------------------------------------
ORIGINAL = "can police arrest me without warrant for cheque bounce"


@pytest.mark.parametrize(
    "improved",
    [
        "Can police arrest without a warrant for cheque dishonour? [S1]",  # marker
        "Can police arrest without a warrant, as held in (2020) 1 SCC 1?",  # citation
        "Can police arrest, as in Arnesh Kumar v. State of Bihar, without warrant?",
        'Can police arrest without a warrant ("arrest is not routine")?',  # quotation
        "Can police arrest without warrant [see Section 41]?",  # a bracket
        "",
        "x" * 2000,
    ],
)
def test_improvement_that_cites_anything_is_rejected(improved):
    assert safe_improvement(ORIGINAL, improved) is None


def test_clean_improvement_is_accepted_and_tidied():
    got = safe_improvement(
        ORIGINAL,
        "  Can the police arrest   without a warrant\nfor a dishonoured cheque? ",
    )
    assert got == "Can the police arrest without a warrant for a dishonoured cheque?"


def test_a_citation_the_user_wrote_is_not_treated_as_added_by_the_helper():
    mine = "does AIR 1978 SC 597 still apply to passport impounding"
    assert safe_improvement(
        mine, "Does AIR 1978 SC 597 still apply to passport impounding?"
    )


async def test_improve_returns_the_users_own_text_when_the_helper_cites():
    llm = FakeLLM("Can police arrest without a warrant? See [S1].")
    out = await improve_question(ORIGINAL, _Deps(llm))
    assert out.changed is False and out.text == ORIGINAL


async def test_improve_returns_editable_text_when_clean():
    llm = FakeLLM("Can the police arrest without a warrant for cheque dishonour?")
    out = await improve_question(ORIGINAL, _Deps(llm))
    assert out.changed is True and out.text.endswith("dishonour?")


async def test_improve_when_model_is_down_keeps_the_users_text():
    class Down:
        async def complete(self, *a, **k):
            raise LLMUnavailable("down")

    out = await improve_question(ORIGINAL, _Deps(Down()))
    assert (out.text, out.changed) == (ORIGINAL, False)


# ---- neither helper is a pipeline step -------------------------------------------
def test_the_pipeline_does_not_know_about_either_helper():
    src = (ROOT / "core" / "pipeline.py").read_text()
    assert "followups" not in src and "improve" not in src
    from core.contracts import GATE_MAX_PASSAGES, RERANK_TOP_K, SEARCH_TOP_K

    assert (SEARCH_TOP_K, RERANK_TOP_K, GATE_MAX_PASSAGES) == (50, 10, 8)


def test_neither_helper_imports_the_verifier_or_builds_a_citation():
    for name in ("followups.py", "improve.py", "question_text.py"):
        src = (ROOT / "core" / name).read_text()
        assert "seal_answer" not in src and "VerifiedAnswer" not in src
        assert "Citation(" not in src
