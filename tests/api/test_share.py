"""Share a saved answer by link, over HTTP (PRD-v2 O14)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from core.contracts import AnswerProvenance
from core.settings import Settings
from tests.api.conftest import auth

API = "/api/v1"


def _user_id(c, name="alice"):
    return c.get(f"{API}/me", headers=auth(name)).json()["id"]


def _answered(c, text="What is bail?", name="alice"):
    conv = c.post(f"{API}/conversations", json={}, headers=auth(name)).json()
    c.post(
        f"{API}/conversations/{conv['id']}/messages",
        json={"content": text},
        headers=auth(name),
    )
    msgs = c.get(f"{API}/conversations/{conv['id']}", headers=auth(name)).json()[
        "messages"
    ]
    return conv["id"], msgs


def _share(c, message_id, name="alice"):
    return c.post(f"{API}/messages/{message_id}/share", headers=auth(name))


async def _shaped_answer(c, repo, name="alice", upload=False, fact=False):
    """Save an assistant answer the way step 11 does, with the provenance flags set."""
    uid = _user_id(c, name)
    conv = await repo.create_conversation(uid, "research", None)
    await repo.add_user_message(uid, conv["id"], "my question")
    result = SimpleNamespace(
        outcome="answered", cache_hit=False, model="m", input_tokens=0, output_tokens=0,
        provenance=AnswerProvenance(upload, fact),
        answer=SimpleNamespace(text="An answer [S1].", citations=()),
    )  # fmt: skip
    await repo.save(SimpleNamespace(conversation_id=conv["id"], user_id=uid), result)
    return repo.msgs[conv["id"]][-1]["id"]


# ---- refusal, end to end ---------------------------------------------------------
async def test_creating_a_link_is_refused_for_an_upload_shaped_answer(client, repo):
    mid = await _shaped_answer(client, repo, upload=True)
    r = _share(client, mid)
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    assert "uploaded file or saved case notes" in r.json()["error"]["message"]
    assert repo.shares == {}  # no row, so no token exists
    assert client.get(f"{API}/share", headers=auth()).json()["items"] == []


async def test_creating_a_link_is_refused_for_a_matter_fact_shaped_answer(client, repo):
    mid = await _shaped_answer(client, repo, fact=True)
    r = _share(client, mid)
    assert r.status_code == 403
    assert "uploaded file or saved case notes" in r.json()["error"]["message"]
    assert repo.shares == {}


async def test_the_memory_repository_refuses_too_even_if_the_route_were_skipped(
    client, repo
):
    mid = await _shaped_answer(client, repo, upload=True)
    uid = _user_id(client)
    import pytest

    with pytest.raises(ValueError):
        await repo.create_share_link(
            uid, mid, "h", datetime.now(UTC) + timedelta(days=1)
        )


def test_a_clean_answer_gets_a_link_and_a_question_does_not(client):
    _, msgs = _answered(client)
    question, answer = msgs[0], msgs[-1]
    assert _share(client, question["id"]).status_code == 403  # only an answer
    r = _share(client, answer["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["path"] == f"/s/{body['token']}" and len(body["token"]) >= 43


def test_someone_elses_answer_or_an_unknown_one_looks_absent(client):
    _, msgs = _answered(client, name="alice")
    _user_id(client, "mallory")
    assert _share(client, msgs[-1]["id"], name="mallory").status_code == 404
    assert _share(client, "no-such-id").status_code == 404
    assert _share(client, msgs[-1]["id"]).status_code == 201  # Alice still can


def test_sharing_needs_a_login(client):
    assert client.post(f"{API}/messages/x/share").status_code == 401
    assert client.get(f"{API}/share").status_code == 401
    assert client.delete(f"{API}/share/x").status_code == 401


# ---- the public page ---------------------------------------------------------------
def test_the_public_page_needs_no_login_and_is_private_to_search_engines_and_caches(
    client,
):
    _, msgs = _answered(client)
    token = _share(client, msgs[-1]["id"]).json()["token"]
    r = client.get(f"{API}/s/{token}")  # no Authorization header
    assert r.status_code == 200
    assert (
        "noindex" in r.headers["x-robots-tag"]
        and "nofollow" in r.headers["x-robots-tag"]
    )
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_the_public_page_carries_date_credit_and_notice_and_names_no_one(client):
    _, msgs = _answered(client)
    token = _share(client, msgs[-1]["id"]).json()["token"]
    body = client.get(f"{API}/s/{token}").json()
    assert set(body) == {"question", "text", "citations", "expires_at", "provenance"}
    p = body["provenance"]
    assert p["data_as_of"].startswith("6 November 2025") and p["credit"].startswith(
        "Data: Open India Law"
    )
    assert p["notice"]  # the not-legal-advice notice
    text = client.get(f"{API}/s/{token}").text.lower()
    for private in (
        "alice",
        "@",
        "user_id",
        "conversation",
        "matter_id",
        "email",
        "judge",
        "petitioner",
    ):
        assert private not in text


CITES = [
    {
        "source_id": "S1", "kind": "judgment", "record_id": "r1", "anchor": "p3",
        "title": None, "citation_string": "(2020) 1 SCC 1",
        "url": "https://example.invalid/r1.pdf", "status": "verified",
    },
    {
        "source_id": "S2", "kind": "act", "record_id": "r2", "act_slug": "ipc-1860",
        "section": "420", "title": "Indian Penal Code, 1860", "status": "partly",
    },
]  # fmt: skip


def test_shared_citations_keep_their_ticks_and_never_carry_a_judgment_title(
    client, repo
):
    _, msgs = _answered(client)
    mid = msgs[-1]["id"]
    for conv in repo.msgs.values():
        for m in conv:
            if m["id"] == mid:
                m["citations"] = CITES
    token = _share(client, mid).json()["token"]
    cites = client.get(f"{API}/s/{token}").json()["citations"]
    assert [c["status"] for c in cites] == ["verified", "partly"]
    assert cites[0]["title"] is None and cites[0]["citation_string"] == "(2020) 1 SCC 1"
    assert all(c["status"] in ("verified", "partly", "unchecked") for c in cites)


# ---- revoke and expiry take effect at once ----------------------------------
def test_revoking_takes_effect_immediately(client):
    _, msgs = _answered(client)
    made = _share(client, msgs[-1]["id"]).json()
    url = f"{API}/s/{made['token']}"
    assert client.get(url).status_code == 200
    assert client.delete(f"{API}/share/{made['id']}", headers=auth()).status_code == 200
    r = client.get(url)  # the very next request
    assert r.status_code == 404 and "noindex" in r.headers["x-robots-tag"]
    assert (
        client.delete(f"{API}/share/{made['id']}", headers=auth()).status_code == 404
    )  # already revoked


def test_only_the_owner_can_revoke(client):
    _, msgs = _answered(client, name="alice")
    _user_id(client, "mallory")
    made = _share(client, msgs[-1]["id"]).json()
    assert (
        client.delete(f"{API}/share/{made['id']}", headers=auth("mallory")).status_code
        == 404
    )
    assert client.get(f"{API}/s/{made['token']}").status_code == 200  # still alive


def test_an_expired_link_stops_working(client, repo):
    _, msgs = _answered(client)
    made = _share(client, msgs[-1]["id"]).json()
    repo.shares[made["id"]]["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get(f"{API}/s/{made['token']}").status_code == 404


def test_a_link_stops_working_if_the_answer_is_later_marked_as_shaped(client, repo):
    _, msgs = _answered(client)
    mid = msgs[-1]["id"]
    made = _share(client, mid).json()
    for conv in repo.msgs.values():
        for m in conv:
            if m["id"] == mid:
                m["shaped_by_upload"] = (
                    True  # belt and braces: re-checked on every read
                )
    assert client.get(f"{API}/s/{made['token']}").status_code == 404


def test_unknown_revoked_and_expired_look_identical(client, repo):
    _, msgs = _answered(client)
    made = _share(client, msgs[-1]["id"]).json()
    client.delete(f"{API}/share/{made['id']}", headers=auth())
    a = client.get(f"{API}/s/{made['token']}")
    b = client.get(f"{API}/s/{'x' * 43}")
    assert a.status_code == b.status_code == 404
    strip = lambda r: {k: v for k, v in r.json()["error"].items() if k != "request_id"}  # noqa: E731
    assert strip(a) == strip(b)  # no hint that a link ever existed


# ---- the token is never stored ---------------------------------------------
def test_only_a_hash_is_stored_and_listing_never_shows_a_token(client, repo):
    _, msgs = _answered(client)
    made = _share(client, msgs[-1]["id"]).json()
    assert made["token"] not in str(repo.shares)  # not stored anywhere
    row = next(iter(repo.shares.values()))
    assert len(row["token_hash"]) == 64
    listed = client.get(f"{API}/share", headers=auth()).json()["items"]
    assert [x["id"] for x in listed] == [made["id"]]
    assert "token" not in str(listed) and "token_hash" not in str(listed)


def test_two_links_to_the_same_answer_are_independent(client):
    _, msgs = _answered(client)
    a, b = _share(client, msgs[-1]["id"]).json(), _share(client, msgs[-1]["id"]).json()
    assert a["token"] != b["token"]
    client.delete(f"{API}/share/{a['id']}", headers=auth())
    assert client.get(f"{API}/s/{a['token']}").status_code == 404
    assert client.get(f"{API}/s/{b['token']}").status_code == 200


def test_the_expiry_period_is_a_setting(make_client):
    c = make_client(core_settings=Settings(SHARE_LINK_EXPIRY_DAYS=1))
    _, msgs = _answered(c)
    exp = datetime.fromisoformat(_share(c, msgs[-1]["id"]).json()["expires_at"])
    assert timedelta(hours=23) < exp - datetime.now(UTC) < timedelta(hours=25)
