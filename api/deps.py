"""Builds the real pipeline for production: core's Deps filled with real adapters.

Plain words: the one place the API assembles core's dependencies. Vendor clients come
from adapters/ (rule 1); the gate and the verifier are core's own functions, so every
answer passes through the verifier (core.gate.gate, core.verify.verify). The usage
meter, step-11 store and invented_citation_log writer are our PostgreSQL repo.

At startup we call core.verify.assert_seal_key_configured(): no SEAL_KEY, no boot.
"""

from __future__ import annotations

import logging

from core.contracts import Deps, run_pipeline, stream_events
from core.followups import suggest_followups
from core.improve import improve_question


class RealPipeline:
    def __init__(self, deps: Deps):
        self.deps = deps

    async def run(self, request, on_step=None):
        return await run_pipeline(request, self.deps, on_step)

    def stream(self, result):
        return stream_events(result)

    # Question helpers. Not pipeline steps; both call one cheap model and filter the
    # reply in plain Python (core/followups.py, core/improve.py).
    async def followups(self, question, answer_text):
        return await suggest_followups(question, answer_text, self.deps)

    async def improve(self, text):
        return await improve_question(text, self.deps)


def build_pipeline(core_settings, repo) -> RealPipeline:
    from adapters.cache import RedisCache
    from adapters.decisions import FallbackDecisions, GeminiDecider, JevClient
    from adapters.jev import begin_run
    from adapters.llm import LiteLLMClient
    from adapters.qdrant import QdrantStore
    from adapters.voyage import VoyageClient
    from core.gate import gate
    from core.verify import assert_seal_key_configured, verify

    assert_seal_key_configured()  # refuse to boot without a seal key
    llm = LiteLLMClient(core_settings)
    voyage = VoyageClient(core_settings)
    deps = Deps(
        settings=core_settings,
        embedder=voyage,
        reranker=voyage,
        vectors=QdrantStore(core_settings),
        llm=llm,
        decisions=FallbackDecisions(
            JevClient(core_settings), GeminiDecider(llm, core_settings), core_settings
        ),
        cache=RedisCache(core_settings),
        usage=repo,
        store=repo,
        citation_log=repo,
        gate=gate,
        verify=verify,
        begin_run=begin_run,
    )
    return RealPipeline(deps)


async def close_pipeline(pipeline) -> None:
    """Shutdown hook: close the decisions service (the Jev client). Safe when the
    pipeline was never built (None / fake mode) or has no aclose; never raises."""
    deps = getattr(pipeline, "deps", None)
    aclose = getattr(getattr(deps, "decisions", None), "aclose", None)
    if aclose is None:
        return
    try:
        await aclose()
    except Exception:  # noqa: BLE001  shutdown must never fail
        logging.getLogger("api.deps").warning("decisions aclose failed")
