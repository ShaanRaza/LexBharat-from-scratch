"""The fence fix, option (b): every model call site that expects JSON asks for it with a response schema, and the one that
does not (claim_support) never does. Pipeline steps 2, 3, 6-7, 10; nothing here decides anything.

Why a class-wide test: the bug was "Gemini fences its JSON, the strict parser rejects it", and it hit three call sites at
once (rewrite, decide, the gate). A fix at one site would leave the others broken, so these tests pin the whole class:
each JSON site passes its schema, claim_support passes none, the schemas' allowed values are the contract's own Literals,
and the strict parsers still reject a fenced reply (the injection tests depend on that).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

import pytest

from adapters.decisions import DecisionUnavailable, GeminiDecider
from adapters.llm import FakeLLM
from core import coverage, llm_schemas
from core.contracts import (
    Memory,
    Passage,
    PipelineRequest,
    Rating,
    SafetyClass,
    ScopeClass,
)
from core.followups import suggest_followups
from core.rewrite import rewrite
from core.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
S = Settings(_env_file=None)


def _passage() -> Passage:
    return Passage(record_id="r1", text="Whoever commits murder shall be punished.")


async def test_decide_and_rate_passage_pass_their_schemas_and_claim_support_none():
    llm = FakeLLM(
        lambda p, s: (
            json.dumps(
                {
                    "scope": "in_scope",
                    "safety": "normal",
                    "rating": "answers",
                    "score": 1,
                }
            )
            if "JSON" in p
            else "supports"
        )
    )
    d = GeminiDecider(llm, S)
    await d.decide("what is murder")
    await d.rate_passage("what is murder", _passage())
    await d.claim_support("Murder is punished.", _passage())
    assert llm.schemas == [llm_schemas.DECIDE, llm_schemas.RATE_PASSAGE, None]


async def test_rewrite_and_followups_pass_their_schemas():
    rw = FakeLLM(json.dumps({"query": "murder punishment"}))
    deps = SimpleNamespace(llm=rw, settings=S)
    await rewrite(PipelineRequest("u", "what is murder"), Memory((), ""), deps)
    assert rw.schemas == [llm_schemas.REWRITE]
    fu = FakeLLM(json.dumps({"questions": []}))
    await suggest_followups("q", "a", SimpleNamespace(llm=fu, settings=S))
    assert fu.schemas == [llm_schemas.FOLLOWUPS]


def test_every_complete_call_in_the_product_is_accounted_for():
    """AST sweep of core/ and adapters/: a call of `.complete(` either carries json_schema= (a JSON site) or is one of the
    prose sites. A new call site that parses JSON without a schema fails here until someone decides which it is."""
    json_sites, prose_sites = set(), set()
    for folder in ("core", "adapters"):
        for f in sorted((ROOT / folder).glob("*.py")):
            for node in ast.walk(ast.parse(f.read_text())):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "complete"
                    # llm.py is the gateway; telemetry.py's TracedLLM only forwards the caller's schema
                    and f.name not in ("llm.py", "telemetry.py")
                ):
                    has = any(k.arg == "json_schema" for k in node.keywords)
                    (json_sites if has else prose_sites).add(f"{folder}/{f.name}")
    assert (
        json_sites
        == {
            "adapters/decisions.py",  # _ask: schema passed in by decide and rate_passage, None by claim_support
            "core/followups.py",
            "core/rewrite.py",
        }
    )
    assert prose_sites == {"core/answer.py", "core/improve.py"}  # free text, not JSON


def test_the_schemas_allowed_values_are_the_contracts_own():
    assert llm_schemas.DECIDE["properties"]["scope"]["enum"] == list(
        get_args(ScopeClass)
    )
    assert llm_schemas.DECIDE["properties"]["safety"]["enum"] == list(
        get_args(SafetyClass)
    )
    assert llm_schemas.RATE_PASSAGE["properties"]["rating"]["enum"] == list(
        get_args(Rating)
    )
    # and the prompt offers the same scope choices the schema allows
    assert coverage.scope_choices().split("|") == list(get_args(ScopeClass))


@pytest.mark.parametrize(
    "schema",
    [
        llm_schemas.DECIDE,
        llm_schemas.RATE_PASSAGE,
        llm_schemas.REWRITE,
        llm_schemas.FOLLOWUPS,
    ],
)
def test_each_schema_requires_what_its_parser_requires(schema):
    assert schema["type"] == "object" and schema["required"]
    assert set(schema["required"]) <= set(schema["properties"])


async def test_the_strict_parsers_still_reject_a_fenced_reply():
    fenced = '```json\n{"rating": "answers", "score": 1}\n```'
    with pytest.raises(DecisionUnavailable):
        await GeminiDecider(FakeLLM(fenced), S).rate_passage("q", _passage())
    out = await rewrite(
        PipelineRequest("u", "what is murder"),
        Memory((), ""),
        SimpleNamespace(llm=FakeLLM('```json\n{"query": "x"}\n```'), settings=S),
    )
    assert out.query == "what is murder"  # fell back to the user's own words, as before
