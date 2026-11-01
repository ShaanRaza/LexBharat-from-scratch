"""/me, consents (DPDP), export, and account deletion."""

from datetime import UTC, datetime


def test_me_creates_the_user_and_shows_answers_left(env):
    env.set_settings(PLAN_LIMIT_FREE=5)
    r = env.client.get("/api/v1/me", headers=env.auth())
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["plan"] == "free"
    assert body["answers_limit"] == 5
    assert body["answers_used"] == 0
    assert body["answers_left"] == 5
    assert r.headers["x-answers-limit"] == "5"
    assert r.headers["x-answers-remaining"] == "5"


def test_me_with_no_limit_set_has_null_and_no_headers(client, env):
    r = client.get("/api/v1/me", headers=env.auth())
    assert r.json()["answers_limit"] is None
    assert r.json()["answers_left"] is None
    assert "x-answers-remaining" not in r.headers


def test_me_counts_this_months_usage(env):
    env.set_settings(PLAN_LIMIT_FREE=5)
    me = env.client.get("/api/v1/me", headers=env.auth()).json()
    env.store.usage.append(
        {
            "user_id": __import__("uuid").UUID(me["id"]),
            "date": datetime.now(UTC).date(),
            "requests": 2,
        }
    )
    r = env.client.get("/api/v1/me", headers=env.auth())
    assert r.json()["answers_used"] == 2
    assert r.json()["answers_left"] == 3
    assert r.headers["x-answers-remaining"] == "3"


def test_consent_give_list_withdraw(client, env):
    h = env.auth()
    give = client.post(
        "/api/v1/me/consents",
        headers=h,
        json={"notice_version": "2026-10-01", "purpose": "research", "action": "give"},
    )
    assert give.status_code == 200
    items = give.json()["items"]
    assert items[0]["notice_version"] == "2026-10-01"
    assert items[0]["withdrawn_at"] is None

    gone = client.post(
        "/api/v1/me/consents",
        headers=h,
        json={
            "notice_version": "2026-10-01",
            "purpose": "research",
            "action": "withdraw",
        },
    )
    assert gone.status_code == 200
    assert gone.json()["items"][0]["withdrawn_at"] is not None
    assert client.get("/api/v1/me/consents", headers=h).json()["items"][0][
        "withdrawn_at"
    ]


def test_withdraw_unknown_consent_is_404(client, env):
    r = client.post(
        "/api/v1/me/consents",
        headers=env.auth(),
        json={"notice_version": "v1", "purpose": "never-given", "action": "withdraw"},
    )
    assert r.status_code == 404


def test_consents_are_private_to_each_user(client, env):
    client.post(
        "/api/v1/me/consents",
        headers=env.auth("alice"),
        json={"notice_version": "v1", "purpose": "research", "action": "give"},
    )
    assert (
        client.get("/api/v1/me/consents", headers=env.auth("bob")).json()["items"] == []
    )


def test_export_has_data_and_writes_an_audit_row(client, env):
    h = env.auth()
    conv = client.post("/api/v1/conversations", headers=h, json={}).json()
    r = client.get("/api/v1/me/export", headers=h)
    assert r.status_code == 200
    data = r.json()["export"]
    assert data["account"]["email"] == "alice@example.com"
    assert data["conversations"][0]["id"] == conv["id"]
    assert env.store.audit[-1]["action"] == "export"
    assert env.store.audit[-1]["request_id"] == r.headers["x-request-id"]


def test_delete_account_removes_data_queues_cleanup_and_audits(client, env):
    h = env.auth()
    client.post("/api/v1/conversations", headers=h, json={})
    r = client.delete("/api/v1/me", headers=h)
    assert r.status_code == 200
    assert r.json() == {"status": "deleted", "external_cleanup": "queued"}
    assert env.store.users == {}
    assert env.store.conversations == {}
    job, args = env.queue.jobs[0]
    assert job == "delete_account"
    assert (
        args["firebase_uid"] == "uid-alice"
    )  # so the worker can delete the Firebase user
    assert env.store.audit[-1]["action"] == "delete"
    assert env.store.audit[-1]["user_id"] is None  # the person is gone; the trail stays


def test_delete_account_blocked_for_organisation_owner(client, env):
    client.get("/api/v1/me", headers=env.auth())
    env.store.org_owners.add(env.store.users["uid-alice"]["id"])
    r = client.delete("/api/v1/me", headers=env.auth())
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "owns_organisation"
    assert env.queue.jobs == []  # nothing external was queued
    assert "uid-alice" in env.store.users


def test_delete_account_does_not_delete_if_queue_is_down(client, env):
    client.get("/api/v1/me", headers=env.auth())
    env.queue.fail = True
    r = client.delete("/api/v1/me", headers=env.auth())
    assert r.status_code == 500
    assert "uid-alice" in env.store.users  # data kept, so the user can simply retry
