"""The FastAPI app. Routes only: business logic lives in core/ (CLAUDE.md section 3).

Run it:  uvicorn api.main:app --host 0.0.0.0 --port 8000
OpenAPI file (the website's client is generated from this, rule 3): /api/v1/openapi.json
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from api.deps import (
    ArqQueue,
    UnavailablePipeline,
    build_token_verifier,
    build_upload_signer,
)
from api.errors import RequestIdLogFilter, RequestIdMiddleware, install_error_handlers
from api.routes import conversations, me, misc, records
from api.schemas import ErrorResponse
from api.store import SqlStore
from core.settings import get_settings

API_PREFIX = "/api/v1"


def configure_logging() -> None:
    """Every log line carries the request ID (docs/API.md)."""
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdLogFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        )
    )
    root = logging.getLogger()
    if not any(
        isinstance(h.formatter, logging.Formatter) and h.filters for h in root.handlers
    ):
        root.handlers = [handler]
    root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start-up: open the database pool once. Shut-down: close it."""
    settings = get_settings()
    engine = None
    # Tests put a fake store on app.state before start-up; do not overwrite it.
    if getattr(app.state, "store", None) is None:
        engine = create_async_engine(
            settings.DATABASE_URL.get_secret_value(), pool_pre_ping=True
        )
        app.state.store = SqlStore(engine)
    yield
    if engine is not None:
        await engine.dispose()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.PRODUCT_NAME} API",
        version="1",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        # Every route can return the one standard error body.
        responses={
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    # Outside services, each behind a small interface (api/deps.py). Tests replace these.
    app.state.token_verifier = build_token_verifier()
    app.state.pipeline = UnavailablePipeline()
    app.state.queue = ArqQueue(settings.REDIS_URL)
    app.state.upload_signer = build_upload_signer()

    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    for module in (me, records, conversations, misc):
        app.include_router(module.router, prefix=API_PREFIX)
    return app


app = create_app()
