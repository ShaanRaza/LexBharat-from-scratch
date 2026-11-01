"""Health, request IDs, and the one error format (docs/API.md "Rules every route follows")."""

import pytest

PRIVATE_ROUTES = [
    ("GET", "/api/v1/me"),
    ("DELETE", "/api/v1/me"),
    ("GET", "/api/v1/me/export"),
    ("GET", "/api/v1/me/consents"),
    ("POST", "/api/v1/me/consents"),
    ("GET", "/api/v1/search?q=bail"),
    ("GET", "/api/v1/cases/abc"),
    ("POST", "/api/v1/conversations"),
    ("GET", "/api/v1/conversations"),
    ("GET", "/api/v1/conversations/00000000-0000-0000-0000-000000000001"),
    ("POST", "/api/v1/conversations/00000000-0000-0000-0000-000000000001/messages"),
    ("POST", "/api/v1/feedback"),
    ("POST", "/api/v1/documents/uploads"),
    ("GET", "/api/v1/documents/00000000-0000-0000-0000-000000000001"),
    ("DELETE", "/api/v1/documents/00000000-0000-0000-0000-000000000001"),
]


def test_healthz_ok_is_public(client):
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_healthz_database_down_gives_503_in_standard_format(env):
    env.store.healthy = False
    r = env.client.get("/api/v1/healthz")
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "unhealthy"
    assert "db down" not in r.text  # no internals leaked


def test_every_response_has_a_request_id(client):
    r = client.get("/api/v1/healthz")
    assert len(r.headers["x-request-id"]) >= 8


def test_good_request_id_is_echoed_and_bad_one_replaced(client):
    ok = client.get("/api/v1/healthz", headers={"X-Request-ID": "trace-12345678"})
    assert ok.headers["x-request-id"] == "trace-12345678"
    bad = client.get("/api/v1/healthz", headers={"X-Request-ID": "x\ny"})
    assert bad.headers["x-request-id"] != "x\ny"


def test_error_body_carries_the_same_request_id_as_the_header(client):
    r = client.get("/api/v1/me")  # no login
    assert r.status_code == 401
    assert r.json()["error"]["request_id"] == r.headers["x-request-id"]


def test_unknown_route_uses_standard_error_format(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message", "request_id"}
    assert r.json()["error"]["code"] == "not_found"


def test_validation_error_format_does_not_echo_input(client, env):
    r = client.post(
        "/api/v1/me/consents",
        headers=env.auth(),
        json={"notice_version": "SECRET-VALUE", "purpose": "x", "action": "explode"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"
    assert "SECRET-VALUE" not in r.text


def test_unexpected_error_is_500_with_nothing_internal(env):
    async def boom(*a, **k):
        raise RuntimeError("secret internal detail")

    env.store.get_case = boom
    r = env.client.get("/api/v1/cases/x", headers=env.auth())
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in r.text


@pytest.mark.parametrize(("method", "path"), PRIVATE_ROUTES)
def test_private_routes_reject_missing_login(client, method, path):
    r = client.request(method, path)
    assert r.status_code == 401, path
    assert r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize(("method", "path"), PRIVATE_ROUTES)
def test_private_routes_reject_a_bad_token(client, method, path):
    r = client.request(method, path, headers={"Authorization": "Bearer forged"})
    assert r.status_code == 401, path
    assert r.json()["error"]["code"] == "invalid_token"


def test_wrong_scheme_is_rejected(client):
    r = client.get("/api/v1/me", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401


def test_suspended_account_is_blocked(env):
    env.client.get("/api/v1/me", headers=env.auth())  # creates the user
    env.store.users["uid-alice"]["status"] = "suspended"
    r = env.client.get("/api/v1/me", headers=env.auth())
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "account_suspended"


def test_no_firebase_adapter_means_login_fails_closed(env):
    from api.deps import UnavailableVerifier

    env.app.state.token_verifier = UnavailableVerifier()
    r = env.client.get("/api/v1/me", headers=env.auth())
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "auth_unavailable"


def test_public_routes_need_no_login(env):
    env.store.add_act(
        record_id="a1", act_name="The Test Act", act_year=2000, section_number="1"
    )
    assert env.client.get("/api/v1/healthz").status_code == 200
    assert env.client.get("/api/v1/acts/the-test-act/sections/1").status_code == 200
