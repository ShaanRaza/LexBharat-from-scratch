"""Hermetic set-up for the security tests: fake outside services, a fixed seal key."""

import sys
from pathlib import Path

import pytest

from core.settings import get_settings

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # security_helpers


@pytest.fixture(autouse=True)
def seal_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # never read the developer's real .env
    monkeypatch.setenv("SEAL_KEY", "test-only-seal-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
