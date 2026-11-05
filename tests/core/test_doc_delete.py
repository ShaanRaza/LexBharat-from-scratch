"""Hard delete of uploads, and of a matter with everything in it (A52).

The promise: "delete" means the S3 file, every vector and the database text are gone,
verified, logged, and re-checked at night. Deleting a matter never silently orphans a
client's file: the user chooses, and "everything" really deletes."""

from __future__ import annotations

import pytest

from adapters.qdrant import FakeVectorStore
from adapters.s3 import FakeFileStore
from api.repo import MemoryRepo
from core.doc_delete import (
    DeleteIncomplete,
    DocServices,
    MatterNotFound,
    delete_matter,
    find_leftover,
    hard_delete_document,
    leftover_check,
)
from core.settings import Settings


class StubbornFiles(FakeFileStore):
    """A file store whose delete does nothing for the first `fail_times` calls."""

    def __init__(self, fail_times: int = 0):
        super().__init__()
        self.fail_times = fail_times

    async def delete(self, user_id, document_id):
        if self.fail_times > 0:
            self.fail_times -= 1
            return
        await super().delete(user_id, document_id)


class StubbornVectors(FakeVectorStore):
    """A vector store that silently keeps vectors."""

    async def delete_upload_vectors(self, user_id, document_id):
        return None


async def _doc(svc, user, matter_id=None, text="client secret text"):
    """A stored upload: S3 file + extracted text row + two vectors."""
    doc_id = await svc.repo.create_document(user, "f.pdf", matter_id, text)
    svc.files.put(user, doc_id, b"%PDF client file")
    for i in range(2):
        svc.vectors.add_upload(f"{doc_id}-{i}", text, user, doc_id)
    return doc_id


@pytest.fixture
def svc():
    return DocServices(
        FakeFileStore(), FakeVectorStore(Settings(_env_file=None)), MemoryRepo()
    )


async def test_hard_delete_removes_file_vectors_and_text_and_logs_it(svc):
    d = await _doc(svc, "alice")
    assert await find_leftover("alice", d, svc) == ["file", "vectors", "database"]
    await hard_delete_document("alice", d, svc)
    assert await find_leftover("alice", d, svc) == []
    assert not await svc.files.exists("alice", d)
    assert await svc.vectors.count_upload_vectors("alice", d) == 0
    assert await svc.repo.document_rows_remaining(d) == 0
    assert ("alice", "delete", f"document:{d}") in svc.repo.audit_rows
    assert "client secret" not in str(svc.repo.audit_rows)  # the log never holds text


async def test_delete_touches_only_that_document_and_that_user(svc):
    mine = await _doc(svc, "alice")
    other = await _doc(svc, "bob")
    await hard_delete_document("alice", mine, svc)
    assert await find_leftover("bob", other, svc) == ["file", "vectors", "database"]
    # Alice naming Bob's document id deletes nothing of Bob's and leaves it intact.
    with pytest.raises(DeleteIncomplete):
        await hard_delete_document("alice", other, svc)  # nothing of hers to remove...
    assert await svc.files.exists("bob", other)
    assert await svc.vectors.count_upload_vectors("bob", other) == 2
    assert await svc.repo.document_rows_remaining(other) == 1


async def test_a_delete_that_leaves_something_behind_raises_and_names_it():
    s = DocServices(
        FakeFileStore(), StubbornVectors(Settings(_env_file=None)), MemoryRepo()
    )
    d = await _doc(s, "alice")
    with pytest.raises(DeleteIncomplete) as e:
        await hard_delete_document("alice", d, s)
    assert e.value.left == ["vectors"] and e.value.document_id == d
    assert (
        "alice",
        "delete",
        f"document:{d}",
    ) in s.repo.audit_rows  # intent was logged


async def test_the_nightly_leftover_check_finishes_a_half_failed_delete():
    s = DocServices(
        StubbornFiles(fail_times=1),
        FakeVectorStore(Settings(_env_file=None)),
        MemoryRepo(),
    )
    d = await _doc(s, "alice")
    with pytest.raises(DeleteIncomplete) as e:
        await hard_delete_document("alice", d, s)  # S3 "succeeded" but kept the file
    assert e.value.left == ["file"]
    assert await s.files.exists("alice", d)  # the leftover really exists
    problems = await leftover_check(s)  # the nightly job
    assert problems == []
    assert await find_leftover("alice", d, s) == []  # now fully gone


async def test_the_leftover_check_reports_what_will_not_go():
    s = DocServices(
        FakeFileStore(), StubbornVectors(Settings(_env_file=None)), MemoryRepo()
    )
    d = await _doc(s, "alice")
    with pytest.raises(DeleteIncomplete):
        await hard_delete_document("alice", d, s)
    problems = await leftover_check(s)
    assert [p.document_id for p in problems] == [d] and problems[0].left == ["vectors"]


async def test_the_leftover_check_leaves_documents_that_were_never_deleted_alone(svc):
    d = await _doc(svc, "alice")
    assert await leftover_check(svc) == []
    assert await find_leftover("alice", d, svc) == ["file", "vectors", "database"]


# ---- matters ---------------------------------------------------------------------
async def _matter_with_work(svc):
    repo = svc.repo
    m = await repo.create_matter("alice", "State v Doe", "matter")
    d1 = await _doc(svc, "alice", m["id"])
    d2 = await _doc(svc, "alice", m["id"])
    conv = await repo.create_conversation("alice", "research", None)
    repo.convs[conv["id"]]["matter_id"] = m["id"]
    return m["id"], [d1, d2], conv["id"]


async def test_delete_everything_hard_deletes_uploads_and_the_matters_work(svc):
    m, docs, conv = await _matter_with_work(svc)
    r = await delete_matter("alice", m, "everything", svc, svc.repo)
    assert (r.documents_deleted, r.conversations_deleted) == (2, 1)
    for d in docs:
        assert await find_leftover("alice", d, svc) == []
    assert conv not in svc.repo.convs and m not in svc.repo.matters
    assert await leftover_check(svc) == []  # and the nightly check agrees


async def test_delete_matter_only_moves_work_to_unfiled_and_deletes_no_file(svc):
    m, docs, conv = await _matter_with_work(svc)
    r = await delete_matter("alice", m, "unfile", svc, svc.repo)
    assert (r.documents_deleted, r.conversations_deleted) == (0, 0)
    assert m not in svc.repo.matters
    assert svc.repo.convs[conv]["matter_id"] is None  # unfiled, not deleted
    for d in docs:  # the client's files are still there, now unfiled, not orphaned
        assert svc.repo.documents[d]["matter_id"] is None
        assert await svc.files.exists("alice", d)
        assert await svc.vectors.count_upload_vectors("alice", d) == 2


async def test_if_one_upload_cannot_be_deleted_the_matter_and_its_chats_are_kept():
    s = DocServices(
        FakeFileStore(), StubbornVectors(Settings(_env_file=None)), MemoryRepo()
    )
    m, docs, conv = await _matter_with_work(s)
    with pytest.raises(DeleteIncomplete):
        await delete_matter("alice", m, "everything", s, s.repo)
    assert m in s.repo.matters and conv in s.repo.convs  # nothing was orphaned


async def test_without_the_delete_machinery_everything_is_refused_not_skipped():
    repo = MemoryRepo()
    m = await repo.create_matter("alice", "t", "matter")
    d = await repo.create_document("alice", "f.pdf", m["id"], "text")
    with pytest.raises(DeleteIncomplete):
        await delete_matter("alice", m["id"], "everything", None, repo)
    assert m["id"] in repo.matters and d in repo.documents  # the file was not skipped
    # A matter with no uploads can be deleted without it.
    empty = await repo.create_matter("alice", "e", "project")
    await delete_matter("alice", empty["id"], "everything", None, repo)
    assert empty["id"] not in repo.matters


async def test_another_users_matter_looks_absent_and_nothing_is_deleted(svc):
    m, docs, conv = await _matter_with_work(svc)
    with pytest.raises(MatterNotFound):
        await delete_matter("mallory", m, "everything", svc, svc.repo)
    assert m in svc.repo.matters and await svc.files.exists("alice", docs[0])


async def test_mode_must_be_one_of_the_two_choices(svc):
    m, _, _ = await _matter_with_work(svc)
    with pytest.raises(ValueError):
        await delete_matter("alice", m, "default", svc, svc.repo)  # type: ignore[arg-type]
