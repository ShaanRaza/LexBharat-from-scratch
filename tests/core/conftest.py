"""Fixtures for tests/core. Helper functions live in core_helpers.py (a unique module
name, so it cannot clash with another lane's conftest when all tests run together)."""

import pytest
from core_helpers import make_corpus, make_settings

from adapters.qdrant import FakeVectorStore
from core.settings import Settings


@pytest.fixture
def corpus() -> FakeVectorStore:
    return make_corpus()


@pytest.fixture
def settings() -> Settings:
    return make_settings()
