"""Feedback, uploads (behind a switch), the Razorpay webhook."""

import hashlib
import hmac
import json
import uuid


def sign(body: bytes, secret="whsec_test") -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def event_body(sub_id="sub_1", status="active") -> bytes:
    return json.dumps(
        {"event": "subscription.activated",
         "payload": {"subscription": {"entity": {"id": sub_id, "status": status}}}}
    ).encode()  # fmt: skip


# ---- feedback ----------------------------------------------------------------------
def make_message(client, env, who="alice"):
    from api.pipeline import FinalAnswer

    cid = client.post("/api/v1/conversations", headers=env.auth(who), json={}).json()[
        "id"
    ]
    env.pipeline.events = [FinalAnswer(text="ok")]
    done = (
        client.post(
            f"/api/v1/conversations/{cid}/messages",
            headers=env.auth(who),
            json={"content": "q"},
        )
        .text.strip()
        .split("\n\n")[-1]
    )
    return json.loads(done.split("data: ")[1])["message_id"]


def test_feedback_saved_and_can_be_changed(client, env):
    mid = make_message(client, env)
    r = client.post(
        "/api/v1/feedback",
        headers=env.auth(),
        json={"message_id": mid, "rating": -1, "comment": "wrong"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "saved"}
    client.post(
        "/api/v1/feedback", headers=env.auth(), json={"message_id": mid, "rating": 1}
    )
    assert len(env.store.feedback) == 1  # one per user per message
    assert next(iter(env.store.feedback.values()))["rating"] == 1


def test_feedback_on_someone_elses_message_is_404(client, env):
    mid = make_message(client, env, "alice")
    r = client.post(
        "/api/v1/feedback",
        headers=env.auth("bob"),
        json={"message_id": mid, "rating": 1},
    )
    assert r.status_code == 404


def test_feedback_validates_rating(client, env):
    r = client.post(
        "/api/v1/feedback",
        headers=env.auth(),
        json={"message_id": str(uuid.uuid4()), "rating": 5},
    )
    assert r.status_code == 422


# ---- uploads: OFF by default ---------------------------------------------------------
def test_uploads_are_switched_off_by_default(client, env):
    doc = str(uuid.uuid4())
    for method, path, kw in [
        ("POST", "/api/v1/documents/uploads", {"json": {"filename": "a.pdf"}}),
        ("GET", f"/api/v1/documents/{doc}", {}),
        ("DELETE", f"/api/v1/documents/{doc}", {}),
    ]:
        r = client.request(method, path, headers=env.auth(), **kw)
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "feature_disabled"


def test_upload_flow_when_switched_on(client, env):
    env.set_settings(FEATURE_UPLOADS=True, UPLOAD_MAX_MB=1)
    r = client.post(
        "/api/v1/documents/uploads", headers=env.auth(),
        json={"filename": "bail.pdf", "mime_type": "application/pdf", "size_bytes": 1000},
    )  # fmt: skip
    assert r.status_code == 201
    doc_id = r.json()["document_id"]
    me = client.get("/api/v1/me", headers=env.auth()).json()
    assert (
        r.json()["upload_url"] == f"https://upload.example/uploads/{me['id']}/{doc_id}"
    )
    assert env.store.audit[-1]["action"] == "upload"

    got = client.get(f"/api/v1/documents/{doc_id}", headers=env.auth())
    assert got.json()["status"] == "uploaded"
    assert "storage_path" not in got.json()
    assert (
        client.get(f"/api/v1/documents/{doc_id}", headers=env.auth("bob")).status_code
        == 404
    )

    gone = client.delete(f"/api/v1/documents/{doc_id}", headers=env.auth())
    assert gone.status_code == 204
    assert env.queue.jobs[-1][0] == "delete_document"
    assert env.queue.jobs[-1][1]["storage_path"].endswith(doc_id)
    assert env.store.documents == {}
    assert (
        client.get(f"/api/v1/documents/{doc_id}", headers=env.auth()).status_code == 404
    )


def test_upload_size_limit(client, env):
    env.set_settings(FEATURE_UPLOADS=True, UPLOAD_MAX_MB=1)
    r = client.post(
        "/api/v1/documents/uploads", headers=env.auth(),
        json={"filename": "big.pdf", "size_bytes": 5 * 1024 * 1024},
    )  # fmt: skip
    assert r.status_code == 413


def test_audit_log_never_holds_document_text(client, env):
    env.set_settings(FEATURE_UPLOADS=True)
    client.post(
        "/api/v1/documents/uploads", headers=env.auth(), json={"filename": "a.pdf"}
    )
    assert set(env.store.audit[-1]) == {
        "user_id",
        "action",
        "target_id",
        "ip",
        "request_id",
    }


# ---- Razorpay webhook --------------------------------------------------------------------
def test_webhook_valid_signature_updates_subscription(client, env):
    env.store.subscriptions["sub_1"] = {
        "razorpay_subscription_id": "sub_1",
        "user_id": None,
        "status": "created",
    }
    body = event_body()
    r = client.post(
        "/api/v1/billing/webhook",
        content=body,
        headers={"X-Razorpay-Signature": sign(body)},
    )
    assert r.status_code == 200  # note: no Firebase token needed
    assert env.store.subscriptions["sub_1"]["status"] == "active"


def test_webhook_bad_signature_is_rejected_and_changes_nothing(client, env):
    env.store.subscriptions["sub_1"] = {
        "razorpay_subscription_id": "sub_1",
        "user_id": None,
        "status": "created",
    }
    body = event_body()
    for headers in ({"X-Razorpay-Signature": "0" * 64}, {}):
        r = client.post("/api/v1/billing/webhook", content=body, headers=headers)
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_signature"
    assert env.store.subscriptions["sub_1"]["status"] == "created"


def test_webhook_signature_covers_the_exact_body(client, env):
    body = event_body(status="active")
    tampered = event_body(status="cancelled")
    r = client.post(
        "/api/v1/billing/webhook",
        content=tampered,
        headers={"X-Razorpay-Signature": sign(body)},
    )
    assert r.status_code == 400


def test_webhook_with_no_secret_configured_accepts_nothing(client, env):
    env.set_settings(RAZORPAY_WEBHOOK_SECRET="")
    body = event_body()
    r = client.post(
        "/api/v1/billing/webhook",
        content=body,
        headers={"X-Razorpay-Signature": sign(body, "")},
    )
    assert r.status_code == 503


def test_webhook_signed_but_unrelated_event_is_ok_and_ignored(client, env):
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    r = client.post(
        "/api/v1/billing/webhook",
        content=body,
        headers={"X-Razorpay-Signature": sign(body)},
    )
    assert r.status_code == 200


def test_webhook_unknown_status_is_ignored(client, env):
    env.store.subscriptions["sub_1"] = {
        "razorpay_subscription_id": "sub_1",
        "user_id": None,
        "status": "created",
    }
    body = event_body(status="weird")
    client.post(
        "/api/v1/billing/webhook",
        content=body,
        headers={"X-Razorpay-Signature": sign(body)},
    )
    assert env.store.subscriptions["sub_1"]["status"] == "created"
