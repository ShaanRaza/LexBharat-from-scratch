"""A non-owning application role: data access only, no schema powers.

Plain words (A63): the API and the worker used to connect as the same role that created
and OWNS every table (in compose, the Postgres bootstrap superuser). An owner can run
`ALTER TABLE ... DISABLE TRIGGER`, so the write-once provenance trigger and the
share-link guard (migration 0010) could be switched off by the application's own
connection, which made them advisory. This creates a second role,
`settings.APP_DB_ROLE` (default `app_rw`), that the application connects as:

  * it can SELECT, INSERT, UPDATE and DELETE rows (tables and views, now and, through
    default privileges, in tables later migrations create);
  * it cannot ALTER, DROP, TRUNCATE or CREATE anything, cannot create triggers or
    disable them (that needs ownership), cannot read or change `alembic_version`, and
    is not a superuser and cannot create roles or databases;
  * it is created NOLOGIN. A password is never written into a migration: the deploy
    sets it once with `python -m migrations.set_app_password` (reads APP_DB_PASSWORD).

Migrations keep running as the owner (MIGRATION_DATABASE_URL). The role is cluster-wide
in PostgreSQL, so the downgrade only revokes this database's privileges and leaves the
role itself.

Revision ID: 0011
Revises: 0010
"""

import re

from alembic import op

from core.settings import get_settings

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _role() -> str:
    role = get_settings().APP_DB_ROLE
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise ValueError(f"APP_DB_ROLE is not a safe role name: {role!r}")
    return role


def upgrade() -> None:
    r = _role()
    op.execute(
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{r}') THEN
            CREATE ROLE "{r}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
              NOREPLICATION NOINHERIT;
          END IF;
        END $$
        """
    )
    op.execute(f'GRANT USAGE ON SCHEMA public TO "{r}"')
    op.execute(
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{r}"'
    )
    op.execute(f'REVOKE ALL ON alembic_version FROM "{r}"')
    # Tables a later migration creates (as the owner) are usable by the app at once.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{r}"'
    )


def downgrade() -> None:
    r = _role()
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM "{r}"'
    )
    op.execute(f'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM "{r}"')
    op.execute(f'REVOKE ALL ON SCHEMA public FROM "{r}"')
