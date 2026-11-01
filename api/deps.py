"""Builds the real pipeline (core's run_pipeline + Deps) for production.

Plain words: this is the one place the API learns how to assemble core's dependencies.
It returns None (route answers 503) until core publishes a `build_deps` factory, and
it checks SEAL_KEY at startup so answers can never go out unsealed.
"""

from __future__ import annotations

import importlib


class RealPipeline:
    def __init__(self, deps):
        self.deps = deps

    async def run(self, request):
        from core.contracts import run_pipeline

        return await run_pipeline(request, self.deps)

    def stream(self, result):
        from core.contracts import stream_events

        return stream_events(result)


def build_pipeline(core_settings, repo):
    from core.verify import assert_seal_key_configured

    assert_seal_key_configured()  # refuse to boot without a seal key
    try:
        factory = importlib.import_module("core.factory").build_deps
    except (ImportError, AttributeError):
        return None  # not wired yet: /messages answers 503, nothing is faked
    return RealPipeline(
        factory(core_settings, usage=repo, store=repo, citation_log=repo)
    )
