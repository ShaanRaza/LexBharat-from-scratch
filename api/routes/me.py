"""/me, consents, export, delete. Routes only: storage via app.state.repo."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api import schemas as s
from api.auth import CurrentUser, User
from api.errors import ApiError

router = APIRouter()

PLAN_LIMIT_NAME = {
    "free": "PLAN_LIMIT_FREE", "student": "PLAN_LIMIT_STUDENT",
    "pro": "PLAN_LIMIT_PRO", "chambers": "PLAN_LIMIT_CHAMBERS",
}  # fmt: skip


@router.get("/me", response_model=s.MeResponse)
async def me(request: Request, user: CurrentUser = User):
    limit = getattr(request.app.state.core_settings, PLAN_LIMIT_NAME[user.plan], None)
    used = await request.app.state.repo.answers_this_month(user.id)
    return s.MeResponse(
        id=user.id, email=user.email, name=user.name, role=user.role, plan=user.plan,
        answers_left_this_month=None if limit is None else max(limit - used, 0),
    )  # fmt: skip


@router.get("/me/consents", response_model=s.ConsentList)
async def list_consents(request: Request, user: CurrentUser = User):
    return s.ConsentList(items=await request.app.state.repo.list_consents(user.id))


@router.post("/me/consents", response_model=s.ConsentOut, status_code=201)
async def give_consent(body: s.ConsentIn, request: Request, user: CurrentUser = User):
    return await request.app.state.repo.add_consent(
        user.id, body.notice_version, body.purpose
    )


@router.delete("/me/consents", response_model=s.Ok)
async def withdraw_consent(
    body: s.ConsentWithdraw, request: Request, user: CurrentUser = User
):
    if not await request.app.state.repo.withdraw_consent(user.id, str(body.consent_id)):
        raise ApiError(404, "not_found", "Consent not found.")
    return s.Ok()


def _not_built(what: str) -> ApiError:
    return ApiError(501, "feature_disabled", f"{what} is not built yet.")


@router.get("/me/export")
async def export_me(user: CurrentUser = User):
    raise _not_built("Account export")


@router.delete("/me")
async def delete_me(user: CurrentUser = User):
    # Needs Firebase user deletion + Razorpay cancel + hard delete job (counsel input).
    raise _not_built("Account deletion")
