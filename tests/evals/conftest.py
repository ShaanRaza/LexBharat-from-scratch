"""A fixed seal key, so the tests can build sealed answers."""

import pytest

from core.settings import get_settings


@pytest.fixture(autouse=True)
def seal_key(monkeypatch):
    monkeypatch.setenv("SEAL_KEY", "test-only-seal-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
