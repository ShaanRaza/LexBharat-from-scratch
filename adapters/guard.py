"""Fakes must never run in production; each Fake* calls refuse_in_production()."""

from core.settings import get_settings


def refuse_in_production() -> None:
    if get_settings().ENVIRONMENT == "production":
        raise RuntimeError("fake adapters are not allowed when ENVIRONMENT=production")
