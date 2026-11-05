"""DELETE /matters/{id}: the user must choose, and "everything" really deletes (A52)."""

from adapters.qdrant import FakeVectorStore
from tests.api.conftest import auth


def _user_id(client, name="alice"):
    return client.get("/api/v1/me", headers=auth(name)).json()["id"]


async def _matter_with_upload(client, repo, name="alice"):
    uid = _user_id(client, name)
    m = await repo.create_matter(uid, "State v Doe", "matter")
    d = await repo.create_document(uid, "f.pdf", m["id"], "client text")
    svc = client.app.state.docs
    svc.files.put(uid, d, b"%PDF")
    svc.vectors.add_upload(f"{d}-0", "client text", uid, d)
    return m["id"], d, svc, uid


def _delete(client, mid, mode=None, uid="alice"):
    q = f"?mode={mode}" if mode else ""
    return client.delete(f"/api/v1/matters/{mid}{q}", headers=auth(uid))


async def test_the_user_must_choose_a_mode(client, repo):
    mid, d, svc, uid = await _matter_with_upload(client, repo)
    assert _delete(client, mid).status_code == 422  # no default: they are asked
    assert _delete(client, mid, "default").status_code == 422
    assert mid in repo.matters and await svc.files.exists(uid, d)  # nothing happened


async def test_delete_matter_only_keeps_the_upload_unfiled(client, repo):
    mid, d, svc, uid = await _matter_with_upload(client, repo)
    r = _delete(client, mid, "unfile")
    assert r.status_code == 200
    assert r.json() == {
        "mode": "unfile",
        "documents_deleted": 0,
        "conversations_deleted": 0,
    }
    assert mid not in repo.matters
    assert repo.documents[d]["matter_id"] is None and await svc.files.exists(uid, d)


async def test_delete_everything_hard_deletes_the_upload(client, repo):
    mid, d, svc, uid = await _matter_with_upload(client, repo)
    r = _delete(client, mid, "everything")
    assert r.status_code == 200 and r.json()["documents_deleted"] == 1
    assert mid not in repo.matters and d not in repo.documents
    assert not await svc.files.exists(uid, d)
    assert await svc.vectors.count_upload_vectors(uid, d) == 0


async def test_another_users_matter_is_a_404_and_nothing_is_deleted(client, repo):
    mid, d, svc, uid = await _matter_with_upload(client, repo)
    _user_id(client, "mallory")  # a real, different user
    assert _delete(client, mid, "everything", uid="mallory").status_code == 404
    assert mid in repo.matters and await svc.files.exists(uid, d)


async def test_a_delete_that_cannot_finish_keeps_the_matter_and_says_so(
    make_client, repo
):
    class Keeps(FakeVectorStore):
        async def delete_upload_vectors(self, user_id, document_id):
            return None

    c = make_client()
    c.app.state.docs.vectors = Keeps(c.app.state.core_settings)
    mid, d, svc, uid = await _matter_with_upload(c, repo)
    r = _delete(c, mid, "everything")
    assert r.status_code == 503 and r.json()["error"]["code"] == "service_unavailable"
    assert mid in repo.matters  # kept: nothing was silently orphaned
    assert "The matter was kept" in r.json()["error"]["message"]


def test_needs_a_login(client):
    assert client.delete("/api/v1/matters/x?mode=unfile").status_code == 401
