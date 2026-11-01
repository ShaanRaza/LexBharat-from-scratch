"""Shared set-up for the trust tests: fake outside services, a fixed seal key."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters.decisions import FakeDecisions
from adapters.memory import FakeCitationLog
from adapters.qdrant import FakeVectorStore
from core.contracts import DraftAnswer, Passage
from core.settings import Settings, get_settings

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `evals` imports

JUDGMENT_TEXT = (
    "The Court held that personal liberty under Article 21 cannot be curtailed "
    "except by procedure established by law, and that bail is the rule, "
    "jail the exception."
)
OTHER_TEXT = (
    "The appeal is dismissed with costs. "
    "Section 138 requires a notice within thirty days."
)


@pytest.fixture(autouse=True)
def seal_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # hermetic: never read the developer's real .env
    monkeypatch.setenv("SEAL_KEY", "test-only-seal-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_passages() -> list[Passage]:
    return [
        Passage(
            record_id="rec-1",
            text=JUDGMENT_TEXT,
            source_id="S1",
            citation_string="[1959] SUPP. 2 S.C.R. 986",
            title="A versus B",
            pdf_url="https://example.test/1.pdf",
        ),
        Passage(
            record_id="rec-2",
            text=OTHER_TEXT,
            source_id="S2",
            citation_string="(1978) 1 SCC 248",
            title="C versus D",
            pdf_url="https://example.test/2.pdf",
        ),
    ]


class World:
    """Everything verify() needs, with switches for the failure paths."""

    def __init__(self, jev_down: bool = False):
        self.settings = Settings()
        self.vectors = FakeVectorStore(self.settings)
        self.vectors.add_law("rec-1", JUDGMENT_TEXT)
        self.vectors.add_law("rec-2", OTHER_TEXT)
        self.decisions = FakeDecisions(down=jev_down)
        self.citation_log = FakeCitationLog()
        self.passages = make_passages()

    @property
    def deps(self):
        return SimpleNamespace(
            settings=self.settings,
            vectors=self.vectors,
            decisions=self.decisions,
            citation_log=self.citation_log,
        )

    def draft(self, text: str) -> DraftAnswer:
        return DraftAnswer(text=text, model="fake-model", question="q?")


@pytest.fixture
def world():
    return World()


@pytest.fixture
def world_jev_down():
    return World(jev_down=True)
