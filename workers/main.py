"""Background worker (ARQ). Skeleton only: no jobs are built yet.

Rules (infra/README.md): one job at a time, capped at 1 CPU, so OCR never slows chat.
OCR and upload indexing jobs are added here when uploads are built (behind
FEATURE_UPLOADS). Run:  arq workers.main.WorkerSettings
"""

from arq import cron
from arq.connections import RedisSettings

from core.settings import get_settings
from core.verify import assert_seal_key_configured
from workers.leftover_check import leftover_check_job


async def on_startup(ctx: dict) -> None:
    """Refuse to start without SEAL_KEY (same rule as the API)."""
    assert_seal_key_configured()
    # Document delete machinery for the nightly leftover check. Only built when uploads
    # are on (A52). Real S3 / Qdrant / PostgreSQL: not verified against live services.
    settings = get_settings()
    if settings.FEATURE_UPLOADS:
        from adapters.qdrant import QdrantStore
        from adapters.s3 import S3Store
        from api.pg_repo import PgRepo, make_engine
        from core.doc_delete import DocServices

        repo = PgRepo(make_engine(settings.DATABASE_URL.get_secret_value()), settings)
        ctx["doc_services"] = DocServices(
            S3Store(settings), QdrantStore(settings), repo
        )


async def ping(ctx: dict) -> str:
    """Smoke-test job so the worker has something to run."""
    return "pong"


async def on_shutdown(ctx: dict) -> None:
    """Close the Jev client if this worker ever built a pipeline (none yet)."""
    from api.deps import close_pipeline

    await close_pipeline(ctx.get("pipeline"))


class WorkerSettings:
    functions = [ping, leftover_check_job]
    cron_jobs = [cron(leftover_check_job, hour=3, minute=0)]  # nightly
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 1  # one job at a time
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
