"""The JSON shape each model call site asks for, sent as a response schema.

Plain words: Gemini wraps a JSON reply in a code fence (```json ... ```) unless it is
told to return JSON. The strict parsers (adapters/decisions.py, core/rewrite.py,
core/followups.py) reject a fence on purpose, because an injected passage could
otherwise smuggle a second answer inside one (tests/security/
test_injection_gate_and_claim_check.py). So the fix is on the REQUEST: each call site
that expects JSON passes the schema below, the API returns bare JSON, and the parsers
do not change. `claim_support` is a one-word answer, not JSON, and never gets a schema
(tests/test_llm_schemas.py pins that).

Pipeline steps touched: 2 (Rewrite), 3 (Decide), 6-7 (rate passages / the gate),
10 (follow-ups). Nothing here decides anything.
"""

from __future__ import annotations

from typing import get_args

from core.contracts import Rating, SafetyClass, ScopeClass

_NULL_STRING = {"type": "string", "nullable": True}
_NULL_INT = {"type": "integer", "nullable": True}

DECIDE: dict = {
    "type": "object",
    "properties": {
        "scope": {"type": "string", "enum": list(get_args(ScopeClass))},
        "safety": {"type": "string", "enum": list(get_args(SafetyClass))},
        "court": _NULL_STRING,
        "year_from": _NULL_INT,
        "year_to": _NULL_INT,
        "act": _NULL_STRING,
        "act_year": _NULL_INT,
        "section": _NULL_STRING,
    },
    "required": ["scope", "safety"],
}

RATE_PASSAGE: dict = {
    "type": "object",
    "properties": {
        "rating": {"type": "string", "enum": list(get_args(Rating))},
        "score": {"type": "number"},
    },
    "required": ["rating", "score"],
}

REWRITE: dict = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "act": _NULL_STRING,
        "section": _NULL_STRING,
        "case_number": _NULL_STRING,
        "year": _NULL_INT,
    },
    "required": ["query"],
}

FOLLOWUPS: dict = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
    "required": ["questions"],
}
