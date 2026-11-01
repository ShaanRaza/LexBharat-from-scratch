"""Dependencies: the things routes get handed (settings, database, current user, ...).

Why this file exists: routes must stay thin, and outside services must be swappable
(rule 1). Each outside thing is reached through ONE small interface here:

  * TokenVerifier  - checks a Firebase login token. Real code is adapters/firebase.py
                     (Core agent's lane). If that file is missing, we FAIL CLOSED
                     (503), we never let anyone in.
  * ResearchPipeline - the 11-step pipeline in core/ (see api/pipeline.py).
  * JobQueue       - sends background jobs to the ARQ worker through Redis.
  * Store          - the database (api/store.py).

Tests replace any of them with `app.state.<name> = fake` or FastAPI's
`app.dependency_overrides`; no network, no real keys.
"""

import hmac
import inspect
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import Depends, Request
from starlette.concurrency import run_in_threadpool

from api.errors import ApiError
from api.pipeline import FinalAnswer, ResearchPipeline, SearchHit, TextDelta
from api.store import Store
from core.settings import Settings, get_settings

# ---- settings ---------------------------------------------------------------


def settings_dep() -> Settings:
    return get_settings()


# ---- database ---------------------------------------------------------------


def store_dep(request: Request) -> Store:
    store = getattr(request.app.state, "store", None)
    if store is None:
        raise ApiError(503, "database_unavailable", "The database is not configured.")
    return store


# ---- auth -------------------------------------------------------------------


@dataclass
class TokenClaims:
    uid: str
    email: str
    name: str | None = None


class InvalidToken(Exception):
    """The token is missing, expired, forged or from another project."""


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> TokenClaims: ...


class AdapterTokenVerifier:
    """Wraps `adapters.firebase.verify_id_token(token) -> dict` (sync or async).

    The dict must have `uid` and `email` (and may have `name`). It must raise
    ValueError (or any Exception) for a bad token. That is the contract the Core
    agent's Firebase adapter needs to meet.
    """

    def __init__(self, fn):
        self.fn = fn

    async def verify(self, token: str) -> TokenClaims:
        try:
            if inspect.iscoroutinefunction(self.fn):
                data = await self.fn(token)
            else:
                data = await run_in_threadpool(self.fn, token)
            return TokenClaims(
                uid=str(data["uid"]), email=str(data["email"]), name=data.get("name")
            )
        except Exception as exc:  # any failure = not a valid token
            raise InvalidToken from exc


class UnavailableVerifier:
    """Used when no Firebase adapter exists yet. Rejects EVERYONE (fail closed)."""

    async def verify(self, token: str) -> TokenClaims:
        raise ApiError(
            503, "auth_unavailable", "Login is not available on this server yet."
        )


def build_token_verifier() -> TokenVerifier:
    try:
        from adapters import firebase  # Core agent's file; may not exist yet

        fn = getattr(firebase, "verify_id_token", None)
        if fn is not None:
            return AdapterTokenVerifier(fn)
    except ImportError:
        pass
    return UnavailableVerifier()


def verifier_dep(request: Request) -> TokenVerifier:
    return request.app.state.token_verifier


@dataclass
class CurrentUser:
    id: UUID
    firebase_uid: str
    email: str
    name: str | None
    role: str
    plan: str
    status: str


async def current_user(
    *,
    request: Request,
    verifier: Annotated[TokenVerifier, Depends(verifier_dep)],
    store: Annotated[Store, Depends(store_dep)],
) -> CurrentUser:
    """Every private route needs this. Header: `Authorization: Bearer <Firebase token>`."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(
            401,
            "unauthenticated",
            "Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = await verifier.verify(token.strip())
    except InvalidToken:
        raise ApiError(
            401,
            "invalid_token",
            "Your sign-in has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    row = await store.upsert_user(claims.uid, claims.email, claims.name)
    if row["status"] != "active":
        raise ApiError(403, "account_suspended", "This account cannot be used.")
    return CurrentUser(
        id=row["id"],
        firebase_uid=row["firebase_uid"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        plan=row["plan"],
        status=row["status"],
    )


# ---- research pipeline --------------------------------------------------------


class UnavailablePipeline:
    """Used until the real pipeline in core/ is plugged in. Says so honestly (503)
    instead of returning a made-up answer."""

    async def answer(self, **_: Any) -> AsyncIterator[TextDelta | FinalAnswer]:
        raise ApiError(
            503, "pipeline_unavailable", "Research is not available on this server yet."
        )
        yield  # pragma: no cover  (makes this an async generator)

    async def search(self, **_: Any) -> list[SearchHit]:
        raise ApiError(
            503, "pipeline_unavailable", "Search is not available on this server yet."
        )


def pipeline_dep(request: Request) -> ResearchPipeline:
    return request.app.state.pipeline


# ---- background jobs ----------------------------------------------------------


class JobQueue(Protocol):
    async def enqueue(self, job: str, **kwargs: Any) -> None: ...


class ArqQueue:
    """Real queue: ARQ over Redis (REDIS_URL from settings). The connection is opened
    on first use so the API starts even if Redis is still booting."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._pool = None

    async def enqueue(self, job: str, **kwargs: Any) -> None:
        from arq import create_pool
        from arq.connections import RedisSettings

        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(self.redis_url))
        await self._pool.enqueue_job(job, **kwargs)


def queue_dep(request: Request) -> JobQueue:
    return request.app.state.queue


# ---- upload links (S3) ---------------------------------------------------------------


class UploadSigner(Protocol):
    async def presign_upload(self, path: str, mime_type: str | None) -> str: ...


class UnavailableSigner:
    async def presign_upload(self, path: str, mime_type: str | None) -> str:
        raise ApiError(
            503,
            "storage_unavailable",
            "File storage is not available on this server yet.",
        )


class AdapterSigner:
    """Wraps `adapters.s3.presign_upload(path, mime_type) -> str` (sync or async)."""

    def __init__(self, fn):
        self.fn = fn

    async def presign_upload(self, path: str, mime_type: str | None) -> str:
        if inspect.iscoroutinefunction(self.fn):
            return await self.fn(path, mime_type)
        return await run_in_threadpool(self.fn, path, mime_type)


def build_upload_signer() -> UploadSigner:
    try:
        from adapters import s3  # Core agent's file; may not exist yet

        fn = getattr(s3, "presign_upload", None)
        if fn is not None:
            return AdapterSigner(fn)
    except ImportError:
        pass
    return UnavailableSigner()


def signer_dep(request: Request) -> UploadSigner:
    return request.app.state.upload_signer


# ---- Razorpay webhook signature ------------------------------------------------


def verify_razorpay_signature(body: bytes, signature: str, secret: str) -> bool:
    """HMAC-SHA256 of the raw body, hex, compared in constant time. This is pure math
    (no call to Razorpay), so it lives here rather than in adapters/razorpay.py."""
    expected = hmac.new(secret.encode(), body, "sha256").hexdigest()
    return hmac.compare_digest(expected, signature)


# ---- helpers shared by routes ------------------------------------------------------


def month_start(today: date | None = None) -> date:
    today = today or datetime.now(UTC).date()
    return today.replace(day=1)


def plan_limit(settings: Settings, plan: str) -> int | None:
    """Monthly research answers for a plan. None = the owner has not set it yet
    (docs/ENVIRONMENT.md: limits are undecided), which we treat as 'no cap'."""
    return getattr(settings, f"PLAN_LIMIT_{plan.upper()}", None)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
