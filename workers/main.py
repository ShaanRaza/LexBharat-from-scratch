"""Background worker (ARQ). Skeleton only: no jobs are built yet.

Rules (infra/README.md): one job at a time, capped at 1 CPU, so OCR never slows chat.
OCR and upload indexing jobs are added here when uploads are built (behind
FEATURE_UPLOADS). Run:  arq workers.main.WorkerSettings
"""

from arq.connections import RedisSettings

from core.settings import get_settings


async def ping(ctx: dict) -> str:
    """Smoke-test job so the worker has something to run."""
    return "pong"


class WorkerSettings:
    functions = [ping]
    max_jobs = 1  # one job at a time
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
