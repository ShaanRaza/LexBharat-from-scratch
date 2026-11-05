# ruff: noqa: E501
"""Shared set-up for the adversarial trust tests (test_adversarial_*.py).

These tests are written by a lane that did NOT write the code under test. They assert
the SECURE behaviour; a test that fails because the code is weak is marked
xfail(strict=True, reason="BREAK: ...") rather than "fixed" in the implementation."""

from __future__ import annotations

import asyncio
import re

from adapters.cache import FakeCache
from adapters.decisions import FakeDecisions
from adapters.llm import FakeLLM
from adapters.memory import FakeCitationLog, FakeStore, FakeUsageMeter
from adapters.qdrant import FakeVectorStore
from adapters.voyage import FakeEmbedder, FakeReranker
from core.contracts import Deps, PipelineRequest
from core.gate import gate
from core.settings import get_settings
from core.verify import verify

# Strings that must never reach a client before / outside the final citations event.
CASE_ID = "rec-adv-4411"
CASE_TITLE = "Zorblax versus Quuxington"
CASE_CITE = "(1987) 41 XYZ 777"
TEXT = (
    "Personal liberty under Article 21 cannot be curtailed except by procedure "
    "established by law, and bail is the rule while jail is the exception."
)
QUERY = "personal liberty bail"
REQUEST = PipelineRequest("u1", "Tell me about personal liberty and bail")
LEAKS = (CASE_ID, CASE_TITLE, CASE_CITE, "Zorblax", "Quuxington", "[S1]")


def scripted_llm() -> FakeLLM:
    def respond(prompt: str, system: str) -> str:
        if prompt.startswith("Turn the user's"):
            return '{"query": "%s"}' % QUERY
        m = re.search(r"\[S1\] (.*?)(?:\n\n|\Z)", prompt, re.S)
        words = m.group(1).split()[:12] if m else []
        return " ".join(words) + " [S1]."

    return FakeLLM(respond)


def make_deps(verify_fn=verify, **over) -> Deps:
    settings = get_settings()
    store = FakeVectorStore(settings)
    store.add_law(
        CASE_ID, TEXT, title=CASE_TITLE, citation=CASE_CITE,
        pdf_url="https://example.test/adv.pdf",
    )  # fmt: skip
    d = dict(
        settings=settings, embedder=FakeEmbedder(), reranker=FakeReranker(),
        vectors=store, llm=scripted_llm(), decisions=FakeDecisions(),
        cache=FakeCache(), usage=FakeUsageMeter(), store=FakeStore(),
        citation_log=FakeCitationLog(), gate=gate, verify=verify_fn,
    )  # fmt: skip
    d.update(over)
    return Deps(**d)


async def collect(gen, into: list) -> None:
    async for name, data in gen:
        into.append((name, data))


async def spin(cond, tries: int = 200) -> None:
    """Wait (without sleeping long) until cond() is true."""
    for _ in range(tries):
        if cond():
            return
        await asyncio.sleep(0.005)
    raise AssertionError("condition never became true")
