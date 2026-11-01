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


def test_blank_values_in_an_env_file_mean_unset(tmp_path, monkeypatch):
    for name in ("PLAN_LIMIT_FREE", "UPLOAD_MAX_MB", "UPLOAD_MAX_PAGES", "SEAL_KEY"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / "test.env"
    env.write_text(
        "PLAN_LIMIT_FREE=\nPLAN_LIMIT_PRO=\nUPLOAD_MAX_MB=\nUPLOAD_MAX_PAGES=\n"
        "FEATURE_UPLOADS=\nSEAL_KEY=\n"
    )
    s = Settings(_env_file=env)
    assert s.PLAN_LIMIT_FREE is None and s.UPLOAD_MAX_MB is None
    assert s.UPLOAD_MAX_PAGES is None and s.FEATURE_UPLOADS is False


def test_blank_seal_key_still_rejected_in_production(tmp_path, monkeypatch):
    import pytest

    monkeypatch.delenv("SEAL_KEY", raising=False)
    env = tmp_path / "prod.env"
    env.write_text("ENVIRONMENT=production\nSEAL_KEY=\n")
    with pytest.raises(ValueError):
        Settings(_env_file=env)
