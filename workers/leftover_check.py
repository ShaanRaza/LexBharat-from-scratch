"""Nightly leftover check for deleted documents (A52).

Plain words: after a document is hard-deleted (file, vectors, database rows) this job
looks again at everything deleted in the last couple of days and finishes any delete
that did not fully complete. Anything it still cannot remove is returned so it can be
alerted. Skipped (and says so) while uploads are switched off."""

from __future__ import annotations

from core.doc_delete import leftover_check


async def leftover_check_job(ctx: dict) -> dict:
    svc = ctx.get("doc_services")
    if svc is None:
        return {"checked": False, "reason": "uploads are off"}
    problems = await leftover_check(svc)
    return {"checked": True, "unresolved": [p.document_id for p in problems]}
