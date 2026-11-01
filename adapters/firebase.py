"""Firebase adapter: checks a login token and says who the user is.

Rule 1: the ONLY file that talks to Firebase. Firebase holds the passwords; we keep only
the Firebase user id (docs/DATA-MODEL.md: there is no password column anywhere).

Only the interface and a Fake live here; no real network calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class InvalidToken(Exception):
    """The login token is missing, expired or forged."""


@dataclass(frozen=True)
class AuthUser:
    firebase_uid: str
    email: str


class AuthVerifier(Protocol):
    async def verify_token(self, id_token: str) -> AuthUser: ...


class FakeAuth:
    """Maps made-up tokens to users. Anything else is rejected."""

    def __init__(self, users: dict[str, AuthUser] | None = None) -> None:
        self.users = users or {}

    async def verify_token(self, id_token: str) -> AuthUser:
        try:
            return self.users[id_token]
        except KeyError:
            raise InvalidToken("unknown token") from None
