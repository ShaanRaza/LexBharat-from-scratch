"""One settings module: every name in .env.example, same defaults.

Rule 2 (CLAUDE.md): model names, keys, limits and thresholds live in config,
never in code. Secrets use SecretStr so they never print.
"""

from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Environment ("production" turns on the safety checks below) ---
    ENVIRONMENT: str = "development"

    # --- Product ---
    PRODUCT_NAME: str = "KanoonBuddy"
    CORPUS_COLLECTION: str = "kanoon_v1"
    SNAPSHOT_VERSION: str = "v2026.08"
    DATA_AS_OF: str = ""
    DATA_CREDIT: str = "Data: Open India Law by Vaquill AI, CC BY 4.0"

    # --- Citation seal (HMAC key; must be stable across processes so cached
    # --- answers still verify; never hard-code, set in AWS Secrets Manager / .env)
    SEAL_KEY: SecretStr = SecretStr("")

    # --- AI gateway (LiteLLM) ---
    MODEL_FREE: str = "gemini/gemini-2.5-flash-lite"
    MODEL_STUDENT: str = "gemini/gemini-3.1-flash-lite"
    MODEL_PRO: str = "gemini/gemini-3.1-flash-lite"
    MODEL_REWRITE: str = "gemini/gemini-2.5-flash-lite"
    MODEL_FALLBACK: str = ""
    GEMINI_API_KEY: SecretStr = SecretStr("")

    # --- Voyage AI ---
    VOYAGE_API_KEY: SecretStr = SecretStr("")
    VOYAGE_EMBED_MODEL: str = "voyage-4"
    VOYAGE_RERANK_MODEL: str = "rerank-2.5-lite"

    # --- Jev (TypeSafe AI) ---
    JEV_API_KEY: SecretStr = SecretStr("")
    JEV_TIMEOUT_MS: int = 800
    JEV_GATE_THRESHOLD: float = 0.6
    JEV_ENABLED_SCOPE: bool = False
    JEV_ENABLED_FILTERS: bool = False
    JEV_ENABLED_GATE: bool = False
    JEV_ENABLED_CLAIM: bool = False
    JEV_ENABLED_SAFETY: bool = False

    # --- Qdrant ---
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: SecretStr = SecretStr("")
    QDRANT_COLLECTION: str = "kanoon_v1"
    QDRANT_UPLOADS_COLLECTION: str = "user_documents"

    # --- PostgreSQL / Redis ---
    DATABASE_URL: SecretStr = SecretStr(
        "postgresql+psycopg://kanoon:kanoon@postgres:5432/kanoon"
    )
    REDIS_URL: str = "redis://redis:6379/0"
    ANSWER_CACHE_TTL_DAYS: int = 7

    # --- AWS / S3 ---
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_UPLOADS: str = ""
    S3_BUCKET_BACKUPS: str = ""
    S3_KMS_KEY_ID: str = ""

    # --- Firebase (login only) ---
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS_JSON: SecretStr = SecretStr("")

    # --- Razorpay ---
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: SecretStr = SecretStr("")
    RAZORPAY_WEBHOOK_SECRET: SecretStr = SecretStr("")

    # --- Monitoring ---
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: SecretStr = SecretStr("")
    LANGFUSE_HOST: str = ""
    SENTRY_DSN: SecretStr = SecretStr("")

    # --- Limits (undecided values are left blank on purpose) ---
    PLAN_LIMIT_FREE: int | None = None
    PLAN_LIMIT_STUDENT: int | None = None
    PLAN_LIMIT_PRO: int | None = None
    PLAN_LIMIT_CHAMBERS: int | None = None
    UPLOAD_MAX_MB: int | None = None
    UPLOAD_MAX_PAGES: int | None = None

    # --- Feature switches (all off at launch) ---
    FEATURE_UPLOADS: bool = False
    FEATURE_STATS_LIVE: bool = False
    FEATURE_MODEL_ROUTING: bool = False
    FEATURE_HINDI: bool = False

    @model_validator(mode="after")
    def _production_needs_seal_key(self) -> "Settings":
        if self.ENVIRONMENT == "production" and not self.SEAL_KEY.get_secret_value():
            raise ValueError("SEAL_KEY must be set when ENVIRONMENT=production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
