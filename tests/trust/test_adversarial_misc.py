# ruff: noqa: E501
"""More attacks: the usage meter (exactly once per answer, never by a helper), the one
user-filtered search function, and the HTTP routes behind a hostile pipeline."""

from __future__ import annotations

import asyncio

import pytest
from adversarial_helpers import REQUEST, make_deps
from fastapi.testclient import TestClient

from adapters.firebase import FakeAuth
from adapters.memory import FakeStore
from api.bridge import FakePipeline
from api.config import ApiSettings
from api.main import create_app
from api.repo import MemoryRepo
from core.contracts import Footer, PipelineRequest, PipelineResult, run_pipeline
from core.followups import Followups
from core.improve import Improved
from core.save import save
from core.settings import Settings, get_settings
from core.user_search import search_my_work
from core.verify import seal_answer

FOOTER = Footer("2026-08-31", "v2026.08")


def answered(cache_hit=False) -> PipelineResult:
    return PipelineResult(
        "answered", seal_answer("Bail [S1].", [], []), FOOTER, cache_hit=cache_hit
    )


# ---- usage meter: once per fresh answer, never otherwise ------------------------------
async def test_each_fresh_answer_is_counted_exactly_once_and_repeats_are_free():
    deps = make_deps()
    for _ in range(4):
        res = await run_pipeline(REQUEST, deps)
        assert res.outcome == "answered"
    assert deps.usage.counts == {"u1": 1}  # run 1 counted; runs 2-4 were cache hits


@pytest.mark.parametrize(
    "result",
    [
        PipelineResult("not_found", None, FOOTER),
        PipelineResult("out_of_scope", None, FOOTER, "out_of_scope:x"),
        PipelineResult("usage_limit", None, FOOTER),
        PipelineResult("error", None, FOOTER, error="Boom"),
    ],
)
async def test_nothing_that_is_not_an_answer_is_counted(result):
    deps = make_deps()
    await save(PipelineRequest("u1", "q"), result, deps)
    assert deps.usage.counts == {}


async def test_a_cache_hit_is_never_counted_even_if_saved_twice():
    deps = make_deps()
    r = answered(cache_hit=True)
    await save(PipelineRequest("u1", "q"), r, deps)
    await save(PipelineRequest("u1", "q"), r, deps)
    assert deps.usage.counts == {}


async def test_a_failed_save_then_a_retry_must_not_deliver_a_free_answer():
    """Step 11 saves, THEN counts. If the save fails after the answer was cached, the
    retry is a free cache hit: one answer delivered, none counted."""

    class FlakyStore(FakeStore):
        calls = 0

        async def save(self, request, result):
            FlakyStore.calls += 1
            if FlakyStore.calls == 1:
                raise ConnectionError("database went away")
            await super().save(request, result)

    deps = make_deps(store=FlakyStore())
    with pytest.raises(ConnectionError):
        await run_pipeline(REQUEST, deps)  # answer computed + cached, save blew up
    second = await run_pipeline(REQUEST, deps)  # the user retries
    assert second.outcome == "answered"
    assert sum(deps.usage.counts.values()) == 1  # delivered once => counted once


async def test_two_identical_requests_in_flight_never_count_more_than_two():
    deps = make_deps()
    a, b = await asyncio.gather(
        run_pipeline(REQUEST, deps), run_pipeline(REQUEST, deps)
    )
    assert a.outcome == b.outcome == "answered"
    assert (
        1 <= sum(deps.usage.counts.values()) <= 2
    )  # both computed => both paid, no more


# ---- the shared user-filtered search function ------------------------------------------
class Rows:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    async def search_user_work(self, user_id, q, limit):
        self.calls.append((user_id, q, limit))
        return self.rows


@pytest.mark.parametrize("uid", ["", " ", "\t", "\n", None])
async def test_a_missing_or_blank_user_is_refused_before_the_repository_is_touched(uid):
    repo = Rows([])
    with pytest.raises((PermissionError, AttributeError, TypeError)):
        await search_my_work(repo, uid, "bail")
    assert repo.calls == []


@pytest.mark.parametrize(
    "row",
    [
        {"user_id": "bob"},
        {"user_id": "alice "},  # trailing space
        {"user_id": "Alice"},
        {"user_id": "alicе"},  # Cyrillic е
        {"user_id": "alice​"},
        {"user_id": None},
        {},
        {"user_id": ["alice"]},
        {"owner": "alice"},
    ],
)
async def test_one_foreign_or_malformed_row_poisons_the_whole_result(row):
    ok = {"user_id": "alice", "kind": "message"}
    with pytest.raises(PermissionError):
        await search_my_work(Rows([ok, row, ok]), "alice", "bail")


async def test_the_users_own_rows_pass_whatever_the_id_type():
    import uuid

    uid = uuid.uuid4()
    rows = [{"user_id": str(uid)}, {"user_id": uid}]
    assert len(await search_my_work(Rows(rows), str(uid), "bail")) == 2


@pytest.mark.parametrize("limit", [-5, 0, 1, 50, 51, 10**9])
async def test_the_row_limit_is_clamped_whatever_the_caller_asks(limit):
    repo = Rows([])
    await search_my_work(repo, "alice", "bail", limit)
    assert 1 <= repo.calls[0][2] <= 50


async def test_the_query_is_trimmed_and_capped_before_it_reaches_the_repository():
    repo = Rows([])
    await search_my_work(repo, "alice", "  " + "x" * 5000 + "  ")
    assert len(repo.calls[0][1]) == 200


# ---- the routes behind a hostile pipeline ----------------------------------------------
class Hostile(FakePipeline):
    async def followups(self, question, answer_text):
        return Followups(
            ["What does [S1] hold?", "What did Maneka v. Union decide?", "What is bail?"],
            1, 1, "m",
        )  # fmt: skip

    async def improve(self, text):
        return Improved(
            "Can bail be refused? See [S1] and Maneka v. Union.", True, 1, 1, "m"
        )


@pytest.fixture
def hostile_client(monkeypatch):
    for cls in (Settings, ApiSettings):
        monkeypatch.setitem(cls.model_config, "env_file", None)
    get_settings.cache_clear()
    repo = MemoryRepo()
    app = create_app(
        api_settings=ApiSettings(APP_ENV="test", WEB_ORIGIN="https://web.example"),
        core_settings=Settings(),
        repo=repo, verifier=FakeAuth(), pipeline=Hostile(repo),
    )  # fmt: skip
    return TestClient(app)


def _auth():
    return {"Authorization": "Bearer tok:alice"}


@pytest.mark.xfail(
    strict=True,
    reason="BREAK (low): the follow-ups ROUTE (api/routes/conversations.py) returns "
    "whatever the pipeline gives it; the marker filter lives only in core/followups.py "
    "and the browser. A different pipeline implementation could serve markers",
)
def test_the_followups_route_never_serves_a_marker_even_from_a_careless_pipeline(
    hostile_client,
):
    c = hostile_client
    conv = c.post("/api/v1/conversations", json={}, headers=_auth()).json()
    c.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "q"},
        headers=_auth(),
    )
    msgs = c.get(f"/api/v1/conversations/{conv['id']}", headers=_auth()).json()[
        "messages"
    ]
    r = c.post(
        f"/api/v1/conversations/{conv['id']}/messages/{msgs[-1]['id']}/followups",
        headers=_auth(),
    )
    assert r.status_code == 200
    assert all("[" not in s and "S1" not in s for s in r.json()["suggestions"])


@pytest.mark.xfail(
    strict=True,
    reason="BREAK (low): the improve ROUTE returns the pipeline's text unchecked; only "
    "core/improve.py applies safe_improvement()",
)
def test_the_improve_route_never_serves_a_citation_from_a_careless_pipeline(
    hostile_client,
):
    r = hostile_client.post(
        "/api/v1/prompts/improve", json={"text": "bail"}, headers=_auth()
    )
    assert r.status_code == 200
    assert "[S1]" not in r.json()["text"] and "Maneka" not in r.json()["text"]


def test_a_route_error_from_the_pipeline_leaks_no_text(hostile_client):
    class Boom(Hostile):
        async def improve(self, text):
            raise RuntimeError("secret rec-adv-4411 Zorblax")

    hostile_client.app.state.pipeline = Boom(hostile_client.app.state.repo)
    r = hostile_client.post(
        "/api/v1/prompts/improve", json={"text": "bail"}, headers=_auth()
    )
    assert (
        r.status_code == 200
        and "Zorblax" not in r.text
        and r.json()["changed"] is False
    )
