"""Shared fixtures: a fresh app wired to fakes for every test (no network, no DB)."""

import pytest
from api_fakes import (
    FakePipeline,
    FakeQueue,
    FakeSigner,
    FakeStore,
    FakeVerifier,
)
from fastapi.testclient import TestClient

from api.deps import settings_dep
from api.main import create_app
from core.settings import Settings


def make_settings(**overrides) -> Settings:
    """Settings built from defaults only: _env_file=None ignores any real .env."""
    base = {
        "PRODUCT_NAME": "TestBuddy",
        "DATA_AS_OF": "2026-08-01",
        "SNAPSHOT_VERSION": "v2026.08",
        "RAZORPAY_WEBHOOK_SECRET": "whsec_test",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


class Env:
    """Everything a test might poke at, plus helpers to call the API."""

    def __init__(self):
        self.app = create_app()
        self.store = FakeStore()
        self.queue = FakeQueue()
        self.pipeline = FakePipeline()
        self.app.state.store = self.store
        self.app.state.queue = self.queue
        self.app.state.pipeline = self.pipeline
        self.app.state.token_verifier = FakeVerifier()
        self.app.state.upload_signer = FakeSigner()
        self.set_settings()
        # 500s come back as responses (with our error body) instead of raising in the test.
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def set_settings(self, **overrides) -> Settings:
        s = make_settings(**overrides)
        self.app.dependency_overrides[settings_dep] = lambda: s
        return s

    @staticmethod
    def auth(who: str = "alice") -> dict[str, str]:
        return {"Authorization": f"Bearer token-{who}"}


@pytest.fixture
def env() -> Env:
    return Env()


@pytest.fixture
def client(env) -> TestClient:
    return env.client
