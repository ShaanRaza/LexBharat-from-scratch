"""FastAPI app factory. Routes only; business logic is in core/.

`create_app()` takes optional overrides so tests can inject fakes (repo, login
verifier, pipeline). In production they are built from config.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import DenyAllAuth
from api.config import ApiSettings, get_api_settings
from api.errors import RequestIdMiddleware, install_error_handlers
from api.routes import content, conversations, history, matters, me, misc

PREFIX = "/api/v1"


def create_app(
    api_settings: ApiSettings | None = None,
    core_settings=None,
    repo=None,
    verifier=None,
    pipeline=None,
    limiter=None,
    docs=None,
) -> FastAPI:
    api_settings = api_settings or get_api_settings()
    if core_settings is None:
        from core.settings import get_settings

        core_settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        from api.deps import close_pipeline

        await close_pipeline(getattr(app.state, "pipeline", None))

    app = FastAPI(title="Research API", version="1", lifespan=lifespan)
    app.state.core_settings = core_settings
    app.state.api_settings = api_settings
    app.state.verifier = verifier or DenyAllAuth()  # fail closed by default
    app.state.fake_pipeline = False

    if repo is None:
        from api.pg_repo import PgRepo, make_engine

        repo = PgRepo(
            make_engine(core_settings.DATABASE_URL.get_secret_value()), core_settings
        )
    app.state.repo = repo

    if pipeline is not None:
        app.state.pipeline = pipeline
    elif api_settings.FAKE_PIPELINE:
        from api.bridge import FakePipeline, assert_fake_allowed

        assert_fake_allowed(api_settings.APP_ENV)  # second lock; config checks first
        app.state.pipeline = FakePipeline(repo)
        app.state.fake_pipeline = True
    else:
        from api.deps import build_pipeline

        app.state.pipeline = build_pipeline(core_settings, repo)

    if limiter is None:
        if api_settings.APP_ENV in ("development", "test"):
            from adapters.cache import FakeRateLimiter

            limiter = FakeRateLimiter()
        else:
            from adapters.cache import RedisRateLimiter

            limiter = RedisRateLimiter(core_settings)
    app.state.limiter = limiter

    # Document delete machinery (S3, Qdrant uploads, document rows). Fakes only in
    # development/test; in production it is wired when uploads are (FEATURE_UPLOADS).
    if docs is None and api_settings.APP_ENV in ("development", "test"):
        from adapters.qdrant import FakeVectorStore
        from adapters.s3 import FakeFileStore
        from core.doc_delete import DocServices

        docs = DocServices(FakeFileStore(), FakeVectorStore(core_settings), repo)
    app.state.docs = docs

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    install_error_handlers(app)
    for r in (
        history.router,
        me.router,
        conversations.router,
        matters.router,
        content.router,
        misc.router,
    ):
        app.include_router(r, prefix=PREFIX)
    return app
