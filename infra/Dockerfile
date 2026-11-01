# syntax=docker/dockerfile:1
#
# One Dockerfile, three images (pick with `target:` in docker-compose.yml):
#   api     - the FastAPI app            (also runs migrations: alembic is installed)
#   worker  - the ARQ background worker  (adds Tesseract for OCR)
#   test    - the same code plus pytest/ruff, so tests run in Docker too (rule 5)
#
# ARM: the server is ARM (Graviton r7g), so every image must build for linux/arm64.
# python:3.12-slim-bookworm is an official multi-arch image that includes arm64
# (from Docker's published docs; the CI workflow docker.yml really builds it for arm64).
# Every Python dependency in pyproject.toml ships a linux/aarch64 wheel or builds from
# source on slim; if one ever does not, the arm64 build step in CI fails loudly.

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install only the dependency list from pyproject.toml first. Docker caches this layer,
# so changing a source file does not reinstall every package.
COPY pyproject.toml ./
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml','rb'))['project']; print('\n'.join(d['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

# Source code. tests/, web/, evals/, docs/ are not needed at run time.
COPY api ./api
COPY core ./core
COPY adapters ./adapters
COPY workers ./workers
COPY migrations ./migrations

# Never run as root inside the container.
RUN useradd --system --uid 10001 --no-create-home app
USER app


# ---- api ---------------------------------------------------------------------
FROM base AS api
EXPOSE 8000
# --proxy-headers: trust X-Forwarded-For from the HTTPS proxy in front, so the audit log
# records the real client IP.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]


# ---- worker ------------------------------------------------------------------
FROM base AS worker
USER root
# OCR for scanned uploads: Tesseract with English + Hindi. These Debian packages exist for
# arm64 (Debian publishes every architecture). PyMuPDF is not installed yet: it is not in
# pyproject.toml (lead agent's file) and uploads are off at launch.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*
USER app
CMD ["arq", "workers.main.WorkerSettings"]


# ---- test --------------------------------------------------------------------
FROM base AS test
USER root
# /app is read-only for the app user; pytest's cache folder would fail to write there.
ENV PYTEST_ADDOPTS="-p no:cacheprovider"
COPY pyproject.toml ./
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml','rb'))['project']; print('\n'.join(d['optional-dependencies']['dev']))" > /tmp/dev-requirements.txt \
    && pip install -r /tmp/dev-requirements.txt
COPY tests ./tests
COPY evals ./evals
COPY data ./data
USER app
CMD ["pytest", "-q", "tests/api", "tests/migrations"]
