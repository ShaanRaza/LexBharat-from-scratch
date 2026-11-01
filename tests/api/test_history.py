"""History and search across the user's OWN work. Isolation is the point."""

import pytest

from core.user_search import search_my_work
from tests.api.conftest import auth

API = "/api/v1"


def _ask(c, text, uid):
    conv = c.post(f"{API}/conversations", json={}, headers=auth(uid)).json()
    c.post(
        f"{API}/conversations/{conv['id']}/messages",
        json={"content": text},
        headers=auth(uid),
    )
    return conv["id"]


def _search(c, q, uid):
    r = c.get(f"{API}/history/search", params={"q": q}, headers=auth(uid))
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_search_finds_my_own_questions_and_answers(client):
    cid = _ask(client, "What is anticipatory bail?", "alice")
    hits = _search(client, "anticipatory", "alice")
    assert {h["kind"] for h in hits} == {"conversation", "message"}
    assert all(h["conversation_id"] == cid for h in hits)
    assert _search(
        client, "FAKE ANSWER", "alice"
    )  # the saved answer text is searchable


def test_user_a_search_never_returns_user_b_rows(client):
    a = _ask(client, "bail for cheque dishonour", "alice")
    b = _ask(client, "bail for cheque dishonour", "bob")  # identical words
    ours = {h["conversation_id"] for h in _search(client, "bail cheque", "alice")}
    theirs = {h["conversation_id"] for h in _search(client, "bail cheque", "bob")}
    assert ours == {a} and theirs == {b}
    # a word only Bob used is invisible to Alice
    _ask(client, "zebracrossing secret matter", "bob")
    assert _search(client, "zebracrossing", "alice") == []
    assert _search(client, "zebracrossing", "bob")


def test_an_empty_or_missing_query_is_refused(client):
    assert client.get(f"{API}/history/search", headers=auth()).status_code == 422
    assert (
        client.get(
            f"{API}/history/search", params={"q": ""}, headers=auth()
        ).status_code
        == 422
    )
    assert client.get(f"{API}/history/search", params={"q": "x"}).status_code == 401


def test_search_hits_carry_the_matter_so_the_screen_can_link_it(client):
    m = client.post(f"{API}/matters", json={"title": "M"}, headers=auth()).json()
    conv = client.post(
        f"{API}/conversations", json={"matter_id": m["id"]}, headers=auth()
    ).json()
    client.post(
        f"{API}/conversations/{conv['id']}/messages",
        json={"content": "limitation period"},
        headers=auth(),
    )
    assert {h["matter_id"] for h in _search(client, "limitation", "alice")} == {m["id"]}


# ---- the one shared function ------------------------------------------------------
async def test_the_shared_function_refuses_a_missing_user_and_a_lying_repository():
    class Repo:
        async def search_user_work(self, user_id, q, limit):
            return [{"user_id": "bob", "kind": "message"}]  # a bug: another user's row

    with pytest.raises(PermissionError):
        await search_my_work(Repo(), "", "bail")
    with pytest.raises(PermissionError):
        await search_my_work(Repo(), "alice", "bail")  # the row is checked again


async def test_a_blank_query_returns_nothing_without_touching_the_repository():
    class Boom:
        async def search_user_work(self, *a):
            raise AssertionError("must not be called")

    assert await search_my_work(Boom(), "alice", "   ") == []


def test_only_the_shared_function_calls_the_repository_search():
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    offenders = []
    for base in ("core", "api", "workers"):
        for f in (root / base).rglob("*.py"):
            if f.name == "user_search.py":
                continue
            if re.search(r"\.search_user_work\(", f.read_text()):
                offenders.append(str(f.relative_to(root)))
    assert offenders == []
