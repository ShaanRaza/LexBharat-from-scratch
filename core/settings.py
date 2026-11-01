"""One settings module: every name in .env.example, same defaults.

Rule 2 (CLAUDE.md): model names, keys, limits and thresholds live in config,
never in code. Secrets use SecretStr so they never print.
"""

from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # blank .env lines mean "not set"
    )

    # --- Environment ("production" turns on the safety checks below) ---
    ENVIRONMENT: str = "development"

    # --- Product ---
    PRODUCT_NAME: str = "LexBharat"
    CORPUS_COLLECTION: str = "kanoon_v1"
    SNAPSHOT_VERSION: str = "v2026.08"
    DATA_AS_OF: str = ""
    DATA_CREDIT: str = "Data: Open India Law by Vaquill AI, CC BY 4.0"

    # --- Citation seal (HMAC key; must be stable across processes so cached
    # --- answers still verify; never hard-code, set in AWS Secrets Manager / .env).
    # --- No default: every entry point (API, worker) must call
    # --- core.verify.assert_seal_key_configured() at startup.
    SEAL_KEY: SecretStr = SecretStr("")

    # --- AI gateway (LiteLLM) ---
    MODEL_FREE: str = "gemini/gemini-3.5-flash-lite"
    MODEL_STUDENT: str = "gemini/gemini-3.1-flash-lite"
    MODEL_PRO: str = "gemini/gemini-3.1-flash-lite"
    MODEL_REWRITE: str = "gemini/gemini-3.5-flash-lite"
    MODEL_FALLBACK: str = ""
    GEMINI_API_KEY: SecretStr = SecretStr("")

    # --- Voyage AI ---
    VOYAGE_API_KEY: SecretStr = SecretStr("")
    VOYAGE_EMBED_MODEL: str = "voyage-4"
    VOYAGE_RERANK_MODEL: str = "rerank-2.5-lite"

    # --- Jev (TypeSafe AI) ---
    JEV_API_KEY: SecretStr = SecretStr("")
    JEV_MODEL: str = "jev-latest"  # name from the API docs; not verified live
    JEV_TIMEOUT_MS: int = 800
    JEV_GATE_THRESHOLD: float = 0.6
    JEV_BATCH_GATE: bool = False  # one Jev request per run for all passages; claim
    # support is never batched (a wrong claim check changes a citation tick)
    JEV_CLAIM_THRESHOLD: float = 0.6  # below this, Jev 'supports' becomes 'partly'
    JEV_ENABLED_SCOPE: bool = False
    JEV_ENABLED_FILTERS: bool = False
    # GATE and CLAIM stay off until a live test shows batched and single Jev answers
    # agree (reviewer finding); claim support is already sent unbatched.
    JEV_ENABLED_GATE: bool = False
    JEV_ENABLED_CLAIM: bool = False
    JEV_ENABLED_SAFETY: bool = False

    # --- Qdrant ---
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: SecretStr = SecretStr("")
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
    # Helper calls (the "Improve my question" helper and next-question suggestions) are
    # NOT answers and never touch the plan limit (A52). They are rate-limited per user
    # per hour instead. PLACEHOLDER numbers until the load test (PRD-v2 gate 14); None
    # switches the limit off.
    RATE_LIMIT_IMPROVE_PER_HOUR: int | None = 60
    RATE_LIMIT_FOLLOWUPS_PER_HOUR: int | None = 60
    # Model price per million tokens, in whatever currency the owner reads the spend
    # view in. Unset = tokens only, no money (nothing is invented).
    AI_PRICE_IN_PER_MTOK: float | None = None
    AI_PRICE_OUT_PER_MTOK: float | None = None
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
