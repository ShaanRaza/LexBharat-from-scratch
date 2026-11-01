"""Hard delete of an uploaded document, and of a matter with everything in it (A52).

Plain words: "delete" means gone. For one document that is three things, done in one
job and logged: the file in S3, every vector in Qdrant (matched on user AND document
id), and the extracted text and record in PostgreSQL. After deleting, the job looks
again and raises if anything is left. A nightly check re-looks at everything deleted
recently, so a half-failed delete is found and finished, not forgotten.

Deleting a matter asks the user which of two things they mean (the route needs `mode`):
  * "unfile":     delete the matter only; its work moves to unfiled (nothing deleted)
  * "everything": delete the matter and everything in it. Uploads are hard-deleted one
                  by one, and if ANY cannot be fully deleted the job stops: the matter
                  and its conversations are kept (files already removed stay removed),
                  so a client's file is never silently orphaned.

Not a pipeline step."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from adapters.qdrant import VectorStore
from adapters.s3 import FileStore
from core.uploads import count_user_document_vectors, delete_user_document_vectors

log = logging.getLogger(__name__)

MatterDeleteMode = Literal["unfile", "everything"]


class DeleteIncomplete(Exception):
    """Something of a deleted document is still there."""

    def __init__(self, document_id: str, left: list[str]):
        super().__init__(f"document {document_id}: still present: {', '.join(left)}")
        self.document_id, self.left = document_id, left


class MatterNotFound(Exception):
    pass


@dataclass
class DocServices:
    """What a document delete needs. `repo` has the documents/audit methods."""

    files: FileStore
    vectors: VectorStore
    repo: Any


@dataclass(frozen=True)
class MatterDeleteReport:
    mode: MatterDeleteMode
    documents_deleted: int
    conversations_deleted: int


async def find_leftover(user_id: str, document_id: str, svc: DocServices) -> list[str]:
    """What of this document is still stored. Empty = fully gone."""
    left = []
    if await svc.files.exists(user_id, document_id):
        left.append("file")
    if await count_user_document_vectors(svc.vectors, user_id, document_id):
        left.append("vectors")
    if await svc.repo.document_rows_remaining(document_id):
        left.append("database")
    return left


async def hard_delete_document(
    user_id: str, document_id: str, svc: DocServices
) -> None:
    """File, vectors and database rows, then verify. Raises DeleteIncomplete if
    anything is left. The intent is logged FIRST so the nightly check knows about a
    delete that fails half way. The log never holds document text."""
    await svc.repo.audit(user_id, "delete", f"document:{document_id}")
    await svc.files.delete(user_id, document_id)
    await delete_user_document_vectors(svc.vectors, user_id, document_id)
    await svc.repo.delete_document_rows(user_id, document_id)
    left = await find_leftover(user_id, document_id, svc)
    if left:
        raise DeleteIncomplete(document_id, left)


async def leftover_check(svc: DocServices, days: int = 2) -> list[DeleteIncomplete]:
    """The nightly check: every document deleted in the last `days` days must be fully
    gone. Anything found is deleted again; what still will not go is returned."""
    problems: list[DeleteIncomplete] = []
    for user_id, document_id in await svc.repo.deleted_documents(days):
        left = await find_leftover(user_id, document_id, svc)
        if not left:
            continue
        log.warning("leftover after delete: %s %s", document_id, left)
        try:
            await hard_delete_document(user_id, document_id, svc)
        except DeleteIncomplete as e:
            problems.append(e)
    return problems


async def delete_matter(
    user_id: str,
    matter_id: str,
    mode: MatterDeleteMode,
    svc: DocServices | None,
    repo: Any,
) -> MatterDeleteReport:
    if mode not in ("unfile", "everything"):
        raise ValueError("mode must be 'unfile' or 'everything'")
    if await repo.get_matter(user_id, matter_id) is None:  # also the ownership check
        raise MatterNotFound(matter_id)
    docs_deleted = 0
    if mode == "everything":
        doc_ids = await repo.matter_document_ids(user_id, matter_id)
        if doc_ids and svc is None:
            # Never skip a client's file because the delete machinery is not there.
            raise DeleteIncomplete(doc_ids[0], ["no document store configured"])
        for doc_id in doc_ids:
            await hard_delete_document(user_id, doc_id, svc)  # type: ignore[arg-type]
            docs_deleted += 1
    convs = await repo.delete_matter(
        user_id, matter_id, delete_conversations=(mode == "everything")
    )
    return MatterDeleteReport(mode, docs_deleted, convs)
