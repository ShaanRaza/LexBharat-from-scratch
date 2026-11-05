"""Firebase login check that FAILS CLOSED.

Plain words: every protected route needs a Firebase token. We never call Firebase
here; we call a `TokenVerifier` (the Firebase adapter implements it). Rules:
- no token / malformed header      -> 401
- adapter says token is invalid    -> 401 (AuthError)
- verifier crashes or is missing   -> 503, access DENIED (never "let them in")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, Request

from adapters.firebase import AuthError, AuthProvider, AuthUser
from api.errors import ApiError

log = logging.getLogger("api.auth")


class DenyAllAuth:
    """Default when no Firebase adapter is wired: nobody gets in."""

    async def verify_token(self, id_token: str) -> AuthUser:
        raise RuntimeError("no token verifier configured")


@dataclass(frozen=True)
class CurrentUser:
    id: str  # users.id (UUID as text)
    firebase_uid: str
    email: str | None
    name: str | None
    role: str | None
    plan: str


async def current_user(request: Request) -> CurrentUser:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "unauthenticated", "Sign in to continue.")
    verifier: AuthProvider = request.app.state.verifier
    try:
        ident = await verifier.verify_token(token.strip())
    except AuthError:
        raise ApiError(401, "unauthenticated", "Sign in to continue.") from None
    except Exception:  # noqa: BLE001  adapter error: deny. Log type only, never the token.
        log.error("token verifier failed; denying request")
        raise ApiError(
            503, "service_unavailable", "Sign-in is unavailable. Try again shortly."
        ) from None
    if not ident or not ident.firebase_uid:
        raise ApiError(401, "unauthenticated", "Sign in to continue.")
    user = await request.app.state.repo.upsert_user(
        ident.firebase_uid, ident.email, None
    )
    return CurrentUser(**user)


User = Depends(current_user)
