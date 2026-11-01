"""Shared test helpers: a tiny fake corpus and a fully-faked pipeline.

Nothing here touches the network. `make_deps(...)` wires Fakes for Voyage, the model,
Qdrant, Jev, the cache and the database, so a whole question can run in memory.
"""

from __future__ import annotations

import json
import re

import pytest

from adapters.cache import FakeCache
from adapters.gemini import FakeLLM
from adapters.jev import DecisionAdapter, FakeDecisionBackend
from adapters.qdrant import FakeVectorStore, Record
from adapters.voyage import FakeVoyage
from core.pipeline import PipelineDeps
from core.save import InMemoryMessageRepository
from core.settings import Settings

ARNESH_TEXT = (
    "The power to arrest must be exercised with care and caution. "
    "Arrest brings humiliation, curtails freedom and casts scars forever. "
    "The police officer must be able to justify the arrest apart from his reasonable "
    "satisfaction that the person has committed the offence."
)
SECTION_438_TEXT = (
    "When any person has reason to believe that he may be arrested on an accusation of "
    "having committed a non-bailable offence, he may apply to the High Court or the "
    "Court of Session for a direction that in the event of such arrest he shall be "
    "released on bail."
)
SIDDHARAM_TEXT = (
    "Anticipatory bail in economic offences needs the court to weigh the gravity of "
    "the offence and the stage of investigation before granting protection from arrest."
)


def make_corpus() -> FakeVectorStore:
    store = FakeVectorStore()
    store.add_record(
        Record(
            record_id="sc-2014-arnesh",
            source_type="judgment",
            title="Arnesh Kumar v. State of Bihar",
            text=ARNESH_TEXT,
            court="supreme_court",
            year=2014,
            citation="(2014) 8 SCC 273",
            case_number="CRL-A-1277-2014",
            pdf_url="https://example.invalid/arnesh.pdf",
        )
    )
    store.add_record(
        Record(
            record_id="act-crpc-438",
            source_type="act",
            title="Code of Criminal Procedure, 1973 - Section 438",
            text=SECTION_438_TEXT,
            act_name="Code of Criminal Procedure, 1973",
            section_number="438",
            source_url="https://example.invalid/crpc/438",
            act_status="",  # not filled: must show "in-force status not checked"
        )
    )
    store.add_record(
        Record(
            record_id="sc-2019-siddharam",
            source_type="judgment",
            title="Siddharam Satlingappa Mhetre v. State of Maharashtra",
            text=SIDDHARAM_TEXT,
            court="supreme_court",
            year=2011,
            citation="(2011) 1 SCC 694",
            pdf_url="https://example.invalid/siddharam.pdf",
        )
    )
    return store


def source_id_for(prompt: str, needle: str) -> str:
    """Find which S-label the pipeline gave to the passage containing `needle`."""
    match = re.search(r'<passage id="(S\d+)">\n[^<]*' + re.escape(needle), prompt)
    assert match, f"{needle!r} was not among the passages shown to the model"
    return match.group(1)


def llm_responder(answer_text):
    """`answer_text` is a string, or a function(prompt) -> string for dynamic S-labels."""
    """A fake model that answers each pipeline prompt the right way."""

    def respond(system: str, prompt: str, model: str) -> str:
        if "JSON only" in system:  # step 2: rewrite
            message = prompt.split("User message:\n", 1)[1].strip()
            return json.dumps({"query": message})
        if "summarise" in system:  # step 1: rolling summary
            return "Earlier the user asked about bail."
        return answer_text(prompt) if callable(answer_text) else answer_text  # step 8

    return respond


def make_settings(**overrides) -> Settings:
    base = {
        "JEV_ENABLED_SCOPE": True,
        "JEV_ENABLED_SAFETY": True,
        "JEV_ENABLED_GATE": True,
        "JEV_ENABLED_CLAIM": True,
        "DATA_AS_OF": "2026-08-31",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def make_deps(
    answer_text: str,
    *,
    store: FakeVectorStore | None = None,
    jev: FakeDecisionBackend | None = None,
    fallback: FakeDecisionBackend | None = None,
    voyage: FakeVoyage | None = None,
    llm: FakeLLM | None = None,
    **settings_overrides,
) -> PipelineDeps:
    settings = make_settings(**settings_overrides)
    return PipelineDeps(
        settings=settings,
        llm=llm or FakeLLM(responder=llm_responder(answer_text)),
        voyage=voyage or FakeVoyage(),
        store=store or make_corpus(),
        decisions=DecisionAdapter(
            jev or FakeDecisionBackend(), fallback or FakeDecisionBackend(), settings
        ),
        cache=FakeCache(),
        repo=InMemoryMessageRepository(),
    )


@pytest.fixture
def corpus() -> FakeVectorStore:
    return make_corpus()


@pytest.fixture
def settings() -> Settings:
    return make_settings()
