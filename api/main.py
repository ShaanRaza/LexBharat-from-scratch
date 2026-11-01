"""FastAPI app factory. Routes only; business logic is in core/.

`create_app()` takes optional overrides so tests can inject fakes (repo, login
verifier, pipeline). In production they are built from config.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import DenyAllAuth
from api.config import ApiSettings, get_api_settings
from api.errors import RequestIdMiddleware, install_error_handlers
from api.routes import content, conversations, me, misc

PREFIX = "/api/v1"


def create_app(
    api_settings: ApiSettings | None = None,
    core_settings=None,
    repo=None,
    verifier=None,
    pipeline=None,
) -> FastAPI:
    api_settings = api_settings or get_api_settings()
    if core_settings is None:
        from core.settings import get_settings

        core_settings = get_settings()

    app = FastAPI(title="Research API", version="1")
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

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    install_error_handlers(app)
    for r in (me.router, conversations.router, content.router, misc.router):
        app.include_router(r, prefix=PREFIX)
    return app
