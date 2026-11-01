"""API-only settings (everything else is in core/settings.py).

Plain words: where the website lives (CORS), which environment this is, and the
fake-pipeline switch. APP_ENV defaults to "production" on purpose: a forgotten
variable must make the app stricter, never looser.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_ENV: str = "production"  # production | staging | development | test
    WEB_ORIGIN: str = "http://localhost:3000"  # comma-separated list allowed
    # FAKE MODE: canned answers, no vendor calls. Refused outside development/test.
    FAKE_PIPELINE: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.WEB_ORIGIN.split(",") if o.strip()]

    @model_validator(mode="after")
    def _fake_never_in_production(self) -> "ApiSettings":
        if self.FAKE_PIPELINE and self.APP_ENV not in ("development", "test"):
            raise ValueError(
                "FAKE_PIPELINE=true is only allowed when APP_ENV is development "
                "or test. Refusing to start."
            )
        return self


@lru_cache
def get_api_settings() -> ApiSettings:
    return ApiSettings()
