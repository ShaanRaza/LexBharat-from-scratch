"""Matters: list, create, open, rename, archive, and filing conversations under them."""

from tests.api.conftest import auth

API = "/api/v1"


def _make(c, title="State v Doe", uid="alice", **extra):
    r = c.post(f"{API}/matters", json={"title": title, **extra}, headers=auth(uid))
    assert r.status_code == 201, r.text
    return r.json()


def _conv(c, uid="alice", **body):
    r = c.post(f"{API}/conversations", json=body, headers=auth(uid))
    assert r.status_code == 201, r.text
    return r.json()


def test_create_list_and_open_a_matter(client):
    m = _make(client)
    assert (
        m["kind"] == "matter"
        and m["status"] == "active"
        and m["conversation_count"] == 0
    )
    p = _make(client, "Moot prep", kind="project")  # a label, not a second feature
    assert p["kind"] == "project"
    items = client.get(f"{API}/matters", headers=auth()).json()["items"]
    assert {i["title"] for i in items} == {"State v Doe", "Moot prep"}
    got = client.get(f"{API}/matters/{m['id']}", headers=auth()).json()
    assert got["title"] == "State v Doe" and got["conversations"] == []


def test_rename_archive_and_restore(client):
    m = _make(client)
    r = client.patch(
        f"{API}/matters/{m['id']}", json={"title": " Renamed "}, headers=auth()
    )
    assert r.json()["title"] == "Renamed"  # trimmed
    r = client.patch(
        f"{API}/matters/{m['id']}", json={"status": "archived"}, headers=auth()
    )
    assert r.json()["status"] == "archived" and r.json()["archived_at"] is not None
    assert client.get(f"{API}/matters", headers=auth()).json()["items"] == []  # hidden
    arch = client.get(f"{API}/matters?status=archived", headers=auth()).json()["items"]
    assert [a["id"] for a in arch] == [m["id"]]
    both = client.get(f"{API}/matters?status=all", headers=auth()).json()["items"]
    assert len(both) == 1
    r = client.patch(
        f"{API}/matters/{m['id']}", json={"status": "active"}, headers=auth()
    )
    assert r.json()["status"] == "active" and r.json()["archived_at"] is None


def test_archiving_deletes_nothing(client, repo):
    m = _make(client)
    c = _conv(client, matter_id=m["id"])
    client.patch(
        f"{API}/matters/{m['id']}", json={"status": "archived"}, headers=auth()
    )
    got = client.get(f"{API}/matters/{m['id']}", headers=auth()).json()
    assert [x["id"] for x in got["conversations"]] == [c["id"]]


def test_patch_needs_something_to_change_and_a_title_must_not_be_empty(client):
    m = _make(client)
    assert (
        client.patch(f"{API}/matters/{m['id']}", json={}, headers=auth()).status_code
        == 422
    )
    r = client.patch(f"{API}/matters/{m['id']}", json={"title": ""}, headers=auth())
    assert r.status_code in (400, 422)
    assert client.post(
        f"{API}/matters", json={"title": ""}, headers=auth()
    ).status_code in (400, 422)


def test_a_conversation_can_start_in_a_matter_and_moves_between_them(client):
    a, b = _make(client, "A"), _make(client, "B")
    c = _conv(client, matter_id=a["id"])
    assert c["matter_id"] == a["id"]
    moved = client.patch(
        f"{API}/conversations/{c['id']}", json={"matter_id": b["id"]}, headers=auth()
    )
    assert moved.status_code == 200 and moved.json()["matter_id"] == b["id"]
    ga = client.get(f"{API}/matters/{a['id']}", headers=auth()).json()
    gb = client.get(f"{API}/matters/{b['id']}", headers=auth()).json()
    assert ga["conversation_count"] == 0 and gb["conversation_count"] == 1
    assert [x["id"] for x in gb["conversations"]] == [c["id"]]
    unfiled = client.patch(
        f"{API}/conversations/{c['id']}", json={"matter_id": None}, headers=auth()
    )
    assert unfiled.json()["matter_id"] is None


def test_conversation_list_can_be_filtered_by_matter_or_unfiled(client):
    m = _make(client)
    inside, outside = _conv(client, matter_id=m["id"]), _conv(client)

    def ids(q):
        return {
            i["id"]
            for i in client.get(f"{API}/conversations{q}", headers=auth()).json()[
                "items"
            ]
        }

    assert ids("") == {inside["id"], outside["id"]}
    assert ids(f"?matter_id={m['id']}") == {inside["id"]}
    assert ids("?unfiled=true") == {outside["id"]}


def test_another_users_matter_is_absent_everywhere(client, repo):
    m = _make(client, uid="alice")
    client.get(f"{API}/me", headers=auth("mallory"))  # a real second user
    mine = _conv(client, uid="mallory")
    h = auth("mallory")
    assert client.get(f"{API}/matters/{m['id']}", headers=h).status_code == 404
    assert (
        client.patch(
            f"{API}/matters/{m['id']}", json={"title": "x"}, headers=h
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{API}/conversations", json={"matter_id": m["id"]}, headers=h
        ).status_code
        == 404
    )
    r = client.patch(
        f"{API}/conversations/{mine['id']}", json={"matter_id": m["id"]}, headers=h
    )
    assert r.status_code == 404  # cannot file work under someone else's matter
    # and Mallory cannot move Alice's conversation into her own matter either
    theirs = _conv(client, uid="alice")
    own = _make(client, "Mine", uid="mallory")
    r = client.patch(
        f"{API}/conversations/{theirs['id']}", json={"matter_id": own["id"]}, headers=h
    )
    assert r.status_code == 404
    assert client.get(f"{API}/matters", headers=h).json()["items"][0]["title"] == "Mine"
    assert len(client.get(f"{API}/matters", headers=h).json()["items"]) == 1


def test_matters_need_a_login(client):
    assert client.get(f"{API}/matters").status_code == 401
    assert client.post(f"{API}/matters", json={"title": "x"}).status_code == 401
