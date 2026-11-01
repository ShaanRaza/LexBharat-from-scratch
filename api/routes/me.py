"""Account routes: profile, consents (DPDP), export, delete."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api import notices
from api.deps import (
    CurrentUser,
    JobQueue,
    client_ip,
    current_user,
    month_start,
    plan_limit,
    queue_dep,
    settings_dep,
    store_dep,
)
from api.errors import ApiError, request_id_var
from api.schemas import (
    ConsentChange,
    ConsentList,
    DeleteAccountOut,
    MeOut,
)
from api.store import OwnsOrganisation, Store
from core.settings import Settings

router = APIRouter(tags=["account"])


def limit_headers(limit: int | None, used: int) -> dict[str, str]:
    """Remaining answers come back as response headers (docs/API.md). Blank = no cap set."""
    if limit is None:
        return {}
    return {
        "X-Answers-Limit": str(limit),
        "X-Answers-Remaining": str(max(limit - used, 0)),
    }


@router.get(
    "/me", response_model=MeOut, summary="Profile, plan, answers left this month"
)
async def get_me(
    *,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    used = await store.answers_used(user.id, month_start())
    limit = plan_limit(settings, user.plan)
    body = MeOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        plan=user.plan,
        status=user.status,
        answers_limit=limit,
        answers_used=used,
        answers_left=None if limit is None else max(limit - used, 0),
    )
    return JSONResponse(
        body.model_dump(mode="json"), headers=limit_headers(limit, used)
    )


@router.get("/me/consents", response_model=ConsentList, summary="See your consents")
async def list_consents(
    *,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
):
    return {"items": await store.list_consents(user.id)}


@router.post(
    "/me/consents",
    response_model=ConsentList,
    summary="Give or withdraw a consent",
)
async def change_consent(
    *,
    body: ConsentChange,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
):
    if body.action == "give":
        await store.give_consent(user.id, body.notice_version, body.purpose)
        return {"items": await store.list_consents(user.id)}
    changed = await store.withdraw_consent(user.id, body.purpose)
    if changed == 0:
        raise ApiError(404, "not_found", "There is no active consent for that purpose.")
    return {"items": await store.list_consents(user.id)}


@router.get("/me/export", summary="Download a copy of your data (DPDP)")
async def export_me(
    *,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
):
    data = await store.export_user(user.id)
    await store.add_audit(
        user.id, "export", str(user.id), client_ip(request), request_id_var.get()
    )
    return {"export": data, "provenance": notices.provenance(settings, None)}


@router.delete("/me", response_model=DeleteAccountOut, summary="Delete my account")
async def delete_me(
    *,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
    store: Annotated[Store, Depends(store_dep)],
    queue: Annotated[JobQueue, Depends(queue_dep)],
):
    """Hard delete (CLAUDE.md section 6).

    1. Rows in PostgreSQL go now (chats, messages, uploads' extracted text, consents).
    2. A background job removes what lives elsewhere: S3 files, Qdrant vectors, the
       Firebase user, the Razorpay subscription. We send it IDs and paths only.
    3. Payment records stay (the law requires it; period "Needs counsel").
    """
    if await store.owns_organisation(user.id):
        raise ApiError(
            409,
            "owns_organisation",
            "Transfer or close your organisation before deleting your account.",
        )
    info = await store.account_cleanup_info(user.id)
    await queue.enqueue("delete_account", user_id=str(user.id), **info)
    try:
        await store.delete_user(user.id)
    except OwnsOrganisation:
        raise ApiError(
            409,
            "owns_organisation",
            "Transfer or close your organisation before deleting your account.",
        ) from None
    await store.add_audit(
        None, "delete", str(user.id), client_ip(request), request_id_var.get()
    )
    return DeleteAccountOut()
