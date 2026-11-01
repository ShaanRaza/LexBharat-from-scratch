"""Test helper: connect AS the application role (A63, A64).

The code under test (PgRepo and everything above it) must run with exactly the
privileges it has in production: the non-owning application role. The test HARNESS
genuinely needs the table owner for four things the application never does: running
migrations, CREATE/DROP DATABASE for scratch databases, TRUNCATE to clean up between
tests, and ALTER ROLE to give the app role a throwaway password. Those use
TEST_DATABASE_URL (the owner); nothing the application does needs it."""

from __future__ import annotations

import uuid
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from core.settings import Settings
from migrations.set_app_password import set_password

ROLE = Settings(_env_file=None).APP_DB_ROLE


@contextmanager
def app_login(owner_url: str):
    """Yield a URL that connects as the application role to the same database as
    `owner_url`; turn the role's login off again afterwards (roles are cluster-wide)."""
    password = (
        "test-only-" + uuid.uuid4().hex
    )  # a throwaway cluster, never a real secret
    set_password(owner_url, ROLE, password)
    try:
        yield (
            make_url(owner_url)
            .set(username=ROLE, password=password)
            .render_as_string(hide_password=False)
        )
    finally:
        owner = create_engine(owner_url)
        with owner.begin() as c:
            c.execute(text(f'ALTER ROLE "{ROLE}" NOLOGIN PASSWORD NULL'))
        owner.dispose()
