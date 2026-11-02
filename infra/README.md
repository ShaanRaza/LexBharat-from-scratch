# infra

Docker Compose and deploy scripts. **Written but never run** (A114): see "Validation status" at the end.

Six services on a private Docker network: `web`, `api`, `worker`, `qdrant`, `postgres`,
`redis`.

Rules that must hold:

- **Only `web` and `api` are reachable from the internet.** Qdrant, PostgreSQL and Redis
  are never exposed. The Qdrant dashboard is reached through a private tunnel only.
- **The server is ARM (Graviton, r7g)** — every image needs an ARM build. Check this before
  step 6, not during it.
- Secrets come from AWS Secrets Manager, never from a file on the box.
- The worker is capped at **1 CPU** and a fixed memory limit, and takes **one job at a
  time**, so OCR never slows chat.
- Daily PostgreSQL backups and Qdrant snapshots to S3.
- After restoring the Qdrant snapshot, **delete the snapshot file** — the 200 GB disk is
  sized assuming you do.
- A written rebuild-from-snapshot plan, target **under 1 hour**. One server has no
  failover; that is accepted at launch.

## Validation status (3 Nov 2026, A114)

- **Not run.** `docker compose up` has never been run: no compose plugin was installed
  (`brew install docker-compose`), and the Docker engine was in use by the data copy.
  Nothing below claims a service started.
- **Checked without Docker:** `tests/integration/test_compose_static.py` (structure, paths,
  ports, commands, the search extra). The base images all list linux/arm64 (registry
  check); the API image's Python dependencies resolve to aarch64 wheels (86 packages, 93
  with the search extra).
- **To start it:** copy `.env.example` to `.env` and fill in `SEAL_KEY` and the vendor keys;
  set `POSTGRES_PASSWORD` and `APP_DB_PASSWORD`; then
  `docker compose -f infra/docker-compose.yml up -d`, then, once,
  `docker compose -f infra/docker-compose.yml run --rm migrate`. The site is on
  http://localhost:3000 and the API on http://localhost:8000 (health:
  http://localhost:8000/api/v1/healthz). Postgres, Redis and Qdrant are not published.
- **ARM build, to run on the server or an ARM laptop:**
  `docker buildx build --platform linux/arm64 -f infra/Dockerfile.api .` (and `.web`).
- fastembed downloads the `Qdrant/bm25` model on the API's first search.
