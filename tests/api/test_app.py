import pytest

from api.config import ApiSettings
from api.main import create_app
from core.settings import Settings
from tests.api.conftest import auth


def test_cors_allows_web_origin_only(client):
    ok = client.options(
        "/api/v1/me",
        headers={
            "Origin": "https://web.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert ok.headers["access-control-allow-origin"] == "https://web.example"
    bad = client.options(
        "/api/v1/me",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in bad.headers


@pytest.mark.parametrize("env", ["production", "staging", ""])
def test_fake_pipeline_refused_outside_dev(env):
    with pytest.raises(ValueError):
        ApiSettings(APP_ENV=env, FAKE_PIPELINE=True)


def test_fake_pipeline_refused_when_core_environment_is_production():
    with pytest.raises(ValueError):
        ApiSettings(APP_ENV="development", ENVIRONMENT="production", FAKE_PIPELINE=True)


def test_fake_pipeline_refused_by_default_env():
    # APP_ENV defaults to production, so forgetting it can never enable fake mode.
    with pytest.raises(ValueError):
        ApiSettings(FAKE_PIPELINE=True)


def test_second_lock_in_app_factory(repo):
    s = ApiSettings.model_construct(
        APP_ENV="production", FAKE_PIPELINE=True, WEB_ORIGIN=""
    )
    with pytest.raises(RuntimeError):
        create_app(api_settings=s, repo=repo)


def test_fake_mode_reports_itself(repo):
    from fastapi.testclient import TestClient

    app = create_app(
        api_settings=ApiSettings(APP_ENV="development", FAKE_PIPELINE=True),
        repo=repo,
    )
    assert TestClient(app).get("/api/v1/healthz").json()["fake_pipeline"] is True


def test_me_and_user_isolation(client):
    me = client.get("/api/v1/me", headers=auth("alice")).json()
    assert me["plan"] == "free"
    conv = client.post("/api/v1/conversations", json={}, headers=auth("alice")).json()
    # Bob cannot see or write into Alice's conversation.
    assert (
        client.get(
            f"/api/v1/conversations/{conv['id']}", headers=auth("bob")
        ).status_code
        == 404
    )
    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "hi"}, headers=auth("bob"),
    )  # fmt: skip
    assert r.status_code == 404
    assert (
        client.get("/api/v1/conversations", headers=auth("bob")).json()["items"] == []
    )


def test_pagination_cursor(client):
    for _ in range(3):
        client.post("/api/v1/conversations", json={}, headers=auth())
    p1 = client.get("/api/v1/conversations?limit=2", headers=auth()).json()
    assert len(p1["items"]) == 2 and p1["next_cursor"]
    p2 = client.get(
        f"/api/v1/conversations?limit=2&cursor={p1['next_cursor']}", headers=auth()
    ).json()
    assert len(p2["items"]) == 1 and p2["next_cursor"] is None


def test_uploads_off_by_default(client):
    r = client.post(
        "/api/v1/conversations", json={"module": "document"}, headers=auth()
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "feature_disabled"


def test_validation_error_uses_standard_format(client):
    r = client.post("/api/v1/conversations/x/messages", json={}, headers=auth())
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def _section(repo, **over):
    base = {
        "record_id": "IND_central_1_s001", "act_name": "Test Act, 2000",
        "act_year": 2000, "section": "1", "section_title": "t", "text": "body",
        "source_url": "https://x.invalid/a", "act_slug": "test-act-2000",
        "in_force": True, "act_status": None,
    }  # fmt: skip
    repo.sections[:] = [{**base, **over}]
    return None


def test_section_is_never_in_force_while_the_switch_is_off(client, repo):
    """A181: act_status says in force, nothing says repealed, switch off (default)."""
    _section(repo, act_status="in force")
    r = client.get("/api/v1/acts/test-act-2000/sections/1").json()
    assert r["force_status"] == "not_checked"
    assert r["act_status_checked"] is False and r["in_force"] is None
    assert r["provenance"]["credit"].startswith("Data: Open India Law")
    _section(repo, act_status=None)  # and the in_force column alone never counts
    r = client.get("/api/v1/acts/test-act-2000/sections/1").json()
    assert r["force_status"] == "not_checked"


def test_section_in_force_only_where_act_status_says_so_and_the_owner_switched_it_on(
    make_client, repo
):
    on = make_client(core_settings=Settings(SHOW_IN_FORCE=True))
    _section(repo)  # act_status empty: not trusted even with the switch on
    r = on.get("/api/v1/acts/test-act-2000/sections/1").json()
    assert r["force_status"] == "not_checked" and r["in_force"] is None
    _section(repo, act_status="in force")
    r = on.get("/api/v1/acts/test-act-2000/sections/1").json()
    assert r["force_status"] == "in_force" and r["in_force"] is True


def test_section_repealed_from_any_one_of_four_signals(client, repo):
    for over in (
        {"act_status": "repealed"},
        {"record_id": "IND_REP_659_1860_s002", "act_status": None},
        {"is_repealed": True, "act_status": None},
        {"act_name": "Test Act, 1860 (Rep., Act 45 of 2023)", "act_status": None},
        {
            "record_id": "IND_REP_659_1860_s002",
            "act_status": "in_force",
        },  # disagree: repealed
    ):
        _section(repo, **over)
        r = client.get("/api/v1/acts/test-act-2000/sections/1")
        # the act_name may change the slug, so look the section up by its own slug
        if r.status_code == 404:
            r = client.get(f"/api/v1/acts/{repo.sections[0]['act_slug']}/sections/1")
        body = r.json()
        assert body["force_status"] == "repealed" and body["in_force"] is False, over


def test_section_unclear_repeal_note_is_never_called_in_force(client, repo):
    _section(
        repo, act_name="Test Act, 2000 (Rep. by Act 5 of 2001)", act_status="in_force"
    )
    r = client.get("/api/v1/acts/test-act-2000/sections/1").json()
    assert r["force_status"] == "not_checked" and r["in_force"] is None


def test_case_has_no_judge_or_party_fields(client, repo):
    repo.cases["c1"] = {
        "record_id": "c1", "title": "A v B", "court": "Supreme Court",
        "decision_date": None, "case_number": "1/2000", "citation_string": "1 SCC 1",
        "url": "https://x.invalid/c.pdf", "paragraphs": [{"anchor": "p1", "text": "t"}],
        "judges": "SHOULD NOT LEAK", "petitioner": "SHOULD NOT LEAK",
    }  # fmt: skip
    r = client.get("/api/v1/cases/c1", headers=auth())
    assert r.status_code == 200
    assert "SHOULD NOT LEAK" not in r.text


def test_openapi_published(client):
    spec = client.get("/openapi.json").json()
    assert "/api/v1/conversations/{conv_id}/messages" in spec["paths"]


async def test_memory_repo_methods_are_user_scoped(repo):
    a = await repo.upsert_user("a", None, None)
    b = await repo.upsert_user("b", None, None)
    conv = await repo.create_conversation(a["id"], "research", None)
    assert await repo.add_user_message(b["id"], conv["id"], "x") is None
    assert await repo.history(b["id"], conv["id"], "none") == ([], "")
    assert await repo.get_conversation(b["id"], conv["id"]) is None


def test_no_pipeline_means_503_and_nothing_stored(make_client, repo):
    c = make_client()
    c.app.state.pipeline = None
    conv = c.post("/api/v1/conversations", json={}, headers=auth()).json()
    r = c.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "hi"}, headers=auth(),
    )  # fmt: skip
    assert r.status_code == 503
    assert repo.msgs[conv["id"]] == []


def test_judgment_titles_never_leave_the_server(client):
    from tests.api.conftest import parse_sse

    conv = client.post("/api/v1/conversations", json={}, headers=auth()).json()
    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "q"}, headers=auth(),
    )  # fmt: skip
    assert "Fake v. Fake" not in r.text
    cit = [d for n, d in parse_sse(r.text) if n == "citations"][0]
    assert cit["citations"][0]["title"] is None


def test_real_pipeline_wires_core_gate_and_verifier(monkeypatch, repo):
    """build_pipeline fills Deps with core's own gate and verify (never a stand-in),
    and refuses to build without SEAL_KEY."""
    import core.gate
    import core.verify
    from api.deps import build_pipeline
    from core.settings import Settings, get_settings

    monkeypatch.setenv("SEAL_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        build_pipeline(Settings(ENVIRONMENT="development"), repo)
    monkeypatch.setenv("SEAL_KEY", "test-seal-key")
    get_settings.cache_clear()
    pipe = build_pipeline(Settings(ENVIRONMENT="development"), repo)
    assert pipe.deps.gate is core.gate.gate and pipe.deps.verify is core.verify.verify
    assert pipe.deps.usage is repo and pipe.deps.store is repo
    get_settings.cache_clear()


def test_unchecked_status_goes_over_the_wire_exactly():
    from api.bridge import to_wire_citation
    from core.contracts import Citation as CoreCitation

    c = CoreCitation(
        source_id="S1", record_id="r", status="unchecked", citation_string=None,
        pdf_url="https://x.invalid/a.pdf", source_url=None,
    )  # fmt: skip
    assert to_wire_citation(c).model_dump()["status"] == "unchecked"


def test_a_citation_with_no_link_goes_over_the_wire_with_no_url():
    """The dataset has no source link for some records (Supreme Court rows in the parquet,
    regulator records). The citation still goes out with its string and status; the url is
    None, never an empty string."""
    from api.bridge import to_wire_citation
    from core.contracts import Citation as CoreCitation

    for pdf, src in ((None, None), ("", ""), (None, ""), ("", None)):
        c = CoreCitation(
            source_id="S1", record_id="r", status="verified", citation_string="[1999] 1 S.C.R. 377",
            pdf_url=pdf, source_url=src,
        )  # fmt: skip
        wire = to_wire_citation(c).model_dump()
        assert wire["url"] is None and wire["citation_string"] == "[1999] 1 S.C.R. 377"
        assert wire["status"] == "verified"


def test_unknown_status_is_rejected_by_the_wire_schema():
    from api.schemas import Citation

    with pytest.raises(ValueError):
        Citation(source_id="S1", kind="act", record_id="r", status="failed")


async def test_worker_refuses_to_start_without_seal_key(monkeypatch):
    from core.settings import get_settings
    from workers.main import WorkerSettings

    monkeypatch.setenv("SEAL_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        await WorkerSettings.on_startup({})
    monkeypatch.setenv("SEAL_KEY", "test-seal-key")
    get_settings.cache_clear()
    await WorkerSettings.on_startup({})
    get_settings.cache_clear()


class _Closable:
    def __init__(self, boom=False):
        self.closed, self.boom = 0, boom

    async def aclose(self):
        self.closed += 1
        if self.boom:
            raise RuntimeError("x")


def _pipe(decisions):
    from types import SimpleNamespace

    return SimpleNamespace(deps=SimpleNamespace(decisions=decisions))


def test_shutdown_closes_decisions_once(make_client):
    from fastapi.testclient import TestClient

    dec = _Closable()
    c = make_client(pipeline=_pipe(dec))
    with TestClient(c.app):
        assert dec.closed == 0
    assert dec.closed == 1


def test_shutdown_is_safe_without_a_pipeline_or_aclose(make_client):
    from fastapi.testclient import TestClient

    c = make_client()
    c.app.state.pipeline = None  # fail-closed 503 mode
    with TestClient(c.app):
        pass
    c.app.state.pipeline = _pipe(object())  # no aclose
    with TestClient(c.app):
        pass
    c.app.state.pipeline = _pipe(_Closable(boom=True))  # aclose raises
    with TestClient(c.app):
        pass


async def test_worker_shutdown_safe_and_closes():
    from workers.main import on_shutdown

    await on_shutdown({})  # never built a pipeline
    dec = _Closable()
    await on_shutdown({"pipeline": _pipe(dec)})
    assert dec.closed == 1


def test_only_api_deps_imports_begin_run():
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2]
    hits = [
        str(p.relative_to(root))
        for d in ("api", "workers", "core")
        for p in (root / d).rglob("*.py")
        if re.search(
            r"^\s*(from adapters\.jev import[^\n]*begin_run|import adapters\.jev)",
            p.read_text(),
            re.M,
        )
    ]
    assert hits == ["api/deps.py"]
