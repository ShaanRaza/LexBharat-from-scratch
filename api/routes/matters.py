"""Matters (PRD-v2 O11). One table; "Matter" or "Project" is the `kind` label."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Query, Request

from api import schemas as s
from api.auth import CurrentUser, User
from api.errors import ApiError
from core.doc_delete import DeleteIncomplete, MatterNotFound, delete_matter

router = APIRouter()
log = logging.getLogger("api.matters")


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "Matter not found.")


@router.get("/matters", response_model=s.MatterList)
async def list_matters(
    request: Request,
    status: Literal["active", "archived", "all"] = "active",
    user: CurrentUser = User,
):
    rows = await request.app.state.repo.list_matters(
        user.id, None if status == "all" else status
    )
    return s.MatterList(items=rows)


@router.post("/matters", response_model=s.MatterOut, status_code=201)
async def create_matter(
    body: s.MatterCreate, request: Request, user: CurrentUser = User
):
    return await request.app.state.repo.create_matter(
        user.id, body.title.strip(), body.kind
    )


@router.get("/matters/{matter_id}", response_model=s.MatterDetail)
async def get_matter(matter_id: str, request: Request, user: CurrentUser = User):
    repo = request.app.state.repo
    m = await repo.get_matter(user.id, matter_id)
    if m is None:
        raise _not_found()
    convs, _ = await repo.list_conversations(user.id, None, 100, matter_id=matter_id)
    return s.MatterDetail(**m, conversations=convs)


@router.patch("/matters/{matter_id}", response_model=s.MatterOut)
async def update_matter(
    matter_id: str, body: s.MatterUpdate, request: Request, user: CurrentUser = User
):
    """Rename and/or archive (or restore). Archiving hides it from the default list; it
    deletes nothing (deleting is DELETE, which asks what to do with the work)."""
    if body.title is None and body.status is None:
        raise ApiError(422, "validation_error", "Nothing to change.")
    m = await request.app.state.repo.update_matter(
        user.id, matter_id, body.title.strip() if body.title else None, body.status
    )
    if m is None:
        raise _not_found()
    return m


@router.delete("/matters/{matter_id}", response_model=s.MatterDeleted)
async def remove_matter(
    matter_id: str,
    request: Request,
    mode: Literal["unfile", "everything"] = Query(),  # no default: the user must choose
    user: CurrentUser = User,
):
    """Delete a matter. `mode` is REQUIRED because the user is asked which they mean:
    `unfile` = delete the matter only, its work moves to unfiled; `everything` = delete
    the matter and everything in it, uploads included (genuinely hard-deleted)."""
    app = request.app
    try:
        r = await delete_matter(
            user.id, matter_id, mode, getattr(app.state, "docs", None), app.state.repo
        )
    except MatterNotFound as e:
        raise ApiError(404, "not_found", "Matter not found.") from e
    except DeleteIncomplete as e:
        log.error("matter delete stopped: %s", e)
        raise ApiError(
            503,
            "service_unavailable",
            # NEEDS-OWNER: draft wording (DESIGN-DIRECTION section 6). Note it says
            # "nothing was removed", but files deleted before the failing one stay
            # deleted (core/doc_delete.py): the owner should decide the exact words.
            "The matter was kept. One or more files could not be deleted, so "
            "nothing was removed.",
        ) from e
    return s.MatterDeleted(
        mode=r.mode,
        documents_deleted=r.documents_deleted,
        conversations_deleted=r.conversations_deleted,
    )
