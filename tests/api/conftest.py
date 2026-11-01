import pytest
from fastapi.testclient import TestClient

from adapters.firebase import FakeAuth
from api.bridge import FakePipeline
from api.config import ApiSettings
from api.main import create_app
from api.repo import MemoryRepo
from core.settings import Settings


@pytest.fixture
def repo():
    return MemoryRepo()


@pytest.fixture
def make_client(repo):
    def _make(**kw):
        app = create_app(
            api_settings=kw.pop(
                "api_settings",
                ApiSettings(APP_ENV="test", WEB_ORIGIN="https://web.example"),
            ),
            core_settings=Settings(),
            repo=repo,
            verifier=kw.pop("verifier", FakeAuth()),
            pipeline=kw.pop("pipeline", FakePipeline(repo)),
            **kw,
        )
        return TestClient(app)

    return _make


@pytest.fixture
def client(make_client):
    return make_client()


def auth(uid="alice"):
    return {"Authorization": f"Bearer tok:{uid}"}


def parse_sse(text: str) -> list[tuple[str, dict]]:
    import json

    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        out.append((lines["event"], json.loads(lines["data"])))
    return out
