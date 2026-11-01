"""Helpers for tests/core: build a Deps made only of fakes."""

from __future__ import annotations

from adapters.cache import FakeCache
from adapters.decisions import FakeDecisions
from adapters.llm import FakeLLM
from adapters.memory import FakeCitationLog, FakeStore, FakeUsageMeter
from adapters.voyage import FakeEmbedder, FakeReranker
from core.contracts import Deps


def make_deps(settings, store, gate, verify=None, **over) -> Deps:
    d = dict(
        settings=settings,
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        vectors=store,
        llm=FakeLLM('{"query": "placeholder"}'),
        decisions=FakeDecisions(),
        cache=FakeCache(),
        usage=FakeUsageMeter(),
        store=FakeStore(),
        citation_log=FakeCitationLog(),
        gate=gate,
        verify=verify,
    )
    d.update(over)
    return Deps(**d)
