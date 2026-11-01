"""Give the application role a login password. Run once per environment, by the deploy.

    APP_DB_PASSWORD=... python -m migrations.set_app_password

The password comes from the environment (a secret store in production) and is never
written to a file or printed. It connects as the OWNER (MIGRATION_DATABASE_URL, falling
back to DATABASE_URL) because only an owner-level role may alter another role."""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from core.settings import get_settings


def set_password(owner_url: str, role: str, password: str) -> None:
    if not password:
        raise SystemExit(
            "APP_DB_PASSWORD is empty: refusing to create a passwordless login"
        )
    dsn = make_url(owner_url).set(drivername="postgresql").render_as_string(False)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )


def main() -> None:
    s = get_settings()
    owner = (
        os.environ.get("MIGRATION_DATABASE_URL")
        or s.MIGRATION_DATABASE_URL.get_secret_value()
        or os.environ.get("DATABASE_URL")
        or s.DATABASE_URL.get_secret_value()
    )
    set_password(owner, s.APP_DB_ROLE, os.environ.get("APP_DB_PASSWORD", ""))
    print(f"login enabled for role {s.APP_DB_ROLE}")  # never the password


if __name__ == "__main__":
    sys.exit(main())
