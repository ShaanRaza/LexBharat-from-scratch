"""Static checks of infra/ that need no Docker engine (decision A114).

`docker compose up` could not be run when this was written (no compose plugin on the
laptop, and the engine was in use by the data copy), so what CAN be checked from the
files is checked here: that every path, service, command and port the compose file
names exists, and that the bugs found by reading it stay fixed. This does NOT prove the
stack starts: run `docker compose -f infra/docker-compose.yml up` for that."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra"
COMPOSE = yaml.safe_load((INFRA / "docker-compose.yml").read_text())
SERVICES = COMPOSE["services"]


def _copy_sources(dockerfile: Path) -> list[str]:
    out = []
    for line in dockerfile.read_text().splitlines():
        parts = line.split()
        if (
            parts
            and parts[0] == "COPY"
            and not any(p.startswith("--from") for p in parts)
        ):
            out += parts[1:-1]
    return out


def test_the_expected_services_exist():
    assert set(SERVICES) == {
        "web",
        "api",
        "migrate",
        "worker",
        "postgres",
        "redis",
        "qdrant",
    }


def test_only_web_and_api_publish_a_port():
    """infra/README.md: Qdrant, PostgreSQL and Redis are never reachable."""
    assert {n for n, s in SERVICES.items() if "ports" in s} == {"web", "api"}
    assert SERVICES["web"]["ports"] == ["3000:3000"]
    assert SERVICES["api"]["ports"] == ["8000:8000"]


def test_every_dependency_exists_and_a_healthy_condition_has_a_healthcheck():
    for name, svc in SERVICES.items():
        deps = svc.get("depends_on") or {}
        for dep in deps:
            assert dep in SERVICES, f"{name} depends on missing {dep}"
            cond = deps[dep].get("condition") if isinstance(deps, dict) else None
            if cond == "service_healthy":
                assert "healthcheck" in SERVICES[dep], f"{dep} has no healthcheck"


@pytest.mark.parametrize("name", ["web", "api", "migrate", "worker"])
def test_build_paths_exist(name):
    b = SERVICES[name]["build"]
    context = (INFRA / b["context"]).resolve()
    assert context == ROOT
    assert (context / b["dockerfile"]).exists()


@pytest.mark.parametrize("dockerfile", ["Dockerfile.api", "Dockerfile.web"])
def test_every_copied_path_exists_and_is_allowed_by_the_ignore_file(dockerfile):
    sources = _copy_sources(INFRA / dockerfile)
    assert sources
    ignore = (INFRA / f"{dockerfile}.dockerignore").read_text().splitlines()
    allowed = {line[1:] for line in ignore if line.startswith("!")}
    assert "*" in [line.strip() for line in ignore]  # an allow-list
    for src in sources:
        assert (ROOT / src).exists(), f"{dockerfile} copies missing {src}"
        top = src.split("/")[0]
        assert top in allowed, f"{dockerfile}.dockerignore hides {top}"


def test_no_env_file_can_reach_a_build_context():
    for f in ("Dockerfile.api.dockerignore", "Dockerfile.web.dockerignore"):
        text = (INFRA / f).read_text()
        assert "\n*\n" in "\n" + text  # allow-list: everything not named is excluded
        assert "!.env" not in text


def test_the_api_image_installs_the_search_extra():
    """fastembed is the keyword half of search. Without the extra every question ends as
    an error inside the container (adapters/qdrant.py raises VectorStoreUnavailable)."""
    run = [
        ln
        for ln in (INFRA / "Dockerfile.api").read_text().splitlines()
        if ln.startswith("RUN pip install")
    ]
    assert run and re.search(r"\.\[[^\]]*search[^\]]*\]", run[0]), run


def test_the_commands_the_services_run_exist():
    import importlib

    assert (ROOT / "migrations" / "set_app_password.py").exists()
    assert (ROOT / "migrations" / "alembic.ini").exists()
    assert "workers.main.WorkerSettings" in " ".join(SERVICES["worker"]["command"])
    assert hasattr(importlib.import_module("workers.main"), "WorkerSettings")
    main = importlib.import_module("api.main")
    assert callable(main.create_app)
    health = SERVICES["api"]["healthcheck"]["test"][-1]
    assert f"{main.PREFIX}/healthz" in health
    assert any(
        getattr(r, "path", "") == "/healthz"
        for r in importlib.import_module("api.routes.misc").router.routes
    )


def test_postgres_and_redis_gate_startup_on_a_healthcheck():
    for dep in ("postgres", "redis"):
        assert SERVICES["api"]["depends_on"][dep]["condition"] == "service_healthy"


def test_secrets_are_required_not_defaulted():
    text = (INFRA / "docker-compose.yml").read_text()
    assert "${POSTGRES_PASSWORD:?" in text and "${APP_DB_PASSWORD:?" in text
