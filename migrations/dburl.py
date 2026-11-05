"""Which database URL alembic migrates. Kept out of env.py so it can be tested without
running a migration (env.py runs on import)."""

import os

from sqlalchemy.engine import make_url

from core.settings import get_settings


def migration_url() -> str:
    """Migrations run as the table OWNER. Order: MIGRATION_DATABASE_URL in the process
    environment, then DATABASE_URL in the process environment (how tests and one-off
    tools point alembic at a scratch database, so a developer's .env can never redirect
    them), then MIGRATION_DATABASE_URL from .env. Never the application's own URL: the
    non-owning role cannot alter anything, so we say that plainly instead of failing
    with 'permission denied'."""
    s = get_settings()
    url = (
        os.environ.get("MIGRATION_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or s.MIGRATION_DATABASE_URL.get_secret_value()
        or s.DATABASE_URL.get_secret_value()
    )
    if make_url(url).username == s.APP_DB_ROLE:
        raise RuntimeError(
            "Migrations must run as the table owner, but the URL points at the "
            "application role. Set MIGRATION_DATABASE_URL to the owner (see "
            "docs/ENVIRONMENT.md, 'Database roles')."
        )
    return url
