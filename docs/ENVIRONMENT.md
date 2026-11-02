# Environment and configuration

Rule 2 of the seven: **settings live in config, not code.** Model names, API keys, limits,
prices and thresholds sit in environment variables and one settings file. Changing the AI
model must be a config change, never a code change.

Copy [`../.env.example`](../.env.example) to `.env` and fill it in. **`.env` is gitignored
and must stay that way.** On the server, real values live in **AWS Secrets Manager** —
never in a file on the box.

## Why the product name is config

`PRODUCT_NAME` and `CORPUS_COLLECTION` each sit in **one** config value. The final brand
is undecided (KanoonBuddy is a working name; the PRD recommends Praman, pending a
trademark search), so renaming must be a config change, not a code change. **Never
hard-code either string.**

## Groups

| Group | Variables | Notes |
|---|---|---|
| Product | `PRODUCT_NAME`, `CORPUS_COLLECTION`, `DATA_AS_OF`, `SNAPSHOT_VERSION` | Snapshot is `v2026.08` unless the step-1 evaluation upgrades it |
| AI gateway | `LITELLM_*`, `MODEL_FREE`, `MODEL_STUDENT`, `MODEL_PRO`, `MODEL_REWRITE`, `MODEL_FALLBACK` | The model list **only accepts providers marked no-training** |
| Google / Gemini | `GEMINI_API_KEY` | **Paid tier only** |
| Voyage | `VOYAGE_API_KEY`, `VOYAGE_EMBED_MODELS` (JSON, per collection), `VOYAGE_RERANK_MODEL` | the embedding model must match the vectors of the collection searched; an unlisted collection is refused |
| Jev | `JEV_API_KEY`, `JEV_ENABLED_SCOPE`, `JEV_ENABLED_FILTERS`, `JEV_ENABLED_GATE`, `JEV_ENABLED_CLAIM`, `JEV_ENABLED_SAFETY`, `JEV_TIMEOUT_MS`, `JEV_GATE_THRESHOLD` | **One on/off switch per use**, so one can be turned off without touching the others. Timeout 800 ms; threshold starts at 0.6 |
| Qdrant | `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_UPLOADS_COLLECTION` | Never exposed to the internet |
| PostgreSQL | `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `APP_DB_ROLE`, `APP_DB_PASSWORD` | **Two database roles, see "Database roles" below.** The application, in development and production, connects as `DATABASE_URL` (the non-owning role); migrations run as `MIGRATION_DATABASE_URL` (the table owner) |
| Redis | `REDIS_URL`, `ANSWER_CACHE_TTL_DAYS` | Cache TTL 7 days |
| S3 | `AWS_REGION`, `S3_BUCKET_UPLOADS`, `S3_BUCKET_BACKUPS`, `S3_KMS_KEY_ID` | Mumbai, encrypted |
| Firebase | `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_JSON` | Login only |
| Razorpay | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | **Always verify the webhook signature** |
| Monitoring | `LANGFUSE_*`, `SENTRY_DSN` | Langfuse masked, Sentry scrubbed |
| Sharing | `SHARE_LINK_EXPIRY_DAYS` | How long a share link lives (PRD-v2 O14). **Placeholder 30**; the owner sets the real number with the retention periods (O13) |
| Acts | `SHOW_IN_FORCE` | Whether an Act may ever read "In force". **`false` (default) until the `act_status` count is in** (A181, CLAUDE.md section 6). Repealed is shown either way. Owner-only switch |
| Helper limits | `RATE_LIMIT_IMPROVE_PER_HOUR`, `RATE_LIMIT_FOLLOWUPS_PER_HOUR`, `AI_PRICE_IN_PER_MTOK`, `AI_PRICE_OUT_PER_MTOK` | Per user per hour for the two helpers that call a model but are not answers (A52, A54). **Placeholder 60**; empty switches a limit off. Prices are per million tokens; empty = the spend view shows tokens only |
| Limits | `PLAN_LIMIT_FREE`, `PLAN_LIMIT_STUDENT`, `PLAN_LIMIT_PRO`, `PLAN_LIMIT_CHAMBERS`, `UPLOAD_MAX_MB`, `UPLOAD_MAX_PAGES` | Upload limits **undecided** — set from OCR time on real scans |
| Feature switches | `FEATURE_UPLOADS`, `FEATURE_STATS_LIVE`, `FEATURE_MODEL_ROUTING`, `FEATURE_HINDI` | **All off at launch** except as the gates allow |

## Switches that must start OFF

| Switch | Turns on when |
|---|---|
| `FEATURE_UPLOADS` | The 20 interviews **and** the advocate's written legal opinion support it |
| `FEATURE_STATS_LIVE` | The 50-judgment Supreme Court hand check passes, against a pass rule agreed beforehand |
| `FEATURE_MODEL_ROUTING` | A stronger model has been chosen (week-1 test on 50 real questions) |
| `FEATURE_HINDI` | The Hindi test plan passes at every layer (D3) |
| Each `JEV_ENABLED_*` | That use beats the version without it on the 200-question test set |

## Secrets rules

- Never commit a real key. `.env.example` carries **names only**.
- Never print a secret in a log line, an error message, a Langfuse trace or a Sentry report.
- Rotate anything that reaches a chat window, a screenshot or a commit.


## API and Docker Compose only

These are read by `api/config.py` and `infra/docker-compose.yml`, not by `core/settings.py`, so they are not listed in `.env.example`:

| Name | What it does |
|---|---|
| `APP_ENV` | API environment. Defaults to `production`. The fake pipeline needs `development` or `test` **and** `ENVIRONMENT` not `production` |
| `POSTGRES_PASSWORD` | **Required** by Docker Compose (no default). Set it in your shell or `.env` before `docker compose up` |
| `NEXT_PUBLIC_PRODUCT_NAME` | The product name shown by the website. Baked in at build time. Compose passes it as a build argument, falling back to `PRODUCT_NAME`, then `LexBharat`. The website's own code default is neutral ("Legal research") so no brand word is hard-coded in `web/` |
| `WEB_ORIGIN` | The website's address, for CORS |
| `FAKE_PIPELINE` | Canned answers for demos. Refused in production |


## Database roles (A63)

Two roles, on purpose. The database triggers that make the provenance flags write-once and
keep share links off shaped answers (migration 0010) only mean something if the application
cannot switch them off. A table **owner** (or a superuser) can run
`ALTER TABLE ... DISABLE TRIGGER`; a role that merely has data access cannot.

| Role | Used by | Can | Cannot |
|---|---|---|---|
| **Owner** (compose: `kanoon`, the Postgres bootstrap user; `MIGRATION_DATABASE_URL`) | `alembic upgrade head` and `python -m migrations.set_app_password` only | create, alter and drop tables, triggers and roles | nothing: keep its password out of the API and the worker |
| **Application** (`APP_DB_ROLE`, default `app_rw`; `DATABASE_URL`) | the API and the worker | `SELECT`, `INSERT`, `UPDATE`, `DELETE` on every table and view, now and in tables later migrations create | `ALTER`, `DROP`, `TRUNCATE`, `CREATE`, create or disable triggers, read or change `alembic_version`, create roles, become the owner; it is not a superuser |

How it is set up:

1. Migration `0011` creates the application role **without a login** and grants it data
   access only. No password is ever written into a migration or a file.
2. The deploy sets the password once, from a secret: `APP_DB_PASSWORD=... python -m
   migrations.set_app_password` (the compose `migrate` service does this after
   `alembic upgrade head`). It connects as the owner and refuses an empty password.
3. The API and the worker get `DATABASE_URL` pointing at the application role. In compose
   that is built from `APP_DB_ROLE` and `APP_DB_PASSWORD`; set both (and `POSTGRES_PASSWORD`,
   the owner's) before `docker compose up`.

**Development is the same as production (A64).** The default `DATABASE_URL` (in
`core/settings.py` and `.env.example`) is the application role, so a local run has exactly
the privileges production has and cannot switch the triggers off. `MIGRATION_DATABASE_URL`
(the owner) is set in `.env.example` and used only by `alembic` and
`python -m migrations.set_app_password`. First run on a laptop:
`alembic upgrade head && python -m migrations.set_app_password`.

**What a developer must do to their local `.env`:** set `DATABASE_URL` to the app role
(`postgresql+psycopg://app_rw:<APP_DB_PASSWORD>@<host>:5432/<db>`), add the owner URL you
had in `DATABASE_URL` before as `MIGRATION_DATABASE_URL`, add `APP_DB_ROLE` and
`APP_DB_PASSWORD`, then run the two commands above. `alembic` refuses, with a plain
message, to migrate as the application role, and a process-level `DATABASE_URL` always
beats `.env` for alembic, so a developer's `.env` can never send a test migration to their
own database.

**What the test suite genuinely needs the owner for, and why:** only the harness, never
the code under test. Migrations (alembic), `CREATE`/`DROP DATABASE` for scratch databases,
`TRUNCATE` to clean up between tests, and `ALTER ROLE ... PASSWORD` to give the app role a
throwaway login: all schema-level powers the application correctly lacks, so they use
`TEST_DATABASE_URL` (the owner). Everything under test (`PgRepo` and every flow above it)
connects as the application role through `tests/pg_roles.py`, and tests that exist to prove
the owner/app boundary (`tests/migrations`) connect as each deliberately. No privilege was
granted to the application role to make a test pass.

**Managed PostgreSQL (RDS):** the master user the service creates owns the tables it
creates and is a near-superuser (`rds_superuser`), so the same discipline applies: **the
application must never connect as the master user.** Use it only for migrations and for
`migrations.set_app_password`; connect the API and worker as `APP_DB_ROLE`, and keep the
master password out of the application's environment and secrets. If migrations are run by
a different login than the one that first created the tables, make sure ownership is
consistent, or the owner-only rule above does not hold. Not verified against a real RDS
instance. A PostgreSQL role is cluster-wide: if several databases on one cluster use
the same role name, the downgrade of `0011` only revokes this database's privileges.
