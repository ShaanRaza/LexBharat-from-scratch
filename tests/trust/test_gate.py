"""Step 7: the answer-or-refuse gate."""

from types import SimpleNamespace

from adapters.decisions import FakeDecisions
from core.contracts import Passage, RewrittenQuery
from core.gate import gate
from core.settings import Settings


def deps(down=False):
    return SimpleNamespace(settings=Settings(), decisions=FakeDecisions(down=down))


def P(i, text, score=0.0):
    return Passage(record_id=f"r{i}", text=text, score=score)


Q = RewrittenQuery("bail article 21 liberty")


async def test_relevant_passages_labelled_s1_in_order_and_irrelevant_dropped():
    ps = [P(1, "tax on imports of wheat"), P(2, "bail article 21 liberty rule")]
    r = await gate(Q, ps, deps())
    assert [(p.source_id, p.record_id) for p in r.passages] == [("S1", "r2")]
    assert r.ratings["r1"] == "not_relevant"


async def test_none_clears_threshold_returns_not_found_empty():
    r = await gate(Q, [P(1, "wheat imports"), P(2, "customs duty")], deps())
    assert r.passages == () and r.confidence == 0.0


async def test_at_most_eight_survive():
    ps = [P(i, "bail article 21 liberty") for i in range(10)]
    r = await gate(Q, ps, deps())
    assert [p.source_id for p in r.passages] == [f"S{i}" for i in range(1, 9)]


async def test_only_top_ten_considered():
    ps = [P(i, "wheat") for i in range(10)] + [P(99, "bail article 21 liberty")]
    r = await gate(Q, ps, deps())
    assert r.passages == ()


async def test_below_threshold_partly_is_dropped():
    # 1 of 4 query words = 0.25 < 0.6
    r = await gate(Q, [P(1, "bail wheat")], deps())
    assert r.passages == ()


async def test_jev_down_falls_back_to_rerank_score_same_threshold():
    ps = [P(1, "x", score=0.9), P(2, "y", score=0.3)]
    r = await gate(Q, ps, deps(down=True))
    assert [p.record_id for p in r.passages] == ["r1"]


async def test_nothing_is_passed_through_when_jev_down_and_scores_low():
    r = await gate(Q, [P(1, "x", score=0.1)], deps(down=True))
    assert r.passages == ()
