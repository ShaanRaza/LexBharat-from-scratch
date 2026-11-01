"""The eval scorer itself must count honestly (traps are never dropped)."""

from core.contracts import Footer, PipelineResult
from core.verify import seal_answer  # noqa: F401  (import registers the seal checker)
from evals.runner import run_set

FOOT = Footer("2026-08", "v2026.08")


async def test_trap_that_gets_an_answer_fails_the_gate():
    from core.contracts import Citation
    from core.verify import seal_answer as seal

    c = Citation("S1", "ghost", "verified", None, None, None)

    async def pipe(q):
        return PipelineResult("answered", seal("x [S1].", [c], []), FOOT)

    rep = await run_set([{"kind": "trap", "question": "?"}], pipe, corpus_ids={"real"})
    assert rep.trap_failures == 1 and rep.fabricated_reached_user == 1
    assert not rep.passes_launch_gate()


async def test_refusing_every_trap_passes():
    async def pipe(q):
        return PipelineResult("not_found", None, FOOT)

    rep = await run_set([{"kind": "trap", "question": "?"}] * 3, pipe, set())
    assert rep.trap_failures == 0 and rep.passes_launch_gate()
