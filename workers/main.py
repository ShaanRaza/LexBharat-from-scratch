"""Background worker (ARQ): runs jobs the API puts on the Redis queue.

Start it:  arq workers.main.WorkerSettings
Why a worker: OCR and clean-up can take minutes; the chat must stay fast, so they run in
their own container, ONE job at a time (docs/ARCHITECTURE.md "Uploads").

This is a SKELETON. The jobs below say what they will do and fail loudly (not quietly)
until the adapters they need exist. Every outside service is reached through one file in
adapters/ (rule 1); the worker never calls S3, Qdrant, Firebase or Razorpay directly.
"""

import logging
from typing import Any

from arq.connections import RedisSettings

from core.settings import get_settings

log = logging.getLogger("workers")


async def ocr_document(ctx: dict[str, Any], document_id: str, user_id: str) -> dict:
    """STUB. Will: fetch the file from S3, read the text layer with PyMuPDF (text PDFs) or
    Tesseract English+Hindi (scans), chunk it keeping page_no/char_start/char_end, embed
    the chunks into `user_documents` (always with the user_id), and set the document
    status uploaded -> extracting -> indexing -> ready, or `failed` with a reason (an
    unreadable scan is not charged).

    Uploads are switched off at launch (FEATURE_UPLOADS), so nothing queues this yet.
    Never log document text here (CLAUDE.md section 6).
    """
    log.info("ocr_document stub document_id=%s", document_id)  # IDs only, never text
    return {"document_id": document_id, "status": "not_implemented"}


async def delete_document(
    ctx: dict[str, Any], user_id: str, document_id: str, storage_path: str | None
) -> None:
    """STUB. Hard delete of what lives OUTSIDE PostgreSQL: the S3 object at
    `storage_path` and every Qdrant vector with this document_id; log it; the nightly
    leftover check verifies. (The API already removed the PostgreSQL rows.)"""
    raise NotImplementedError("needs adapters for S3 and Qdrant (Core lane)")


async def delete_account(ctx: dict[str, Any], user_id: str, **cleanup: Any) -> None:
    """STUB. After DELETE /me removed the PostgreSQL rows, this removes the rest:
    every S3 object in `storage_paths`, every Qdrant vector for `document_ids`, the
    Firebase user `firebase_uid`, and cancels each of `razorpay_subscription_ids`.

    Contract: run only once the users row is gone; if it still exists, retry later
    (the API queues this job before deleting the row). Payment and invoice records are
    kept, as the law requires. It receives IDs and paths only, never text.
    """
    raise NotImplementedError(
        "needs adapters for S3, Qdrant, Firebase, Razorpay (Core lane)"
    )


class WorkerSettings:
    """ARQ reads this class. Values come from core.settings (rule 2)."""

    functions = (ocr_document, delete_document, delete_account)
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
    # One job at a time so OCR never slows chat (docs/ARCHITECTURE.md).
    max_jobs = 1
    # A scanned 50-page PDF must be ready in under 5 minutes (CLAUDE.md section 10).
    job_timeout = 600
    max_tries = 3
