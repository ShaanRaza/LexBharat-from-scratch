"""Follow-up suggestions and "Improve my question" over HTTP (fake pipeline)."""

import pytest

from tests.api.conftest import auth


def _answered(client, uid="alice", text="What is bail?"):
    conv = client.post("/api/v1/conversations", json={}, headers=auth(uid)).json()
    client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": text},
        headers=auth(uid),
    )
    detail = client.get(f"/api/v1/conversations/{conv['id']}", headers=auth(uid)).json()
    return conv["id"], detail["messages"]


def _url(conv_id, msg_id):
    return f"/api/v1/conversations/{conv_id}/messages/{msg_id}/followups"


def test_followups_are_questions_with_no_marker(client):
    conv_id, msgs = _answered(client)
    assistant = msgs[-1]
    r = client.post(_url(conv_id, assistant["id"]), headers=auth())
    assert r.status_code == 200
    sug = r.json()["suggestions"]
    assert 1 <= len(sug) <= 3
    for q in sug:
        assert q.endswith("?") and "[S" not in q


def test_followups_only_for_an_assistant_answer_in_your_own_conversation(client):
    conv_id, msgs = _answered(client)
    user_msg, assistant = msgs[0], msgs[-1]
    assert user_msg["role"] == "user"
    assert client.post(_url(conv_id, user_msg["id"]), headers=auth()).status_code == 404
    assert client.post(_url(conv_id, "no-such"), headers=auth()).status_code == 404
    # Another user cannot ask for suggestions on alice's answer.
    r = client.post(_url(conv_id, assistant["id"]), headers=auth("mallory"))
    assert r.status_code == 404


def test_followups_need_a_login(client):
    conv_id, msgs = _answered(client)
    assert client.post(_url(conv_id, msgs[-1]["id"])).status_code == 401


def test_followups_failure_is_empty_not_an_error(make_client, repo):
    class Boom:
        async def followups(self, q, a):
            raise RuntimeError("model exploded with secret text")

    from api.bridge import FakePipeline

    pipe = FakePipeline(repo)
    pipe.followups = Boom().followups
    c = make_client(pipeline=pipe)
    conv_id, msgs = _answered(c)
    r = c.post(_url(conv_id, msgs[-1]["id"]), headers=auth())
    assert r.status_code == 200 and r.json() == {"suggestions": []}
    assert "secret text" not in r.text


def test_improve_returns_editable_text(client):
    r = client.post(
        "/api/v1/prompts/improve",
        json={"text": "bail for cheque bounce"},
        headers=auth(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["changed"] is True and "[S" not in body["text"]


@pytest.mark.parametrize("payload", [{"text": ""}, {"text": "x" * 4001}, {}])
def test_improve_validates_input(client, payload):
    r = client.post("/api/v1/prompts/improve", json=payload, headers=auth())
    assert r.status_code in (400, 422)


def test_improve_needs_a_login(client):
    assert client.post("/api/v1/prompts/improve", json={"text": "x"}).status_code == 401


def test_improve_failure_keeps_the_users_text(make_client, repo):
    from api.bridge import FakePipeline

    async def boom(text):
        raise RuntimeError("model exploded")

    pipe = FakePipeline(repo)
    pipe.improve = boom
    c = make_client(pipeline=pipe)
    r = c.post("/api/v1/prompts/improve", json={"text": "my question"}, headers=auth())
    assert r.json() == {"text": "my question", "changed": False}


def test_helpers_do_not_use_or_charge_the_answer_pipeline(client, repo):
    _answered(client)
    before = dict(repo.usage)
    client.post("/api/v1/prompts/improve", json={"text": "abc"}, headers=auth())
    assert repo.usage == before  # not an answer: the usage meter did not move


# ---- A52: rate limits per user per hour, and the spend figure ---------------------
from adapters.cache import FakeRateLimiter  # noqa: E402
from core.settings import Settings  # noqa: E402


def _limited(make_client, **limits):
    return make_client(core_settings=Settings(**limits))


def _improve(c, uid="alice"):
    return c.post("/api/v1/prompts/improve", json={"text": "bail"}, headers=auth(uid))


def test_improve_is_rate_limited_per_user_per_hour(make_client):
    c = _limited(make_client, RATE_LIMIT_IMPROVE_PER_HOUR=2)
    assert [_improve(c).status_code for _ in range(3)] == [200, 200, 429]
    r = _improve(c)
    assert (
        r.json()["error"]["code"] == "rate_limited" and r.json()["error"]["request_id"]
    )
    assert _improve(c, "bob").status_code == 200  # another user has their own count


def test_followups_are_rate_limited_per_user_per_hour(make_client):
    c = _limited(make_client, RATE_LIMIT_FOLLOWUPS_PER_HOUR=1)
    conv_id, msgs = _answered(c)
    url = _url(conv_id, msgs[-1]["id"])
    assert [c.post(url, headers=auth()).status_code for _ in range(2)] == [200, 429]


def test_the_two_helpers_have_separate_counts(make_client):
    c = _limited(
        make_client, RATE_LIMIT_IMPROVE_PER_HOUR=1, RATE_LIMIT_FOLLOWUPS_PER_HOUR=1
    )
    conv_id, msgs = _answered(c)
    assert _improve(c).status_code == 200
    assert c.post(_url(conv_id, msgs[-1]["id"]), headers=auth()).status_code == 200


def test_a_limit_of_none_switches_it_off(make_client):
    c = _limited(make_client, RATE_LIMIT_IMPROVE_PER_HOUR=None)
    assert all(_improve(c).status_code == 200 for _ in range(5))


def test_the_limit_comes_from_config_not_code(make_client):
    # the placeholder default is a setting, visible and changeable
    assert Settings().RATE_LIMIT_IMPROVE_PER_HOUR == 60
    assert Settings(RATE_LIMIT_IMPROVE_PER_HOUR=7).RATE_LIMIT_IMPROVE_PER_HOUR == 7


def test_if_the_counter_is_down_the_paid_call_is_refused(make_client):
    c = make_client(limiter=FakeRateLimiter(down=True))
    assert _improve(c).status_code == 429


def test_a_rate_limited_call_never_reaches_the_model_or_the_spend_figure(
    make_client, repo
):
    c = _limited(make_client, RATE_LIMIT_IMPROVE_PER_HOUR=1)
    _improve(c)
    _improve(c)
    assert len(repo.ai_calls) == 1  # the refused call cost nothing and is not counted


def test_neither_helper_moves_the_usage_meter_but_both_are_counted_as_spend(
    client, repo
):
    conv_id, msgs = _answered(client)
    meter = dict(repo.usage)
    client.post("/api/v1/prompts/improve", json={"text": "bail"}, headers=auth())
    client.post(_url(conv_id, msgs[-1]["id"]), headers=auth())
    assert repo.usage == meter  # the answer meter did not move
    assert [c.feature for _, c in repo.ai_calls] == ["improve", "followups"]
    assert len({u for u, _ in repo.ai_calls}) == 1  # both under the same user
    assert repo.ai_calls[0][1].tokens_in == 30 and repo.ai_calls[1][1].tokens_out == 40


async def test_daily_spend_includes_both_helpers(repo):
    from core.spend import AiCall

    await repo.record_ai_call("u", AiCall("improve", 30, 20, "m"))
    await repo.record_ai_call("u", AiCall("followups", 120, 40, "m"))
    [day] = await repo.daily_ai_spend()
    assert day["helper_calls"] == 2 and day["helper_tokens"] == 210
    assert day["tokens_in"] == 150 and day["tokens_out"] == 60
