"""ONE harmless real call per Jev job. Skipped unless JEV_API_KEY is set (in .env or
the environment) AND typesafe-sdk is installed. Synthetic one-sentence text only; the
key is never printed. Run: .venv/bin/pytest tests/core/test_jev_live.py -s"""

from __future__ import annotations

import importlib.util

import pytest

from adapters.jev import JevClient
from core.contracts import Passage
from core.settings import Settings

# NOTE: the tests/core/conftest autouse fixture does not touch JEV_API_KEY.
_s = Settings()
HAVE_KEY = bool(_s.JEV_API_KEY.get_secret_value())
HAVE_SDK = importlib.util.find_spec("typesafe_sdk") is not None

pytestmark = pytest.mark.skipif(
    not (HAVE_KEY and HAVE_SDK), reason="JEV_API_KEY unset or typesafe-sdk missing"
)

PASSAGE = Passage(
    record_id="live1",
    text="Section 302 of the Indian Penal Code prescribes punishment for murder.",
)


@pytest.fixture
def live() -> JevClient:
    return JevClient(Settings(JEV_TIMEOUT_MS=10000))


async def test_live_scope_and_safety(live):
    d = await live.decide("What is the punishment for murder under the IPC?")
    print("scope/safety:", d.scope, d.safety, "tokens:", live.input_tokens)
    assert d.scope and d.safety


async def test_live_gate(live):
    r = await live.rate_passage("What is the punishment for murder?", PASSAGE)
    print("gate:", r, "tokens in/out:", live.input_tokens, live.output_tokens)
    assert r[0] in ("answers", "partly", "not_relevant")


async def test_live_claim_support(live):
    r = await live.claim_support("Murder is punished under section 302.", PASSAGE)
    print("claim:", r, "tokens in/out:", live.input_tokens, live.output_tokens)
    assert r in ("supports", "partly", "does_not_support")
