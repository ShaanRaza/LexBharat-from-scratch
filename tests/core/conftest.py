"""Shared test setup: fakes for every vendor, practice fixtures as the corpus."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from adapters.qdrant import FakeVectorStore
from core.settings import Settings, get_settings

PRACTICE = Path(__file__).resolve().parents[1] / "fixtures" / "practice"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SEAL_KEY", "test-seal-key-not-a-secret")
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def load_jsonl(name: str) -> list[dict]:
    with gzip.open(PRACTICE / name, "rt") as f:
        return [json.loads(line) for line in f]


@pytest.fixture(scope="session")
def chunks() -> list[dict]:
    return load_jsonl("chunks.jsonl.gz")


@pytest.fixture(scope="session")
def act_sections() -> list[dict]:
    return load_jsonl("act_sections.jsonl.gz")


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def store(settings, chunks, act_sections) -> FakeVectorStore:
    s = FakeVectorStore(settings)
    for c in chunks[:300]:
        s.add_law(
            c["chunk_id"], c["text"], **{k: v for k, v in c.items() if k != "text"}
        )
    for a in act_sections:
        s.add_law(
            a["chunk_id"], a["text"], **{k: v for k, v in a.items() if k != "text"}
        )
    return s
