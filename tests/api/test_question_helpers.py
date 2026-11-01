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
