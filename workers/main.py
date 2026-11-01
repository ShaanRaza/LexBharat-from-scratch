"""Background worker (ARQ). Skeleton only: no jobs are built yet.

Rules (infra/README.md): one job at a time, capped at 1 CPU, so OCR never slows chat.
OCR and upload indexing jobs are added here when uploads are built (behind
FEATURE_UPLOADS). Run:  arq workers.main.WorkerSettings
"""

from arq.connections import RedisSettings

from core.settings import get_settings
from core.verify import assert_seal_key_configured


async def on_startup(ctx: dict) -> None:
    """Refuse to start without SEAL_KEY (same rule as the API)."""
    assert_seal_key_configured()


async def ping(ctx: dict) -> str:
    """Smoke-test job so the worker has something to run."""
    return "pong"


class WorkerSettings:
    functions = [ping]
    on_startup = on_startup
    max_jobs = 1  # one job at a time
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
