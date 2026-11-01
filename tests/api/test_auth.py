"""Login check fails closed: no token, bad token, or a broken adapter = denied."""

from adapters.firebase import AuthUser
from tests.api.conftest import auth


def test_no_token_is_401_in_standard_error_format(client):
    r = client.get("/api/v1/me")
    assert r.status_code == 401
    body = r.json()["error"]
    assert body["code"] == "unauthenticated" and body["request_id"]
    assert r.headers["x-request-id"] == body["request_id"]


def test_bad_token_is_401(client):
    r = client.get("/api/v1/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_wrong_scheme_is_401(client):
    assert (
        client.get("/api/v1/me", headers={"Authorization": "tok:alice"}).status_code
        == 401
    )


def test_adapter_crash_denies(make_client):
    class Broken:
        async def verify_token(self, t):
            raise ConnectionError("firebase down")

    c = make_client(verifier=Broken())
    r = c.get("/api/v1/me", headers=auth())
    assert r.status_code == 503 and r.json()["error"]["code"] == "service_unavailable"


def test_default_verifier_denies_everyone(make_client):
    c = make_client(verifier=None)  # nothing wired -> DenyAll
    assert c.get("/api/v1/me", headers=auth()).status_code == 503


def test_empty_uid_is_denied(make_client):
    class Empty:
        async def verify_token(self, t):
            return AuthUser("", None)

    assert (
        make_client(verifier=Empty()).get("/api/v1/me", headers=auth()).status_code
        == 401
    )


def test_every_protected_route_needs_login(client):
    for method, path in [
        ("get", "/api/v1/me"),
        ("get", "/api/v1/conversations"),
        ("post", "/api/v1/conversations"),
        ("get", "/api/v1/conversations/x"),
        ("post", "/api/v1/conversations/x/messages"),
        ("get", "/api/v1/cases/x"),
        ("get", "/api/v1/search?q=a"),
        ("post", "/api/v1/feedback"),
        ("get", "/api/v1/documents/x"),
        ("delete", "/api/v1/me"),
    ]:
        assert getattr(client, method)(path).status_code == 401, path


def test_public_routes_need_no_login(client):
    assert client.get("/api/v1/healthz").status_code == 200
    assert client.get("/api/v1/stats").status_code in (200, 503)
