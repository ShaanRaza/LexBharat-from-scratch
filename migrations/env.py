"""Alembic environment: how migrations find the database and run.

Rule 4 (CLAUDE.md): every schema change goes through a numbered, reversible
migration in migrations/versions/. Nothing else may create or alter tables.

Rule 2: the database URL comes from core.settings (DATABASE_URL), never from
this file. Tests can override it with `config.set_main_option("sqlalchemy.url", ...)`.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# We write migrations by hand (no autogenerate), so there is no model metadata.
target_metadata = None


def _database_url() -> str:
    # An explicit URL (used by tests) wins over the environment.
    explicit = config.get_main_option("sqlalchemy.url")
    if explicit:
        return explicit
    from core.settings import get_settings  # imported late: only needed here

    return get_settings().DATABASE_URL.get_secret_value()


def run_migrations_offline() -> None:
    """Offline mode: print the SQL instead of running it (`alembic upgrade head --sql`)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mode: connect and run inside one transaction (PostgreSQL DDL is transactional)."""
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
