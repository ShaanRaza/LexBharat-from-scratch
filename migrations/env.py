"""Alembic environment. The database URL comes from config (core/settings.py),
never from alembic.ini, so a secret is never written into a file."""

import os

from alembic import context
from sqlalchemy import create_engine

from core.settings import get_settings


def _url() -> str:
    # Env var first so migrations need no other setting; fall back to config.
    return (
        os.environ.get("DATABASE_URL") or get_settings().DATABASE_URL.get_secret_value()
    )


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
