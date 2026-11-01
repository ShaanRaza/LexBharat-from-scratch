"""Share a saved answer by link (PRD-v2 O14). The rules are in core/share.py."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from api import schemas as s
from api.auth import CurrentUser, User
from api.errors import ApiError, error_response
from core.share import MessageNotFound, ShareRefused, create_share_link, hash_token

router = APIRouter()

# On EVERY response from the public route, errors included: not for search engines, not
# cached anywhere, and the secret address is not leaked in a Referer header.
PUBLIC_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


def _public_error(request: Request, status: int, code: str, message: str):
    r = error_response(request, status, code, message)
    r.headers.update(PUBLIC_HEADERS)
    return r


# NEEDS-OWNER: draft wording from docs/DESIGN-DIRECTION.md section 6, not approved.
# It is about what a user is told regarding their own material: the owner's to settle.
SHARE_REFUSED_OWN_MATERIAL = (
    "This answer used your own uploaded file or saved case notes, "
    "so it cannot be shared by link."
)
REFUSALS = {
    "not_an_answer": "Only an answer can be shared.",
    "shaped_by_upload": SHARE_REFUSED_OWN_MATERIAL,
    "shaped_by_matter_fact": SHARE_REFUSED_OWN_MATERIAL,
    "unknown_provenance": "This answer cannot be shared.",
}


@router.post(
    "/messages/{message_id}/share", response_model=s.ShareCreated, status_code=201
)
async def share_message(message_id: str, request: Request, user: CurrentUser = User):
    """Create a link to ONE of your saved answers. Refused (403) if an upload or a
    matter fact shaped it. The token is returned once and stored only as a hash."""
    app = request.app
    try:
        link = await create_share_link(
            app.state.repo,
            user.id,
            message_id,
            app.state.core_settings.SHARE_LINK_EXPIRY_DAYS,
        )
    except MessageNotFound as e:  # not yours, or not there: both look absent
        raise ApiError(404, "not_found", "Answer not found.") from e
    except ShareRefused as e:
        raise ApiError(403, "forbidden", REFUSALS[e.reason]) from e
    return s.ShareCreated(
        id=link.id,
        token=link.token,
        path=f"/s/{link.token}",
        expires_at=link.expires_at,
    )


@router.get("/share", response_model=s.ShareList)
async def my_share_links(request: Request, user: CurrentUser = User):
    return s.ShareList(items=await request.app.state.repo.list_share_links(user.id))


@router.delete("/share/{link_id}", response_model=s.Ok)
async def revoke_share_link(link_id: str, request: Request, user: CurrentUser = User):
    """Revoke: the public page stops working at once (the row is checked each time)."""
    if not await request.app.state.repo.revoke_share_link(user.id, link_id):
        raise ApiError(404, "not_found", "Link not found.")
    return s.Ok()


@router.get("/s/{token}", response_model=s.SharedAnswer)
async def shared_answer(token: str, request: Request, response: Response):
    """PUBLIC, no login. Read from the database on every request (never cached), so a
    revoked or expired link is gone at once. Not for search engines, not cached, and the
    address is not leaked in a Referer header."""
    response.headers.update(PUBLIC_HEADERS)
    repo = request.app.state.repo
    row = await repo.get_shared_answer(hash_token(token))
    if row is None:  # unknown, revoked, expired, or no longer shareable: all the same
        return _public_error(request, 404, "not_found", "This link is not available.")
    cov = await repo.data_as_of()
    if not cov:
        return _public_error(
            request, 503, "service_unavailable", "Data is not loaded yet."
        )
    cs = request.app.state.core_settings
    return s.SharedAnswer(
        question=row["question"],
        text=row["text"],
        citations=[s.Citation(**c) for c in row["citations"]],
        expires_at=row["expires_at"],
        provenance=s.Provenance(
            data_as_of=cov[0], snapshot_version=cov[1], credit=cs.DATA_CREDIT
        ),
    )
