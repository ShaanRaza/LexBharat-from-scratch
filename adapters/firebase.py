"""Firebase Authentication (login only). The ONLY file that talks to Firebase.

verify_token(id_token) returns the firebase_uid. All app data lives in our PostgreSQL
keyed by that uid; nothing else goes to Firebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from adapters.guard import refuse_in_production
from core.settings import Settings


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class AuthUser:
    firebase_uid: str
    email: str | None = None


class AuthProvider(Protocol):
    async def verify_token(self, id_token: str) -> AuthUser: ...


class FirebaseAuth:
    """Real. firebase_admin imported lazily. Not verified (no credentials)."""

    def __init__(self, settings: Settings):
        self._s = settings

    async def verify_token(self, id_token: str) -> AuthUser:
        try:
            import firebase_admin.auth as fa

            d = fa.verify_id_token(id_token)
        except Exception as e:
            raise AuthError(str(e)) from e
        return AuthUser(d["uid"], d.get("email"))


class FakeAuth:
    """Tokens look like 'tok:<uid>'. Anything else is rejected."""

    def __init__(self) -> None:
        refuse_in_production()

    async def verify_token(self, id_token: str) -> AuthUser:
        if not id_token.startswith("tok:") or len(id_token) <= 4:
            raise AuthError("bad token")
        return AuthUser(id_token[4:], None)
