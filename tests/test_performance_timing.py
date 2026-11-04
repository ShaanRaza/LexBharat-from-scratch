"""The latency measurement (evals/performance): the arithmetic and the guards, on synthetic numbers (CLAUDE.md section 10).

What these pin down: percentiles are percentiles (never an average), parallel vendor calls inside a step count once,
a window that overlaps another client on the shared instance is flagged contended, the instance is "quiet" only when
nothing else is on the port and the server is idle, a target passes on its p95, and the report writes its block into
METRICS.md without touching the rest of the file. The real figures come from the real run.
"""

from __future__ import annotations

import asyncio

import pytest

from evals.performance import report as rp
from evals.performance import timing as T


def test_percentiles_are_not_averages():
    vals = [0.1] * 94 + [5.0] * 6  # a fast product with a slow tail
    p50, p95 = T.p50_p95(vals)
    assert p50 == pytest.approx(0.1)
    assert p95 > 4.0  # the mean (0.39) would have hidden this
    assert T.p50_p95([]) == (None, None)


def test_parallel_vendor_calls_inside_a_step_count_once():
    step = T.Interval("gate", 10.0, 14.0)
    calls = [
        T.Interval("decision:rate_passage", 10.0, 12.0),
        T.Interval("decision:rate_passage", 10.5, 12.5),  # overlaps the first
        T.Interval("decision:rate_passage", 13.0, 14.0),
        T.Interval("voyage:rerank", 5.0, 6.0),  # outside the step
    ]
    assert T.vendor_share(step, calls, "decision:") == pytest.approx(
        3.5
    )  # 10.0-12.5 and 13.0-14.0
    assert T.vendor_share(step, calls, "voyage:") == 0.0
    assert T.union_seconds([(0, 1), (0.5, 2), (3, 4)]) == pytest.approx(3.0)


def test_a_step_wrapper_notes_when_sync_and_async_steps_ran():
    rec = T.Recorder()

    def sync_step():
        return 1

    async def async_step():
        await asyncio.sleep(0.01)
        return 2

    assert T.timed_step("remember", sync_step, rec)() == 1
    assert asyncio.run(T.timed_step("search", async_step, rec)()) == 2
    assert [s.name for s in rec.steps] == ["remember", "search"]
    assert rec.steps[1].seconds >= 0.01


def test_a_window_overlapping_another_client_is_contended():
    quiet = T.LoadSample(100.0, 12.0, 3.0, ())
    foreign = T.LoadSample(
        105.0, 40.0, 3.0, (5313,)
    )  # another session's process on the port
    own_load = T.LoadSample(110.0, 400.0, 5.0, ())  # our own hybrid query: 400% CPU, nobody else on the port
    samples = [quiet, foreign, own_load]
    assert T.is_contended(foreign) and not T.is_contended(quiet)
    assert not T.is_contended(own_load)  # high server CPU with no other client is our own query
    assert T.contended_between(samples, 99.0, 101.0) == []  # a quiet window
    assert T.contended_between(samples, 104.0, 106.0) == [foreign]
    assert T.contended_between(samples, 109.0, 111.0) == []


def test_the_instance_is_quiet_only_when_idle_and_alone():
    idle = T.LoadSample(0.0, 2.0, 1.0, ())
    assert T.is_quiet([idle, idle])
    assert not T.is_quiet([])  # no look at it, no claim
    assert not T.is_quiet([idle, T.LoadSample(1.0, 2.0, 1.0, (5313,))])
    assert not T.is_quiet([idle, T.LoadSample(1.0, 120.0, 1.0, ())])


def _row(
    qid,
    outcome="answered",
    first=2.0,
    full=4.0,
    search=0.2,
    rerank=0.3,
    scope="unfiltered",
    gate=1.0,
):
    return {
        "id": qid,
        "outcome": outcome,
        "scope": scope,
        "first_word_seconds": first,
        "full_answer_seconds": full,
        "steps": {
            "search": search,
            "rerank": rerank,
            "gate": gate,
            "decide": 0.5,
            "embed_query": 0.2,
        },
        "vendor_in_step": {"gate": {"decision": gate}},
        "calls": {"decision:rate_passage": [0.4, 0.6], "decision:decide": [0.5]},
    }


def test_a_target_passes_on_its_p95_and_the_search_stage_is_search_plus_rerank():
    rows = [_row(f"q{i}") for i in range(20)]
    rep = {t["measure"]: t for t in rp.build(rows)["targets"]}
    assert rep["Search stage (search + re-rank)"]["p95"] == pytest.approx(0.5)
    assert rep["Search stage (search + re-rank)"]["result"] == "PASS"
    assert rep["First word of a research answer"]["result"] == "PASS"
    slow = rows + [_row(f"s{i}", first=9.0, full=30.0) for i in range(5)]
    rep = {t["measure"]: t for t in rp.build(slow)["targets"]}
    assert rep["First word of a research answer"]["result"] == "**FAIL**"
    assert rep["Full research answer"]["result"] == "**FAIL**"


def test_only_answered_questions_count_for_the_answer_targets():
    rows = [_row("a"), _row("b", outcome="not_found", first=0.1, full=0.1)]
    rep = {t["measure"]: t for t in rp.build(rows)["targets"]}
    assert rep["First word of a research answer"]["n"] == 1


def test_step_three_is_the_longer_of_the_decision_and_the_embedding():
    assert rp.step3(_row("q")) == pytest.approx(0.5)


def test_the_report_block_is_replaced_in_place_and_the_rest_of_the_file_is_kept(
    tmp_path,
):
    f = tmp_path / "METRICS.md"
    f.write_text("# Metrics\n\nkeep me\n")
    rp.write_metrics(f, "block one")
    rp.write_metrics(f, "block two")
    text = f.read_text()
    assert text.count(rp.BEGIN) == 1 and "block two" in text and "block one" not in text
    assert text.startswith("# Metrics\n\nkeep me")


def test_the_render_names_the_vendor_split_for_a_failure():
    rows = [_row(f"q{i}", first=9.0) for i in range(10)]
    out = rp.render(rows, {}, "4 Nov 2026", "Conditions: a test.")
    assert "**FAIL**" in out and "median inside" in out and "decision" in out
