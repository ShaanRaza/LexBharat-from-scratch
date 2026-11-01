"""Feedback, uploads (behind a switch), the Razorpay webhook, and health."""

import json
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request

from api.deps import (
    CurrentUser,
    JobQueue,
    UploadSigner,
    client_ip,
    current_user,
    queue_dep,
    settings_dep,
    signer_dep,
    store_dep,
    verify_razorpay_signature,
)
from api.errors import ApiError, request_id_var
from api.schemas import (
    DocumentOut,
    FeedbackIn,
    FeedbackOut,
    HealthOut,
    UploadOut,
    UploadRequest,
    WebhookOut,
)
from api.store import Store
from core.settings import Settings

router = APIRouter()


# ---- health (public; the deploy workflow's smoke test calls this) --------------------
@router.get("/healthz", response_model=HealthOut, tags=["health"], summary="Is it up?")
async def healthz(*, store: Annotated[Store, Depends(store_dep)]):
    try:
        await store.ping()
    except Exception:  # noqa: BLE001  (any failure means 'not healthy')
        # Say nothing about why; the details are in the logs.
        raise ApiError(503, "unhealthy", "Database is not reachable.") from None
    return HealthOut()


# ---- feedback ----------------------------------------------------------------
@router.post("/feedback", response_model=FeedbackOut, tags=["feedback"])
async def post_feedback(
    *,
    body: FeedbackIn,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
):
    saved = await store.add_feedback(
        user.id, body.message_id, body.rating, body.reason, body.comment
    )
    if not saved:
        raise ApiError(404, "not_found", "Message not found.")
    return FeedbackOut()


# ---- uploads (built, but OFF at launch: FEATURE_UPLOADS) -------------------------------
def _require_uploads(settings: Settings) -> None:
    if not settings.FEATURE_UPLOADS:
        raise ApiError(403, "feature_disabled", "Uploads are not available yet.")


@router.post(
    "/documents/uploads", response_model=UploadOut, status_code=201, tags=["documents"]
)
async def create_upload(
    *,
    body: UploadRequest,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    signer: Annotated[UploadSigner, Depends(signer_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    _require_uploads(settings)
    if (
        settings.UPLOAD_MAX_MB is not None
        and body.size_bytes is not None
        and body.size_bytes > settings.UPLOAD_MAX_MB * 1024 * 1024
    ):
        raise ApiError(413, "file_too_large", "That file is too large.")
    doc_id = uuid4()
    # The path starts with the user's ID, so a file is always filed under its owner.
    path = f"uploads/{user.id}/{doc_id}"
    url = await signer.presign_upload(path, body.mime_type)
    await store.create_document(
        doc_id, user.id, body.filename, body.mime_type, body.size_bytes, path
    )
    await store.add_audit(
        user.id, "upload", str(doc_id), client_ip(request), request_id_var.get()
    )
    return UploadOut(document_id=doc_id, upload_url=url)


@router.get("/documents/{doc_id}", response_model=DocumentOut, tags=["documents"])
async def get_document(
    *,
    doc_id: UUID,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    _require_uploads(settings)
    doc = await store.get_document(user.id, doc_id)
    if doc is None:
        raise ApiError(404, "not_found", "Document not found.")
    return doc


@router.delete("/documents/{doc_id}", status_code=204, tags=["documents"])
async def delete_document(
    *,
    doc_id: UUID,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    queue: Annotated[JobQueue, Depends(queue_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    """Hard delete: PostgreSQL text now; S3 file and Qdrant vectors via a job."""
    _require_uploads(settings)
    doc = await store.get_document(user.id, doc_id)
    if doc is None:
        raise ApiError(404, "not_found", "Document not found.")
    await queue.enqueue(
        "delete_document",
        user_id=str(user.id),
        document_id=str(doc_id),
        storage_path=doc["storage_path"],
    )
    await store.delete_document(user.id, doc_id)
    await store.add_audit(
        user.id, "delete", str(doc_id), client_ip(request), request_id_var.get()
    )


# ---- Razorpay webhook (no Firebase token; the SIGNATURE is the login) ---------------------
_RAZORPAY_STATUSES = {
    "created", "authenticated", "active", "pending",
    "halted", "cancelled", "completed", "expired", "paused",
}  # fmt: skip


@router.post("/billing/webhook", response_model=WebhookOut, tags=["billing"])
async def razorpay_webhook(
    *,
    request: Request,
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    secret = settings.RAZORPAY_WEBHOOK_SECRET.get_secret_value()
    if not secret:
        # With no secret we cannot check anything, so we accept nothing.
        raise ApiError(503, "webhook_not_configured", "Billing is not configured.")
    body = await request.body()  # the RAW bytes: the signature covers exactly these
    signature = request.headers.get("x-razorpay-signature", "")
    if not verify_razorpay_signature(body, signature, secret):
        raise ApiError(400, "invalid_signature", "Signature check failed.")
    try:
        payload = json.loads(body)
        entity = payload["payload"]["subscription"]["entity"]
        sub_id, status = entity["id"], entity["status"]
    except (ValueError, KeyError, TypeError):
        return WebhookOut()  # signed but not a subscription event: nothing to do
    if status in _RAZORPAY_STATUSES:
        await store.update_subscription_status(sub_id, status)
    return WebhookOut()
