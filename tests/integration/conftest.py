import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    """Bring TEST_DATABASE_URL to head before any integration test, so these tests do
    not depend on test order or on what other tests left behind."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        yield
        return
    env = {**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(ROOT)}
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "-c", "migrations/alembic.ini",
         "upgrade", "head"],
        cwd=ROOT, env=env, check=True, capture_output=True,
    )  # fmt: skip
    yield
