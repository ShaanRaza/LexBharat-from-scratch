"""One settings module: every name in .env.example, same defaults.

Rule 2 (CLAUDE.md): model names, keys, limits and thresholds live in config,
never in code. Secrets use SecretStr so they never print.
"""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class UnknownEmbeddingModel(ValueError):
    """A collection was searched whose embedding model has not been measured."""


def _default_court_models() -> dict[str, dict[str, str]]:
    """collection -> court code -> model, from core/court_models.json (built by
    data/build_court_models.py from a measured sample; A128)."""
    raw = json.loads(Path(__file__).with_name("court_models.json").read_text())
    return {
        name: {code: c["model"] for code, c in col["courts"].items()}
        for name, col in raw["collections"].items()
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # blank .env lines mean "not set"
    )

    # --- Environment ---
    # The ONLY thing "production" does here is the SEAL_KEY check at the bottom of this
    # file. It does not turn on any Jev switch, and nothing else flips them (A104).
    ENVIRONMENT: str = "development"

    # --- Product ---
    PRODUCT_NAME: str = "LexBharat"
    CORPUS_COLLECTION: str = "kanoon_v1"
    SNAPSHOT_VERSION: str = "v2026.08"
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
    # A query embedding must use the model that built the stored vectors of the
    # collection being searched, or ranking is silently damaged (the same text embedded
    # by two models agrees only to about 0.91-0.96 cosine). Keys are collection names; a
    # collection that is not listed is REFUSED, never given a default. Measured 2 Nov
    # 2026 by re-embedding stored text: kanoon_v1 is voyage-4-large in 30 of 30 sampled
    # points. The original corpora are NOT single-model (voyage-4, voyage-4-large and
    # voyage-4-lite all occur inside legal_corpus_v1, legal_corpus_v2 and acts_india,
    # by document), so they are deliberately absent. `kerala_v2_fix` is the staging
    # collection that holds ONLY the re-embedded Kerala chunks whose stored vector was
    # dead (data/dead_vectors/reembed_kerala.py); every vector in it is voyage-4, the
    # model of 368 of 450 sampled Kerala chunks. Override with a JSON object in
    # VOYAGE_EMBED_MODELS.
    VOYAGE_EMBED_MODELS: dict[str, str] = {
        "kanoon_v1": "voyage-4-large",
        "kerala_v2_fix": "voyage-4",
    }
    # A collection that mixes courts embedded by DIFFERENT models is described per court
    # instead: collection -> court code (the record-id prefix, core/court_id.py) ->
    # model, the MAJORITY model of a measured sample. A query is embedded once per model
    # and each vector is searched only among its courts. A court that is not listed is
    # REFUSED, never given a default. A collection named in VOYAGE_EMBED_MODELS above
    # uses that one model and ignores this table (so the served kanoon_v1 and any
    # explicit override are unchanged). Override with a JSON object in
    # VOYAGE_COURT_MODELS.
    VOYAGE_COURT_MODELS: dict[str, dict[str, str]] = Field(
        default_factory=_default_court_models
    )
    VOYAGE_RERANK_MODEL: str = "rerank-2.5-lite"

    # --- Jev (TypeSafe AI) ---
    JEV_API_KEY: SecretStr = SecretStr("")
    JEV_MODEL: str = "jev-latest"  # name from the API docs; not verified live
    JEV_TIMEOUT_MS: int = 800
    JEV_GATE_THRESHOLD: float = 0.6
    JEV_BATCH_GATE: bool = False  # one Jev request per run for all passages; claim
    # support is never batched (a wrong claim check changes a citation tick)
    JEV_CLAIM_THRESHOLD: float = 0.6  # below this, Jev 'supports' becomes 'partly'
    # What the four Jev switches do (A104): each picks WHO answers one fixed-choice
    # decision. On = Jev. Off = the Gemini fallback answers the same choices
    # (adapters/decisions.py, FallbackDecisions). Off is therefore NOT "no check": the
    # scope check, the gate and the claim check still run, decided by Gemini. All four
    # default to False and no code or environment flips them; each is set in .env.
    #
    # SCOPE and SAFETY are one pair: Jev answers both in a single request, so the
    # decision goes to Jev only when BOTH are True (adapters/decisions.py:178). Setting
    # one alone changes nothing. They are off because the Jev client has never run
    # against the real service (no key; adapters/jev.py says so) and JEV_MODEL is not
    # verified. They come on by setting both to true in .env, with JEV_API_KEY set.
    JEV_ENABLED_SCOPE: bool = False
    # (There is no FILTERS switch: Jev does not extract filters, the rewrite step does.
    # A switch that nothing read was deleted, A107.)
    # GATE and CLAIM stay off until a live test shows batched and single Jev answers
    # agree (reviewer finding); claim support is already sent unbatched.
    JEV_ENABLED_GATE: bool = False
    JEV_ENABLED_CLAIM: bool = False
    JEV_ENABLED_SAFETY: bool = False

    # --- Qdrant ---
    QDRANT_URL: str = "http://qdrant:6333"
    # Seconds the search waits for Qdrant before the vector store counts as down. The
    # online default is short on purpose; the evaluation harness raises it when the
    # local instance is shared with other jobs.
    QDRANT_TIMEOUT_S: float = 5.0
    QDRANT_API_KEY: SecretStr = SecretStr("")
    QDRANT_UPLOADS_COLLECTION: str = "user_documents"

    # --- PostgreSQL / Redis ---
    DATABASE_URL: SecretStr = SecretStr(
        "postgresql+psycopg://app_rw:app_rw@postgres:5432/kanoon"
    )
    # The application connects as DATABASE_URL, the NON-OWNING role APP_DB_ROLE (data
    # access only), in development exactly as in production (A63, A64). Migrations
    # connect as MIGRATION_DATABASE_URL, the table owner; it must be set, in .env or the
    # process environment, wherever `alembic` runs.
    MIGRATION_DATABASE_URL: SecretStr = SecretStr("")
    APP_DB_ROLE: str = "app_rw"
    APP_DB_PASSWORD: SecretStr = SecretStr("")  # read only by set_app_password
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
    # switches the limit off. How long a share link lives (PRD-v2 O14, TECH-STACK-v2:
    # default 30 days, owner sets the final number with the retention periods, O13).
    SHARE_LINK_EXPIRY_DAYS: int = 30
    # Whether an Act may ever read "In force" (decision A181). OFF until the
    # act_status count settles whether in_force is a measurement or a
    # default (CLAUDE.md section 6). Repealed is always shown; this never hides it.
    # Owner-only.
    SHOW_IN_FORCE: bool = False
    # The one status line appended to an Act's passage text, AFTER the dataset's own
    # status header is stripped (core/search.py, A105/A110). Which line is picked by
    # core/act_status.py from the payload, never by the model: repealed is always
    # stated (the safe direction); in force is stated ONLY while SHOW_IN_FORCE is on;
    # anything else gets the not-checked line. NEEDS-OWNER: the repealed and in-force
    # wordings are statements about the law and stay EMPTY (no line is added) until the
    # owner decides them. The not-checked line is the one the website already uses
    # (web/src/lib/copy.ts IN_FORCE_NOT_CHECKED); a test keeps the two equal.
    ACT_STATUS_REPEALED: str = ""
    ACT_STATUS_IN_FORCE: str = ""
    ACT_STATUS_NOT_CHECKED: str = "In-force status not checked for this Act."
    # The label shown next to a case reference (core/hc_citation.py, A124): a statement
    # about what the identifier IS, so NEEDS-OWNER (CLAUDE.md section 8). This is the
    # placeholder suggested in the brief; the owner approves or replaces it on screen.
    CASE_REFERENCE_LABEL: str = (
        "Case reference, built from the record - not a published citation."
    )
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

    def embed_model_for(self, collection: str, court_code: str | None = None) -> str:
        """The model that built `collection`'s vectors (for `court_code`'s chunks, when
        the collection is described per court). Refuses anything not recorded."""
        if collection in self.VOYAGE_EMBED_MODELS:  # one model for the whole collection
            return self.VOYAGE_EMBED_MODELS[collection]
        per_court = self.VOYAGE_COURT_MODELS.get(collection)
        if per_court is not None:
            if court_code is None:
                raise UnknownEmbeddingModel(
                    f"collection {collection!r} is embedded per court: name the "
                    f"court code"
                )
            try:
                return per_court[court_code]
            except KeyError:
                raise UnknownEmbeddingModel(
                    f"court {court_code!r} is not registered for {collection!r}; "
                    "measure it and register it (data/build_court_models.py), do not "
                    "default"
                ) from None
        raise UnknownEmbeddingModel(
            f"no embedding model is recorded for collection {collection!r}; "
            "add it to VOYAGE_EMBED_MODELS only after re-embedding stored "
            "text reproduces the vectors"
        )

    @model_validator(mode="after")
    def _production_needs_seal_key(self) -> "Settings":
        if self.ENVIRONMENT == "production" and not self.SEAL_KEY.get_secret_value():
            raise ValueError("SEAL_KEY must be set when ENVIRONMENT=production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
