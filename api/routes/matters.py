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
            "We could not finish deleting one of the uploaded files, so nothing "
            "else was removed and the matter was kept. Please try again.",
        ) from e
    return s.MatterDeleted(
        mode=r.mode,
        documents_deleted=r.documents_deleted,
        conversations_deleted=r.conversations_deleted,
    )
