"""Conversations: create, list (cursor), read, privacy between users."""

import uuid


def make(client, env, who="alice", **body):
    r = client.post("/api/v1/conversations", headers=env.auth(who), json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_read_back(client, env):
    c = make(client, env, title="Bail question")
    assert c["module"] == "research"
    assert c["message_count"] == 0
    r = client.get(f"/api/v1/conversations/{c['id']}", headers=env.auth())
    assert r.status_code == 200
    assert r.json()["messages"] == []
    assert r.json()["provenance"]["credit"].startswith("Data: Open India Law")


def test_invalid_module_is_422(client, env):
    r = client.post(
        "/api/v1/conversations", headers=env.auth(), json={"module": "magic"}
    )
    assert r.status_code == 422


def test_list_uses_cursor_pagination_newest_first(client, env):
    ids = [make(client, env, title=f"c{i}")["id"] for i in range(5)]
    first = client.get("/api/v1/conversations?limit=2", headers=env.auth()).json()
    assert [c["id"] for c in first["items"]] == [ids[4], ids[3]]
    assert first["next_cursor"]

    second = client.get(
        f"/api/v1/conversations?limit=2&cursor={first['next_cursor']}",
        headers=env.auth(),
    ).json()
    assert [c["id"] for c in second["items"]] == [ids[2], ids[1]]

    last = client.get(
        f"/api/v1/conversations?limit=2&cursor={second['next_cursor']}",
        headers=env.auth(),
    ).json()
    assert [c["id"] for c in last["items"]] == [ids[0]]
    assert last["next_cursor"] is None


def test_bad_cursor_is_400_in_standard_format(client, env):
    r = client.get("/api/v1/conversations?cursor=%%%", headers=env.auth())
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_cursor"


def test_limit_is_capped(client, env):
    r = client.get("/api/v1/conversations?limit=1000", headers=env.auth())
    assert r.status_code == 422


def test_list_shows_only_my_conversations(client, env):
    make(client, env, "alice")
    make(client, env, "bob")
    assert (
        len(
            client.get("/api/v1/conversations", headers=env.auth("alice")).json()[
                "items"
            ]
        )
        == 1
    )


def test_cannot_read_someone_elses_conversation(client, env):
    c = make(client, env, "alice")
    r = client.get(f"/api/v1/conversations/{c['id']}", headers=env.auth("bob"))
    assert r.status_code == 404  # 404, not 403: we do not confirm the ID exists


def test_unknown_conversation_is_404(client, env):
    r = client.get(f"/api/v1/conversations/{uuid.uuid4()}", headers=env.auth())
    assert r.status_code == 404


def test_cannot_attach_someone_elses_document(client, env):
    env.set_settings(FEATURE_UPLOADS=True)
    up = client.post(
        "/api/v1/documents/uploads", headers=env.auth("bob"), json={"filename": "f.pdf"}
    ).json()
    c = make(client, env, "alice", module="document", document_id=up["document_id"])
    assert env.store.conversations[uuid.UUID(c["id"])]["document_id"] is None
