"""Settings guarantees core relies on."""

from typing import get_args

from core.contracts import CitationStatus
from core.settings import Settings


def test_only_one_corpus_collection_setting():
    names = [n for n in Settings.model_fields if "COLLECTION" in n]
    assert sorted(names) == ["CORPUS_COLLECTION", "QDRANT_UPLOADS_COLLECTION"]


def test_citation_statuses():
    assert set(get_args(CitationStatus)) == {"verified", "partly", "unchecked"}


def test_seal_key_has_no_default():
    assert Settings.model_fields["SEAL_KEY"].default.get_secret_value() == ""
