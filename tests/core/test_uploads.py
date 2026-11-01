"""The user_id filter: one function, always on, and nothing else queries uploads."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from adapters.qdrant import FakeVectorStore, Hit
from core.uploads import search_user_documents

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def up(settings):
    s = FakeVectorStore(settings)
    s.add_upload("a1", "client bail application for Ravi", "alice", "docA")
    s.add_upload("b1", "client bail application for Sita", "bob", "docB")
    return s


async def test_user_only_sees_own_documents(up):
    hits = await search_user_documents(up, "alice", None, "bail application", (), 10)
    assert [h.record_id for h in hits] == ["a1"]
    hits = await search_user_documents(up, "bob", None, "bail application", (), 10)
    assert [h.record_id for h in hits] == ["b1"]


async def test_other_users_document_id_returns_nothing(up):
    hits = await search_user_documents(up, "alice", None, "bail", ("docB",), 10)
    assert hits == []


@pytest.mark.parametrize("uid", ["", "   "])
async def test_empty_user_id_refused(up, uid):
    with pytest.raises(PermissionError):
        await search_user_documents(up, uid, None, "bail", (), 10)


async def test_leaky_store_is_caught(settings):
    class Leaky:
        async def search_uploads(self, *a, **k):
            return [Hit("b1", "t", 1.0, {"user_id": "bob"})]

    with pytest.raises(PermissionError):
        await search_user_documents(Leaky(), "alice", None, "x", (), 5)


async def test_upload_collection_unreachable_through_law_search(up, settings):
    with pytest.raises(PermissionError):
        await up.search(settings.QDRANT_UPLOADS_COLLECTION, None, "bail", {}, 5)
    with pytest.raises(PermissionError):
        await up.get_record(settings.QDRANT_UPLOADS_COLLECTION, "a1")
    assert await up.get_record(settings.QDRANT_UPLOADS_COLLECTION, "a1", "bob") is None
    rec = await up.get_record(settings.QDRANT_UPLOADS_COLLECTION, "a1", "alice")
    assert rec and "Ravi" in rec.text


def test_only_the_shared_function_queries_uploads():
    """search_uploads( may be CALLED only from core/uploads.py (defined in adapters)."""
    offenders = []
    for base in ("core", "api", "workers", "data"):
        for f in (ROOT / base).rglob("*.py"):
            if f.name == "uploads.py" and base == "core":
                continue
            if re.search(r"\.search_uploads\(", f.read_text()):
                offenders.append(str(f.relative_to(ROOT)))
    assert offenders == []
