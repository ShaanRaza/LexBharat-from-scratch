"""Health, uploads, billing, organisations: routes whose backing logic is not in v1
core yet answer 501 (clear error) after the login check. Nothing is faked."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api import schemas as s
from api.auth import CurrentUser, User
from api.errors import ApiError

router = APIRouter()


@router.get("/healthz", response_model=s.HealthResponse)
async def healthz(request: Request):
    return s.HealthResponse(fake_pipeline=request.app.state.fake_pipeline)


def _off(what: str) -> ApiError:
    return ApiError(501, "feature_disabled", f"{what} is not built yet.")


def _uploads_gate(request: Request) -> None:
    if not request.app.state.core_settings.FEATURE_UPLOADS:
        raise ApiError(403, "feature_disabled", "Uploads are not available yet.")


@router.post("/documents/uploads", response_model=s.UploadCreated)
async def create_upload(
    body: s.UploadCreate, request: Request, user: CurrentUser = User
):
    _uploads_gate(request)
    raise _off("Uploads")


@router.get("/documents/{doc_id}", response_model=s.DocumentOut)
async def get_document(doc_id: str, request: Request, user: CurrentUser = User):
    _uploads_gate(request)
    raise _off("Uploads")


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, request: Request, user: CurrentUser = User):
    _uploads_gate(request)
    raise _off("Upload deletion")


@router.post("/billing/webhook")
async def billing_webhook():
    # Must verify the Razorpay signature before doing anything (adapters/razorpay.py).
    raise _off("Billing")


@router.post("/organisations", response_model=s.OrganisationOut)
async def create_org(body: s.OrganisationCreate, user: CurrentUser = User):
    raise _off("Organisations")


@router.post("/organisations/{org_id}/members")
async def invite_member(org_id: str, body: s.MemberInvite, user: CurrentUser = User):
    raise _off("Organisations")


@router.delete("/organisations/{org_id}/members")
async def remove_member(org_id: str, body: s.MemberRemove, user: CurrentUser = User):
    raise _off("Organisations")
