"""A127, live: a DOCUMENT call through adapters/voyage.py reproduces a real stored vector.

Skipped unless VOYAGE_API_KEY is set in the environment (it is never read from .env here
and never printed). Spends a few thousand tokens (a fraction of a rupee). Run:

    VOYAGE_API_KEY=... .venv/bin/pytest tests/integration/test_voyage_live.py -s

The fixture is five real chunks with the vector the corpus stores for them. The claim is
the one the offline stand-in in tests/core/test_voyage_adapter.py can only assume:
Voyage, asked for a document embedding by the adapter, returns the stored vector at
cosine 0.998 or better, and asked for a query embedding it does not.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from adapters.voyage import VoyageClient
from core.settings import Settings

KEY = os.environ.get("VOYAGE_API_KEY", "")
pytestmark = pytest.mark.skipif(
    not KEY, reason="VOYAGE_API_KEY not set in the environment"
)

ROWS = json.loads(
    (
        Path(__file__).resolve().parents[1] / "fixtures" / "voyage_known_vectors.json"
    ).read_text()
)["rows"]


def _cos(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


@pytest.mark.parametrize("collection", sorted({r["collection"] for r in ROWS}))
async def test_a_document_call_reproduces_the_stored_vectors_and_a_query_call_does_not(
    collection,
):
    rows = [r for r in ROWS if r["collection"] == collection]
    client = VoyageClient(
        Settings(_env_file=None, VOYAGE_API_KEY=KEY), timeout_s=60, max_attempts=3
    )
    texts = [r["text"] for r in rows]
    doc = await client.embed_batch(texts, collection, "document")
    qry = await client.embed_batch(texts, collection, "query")
    dcos = [_cos(v, r["stored_vector"]) for v, r in zip(doc.vectors, rows)]
    qcos = [_cos(v, r["stored_vector"]) for v, r in zip(qry.vectors, rows)]
    print(
        f"\n{collection} ({rows[0]['expected_model']}): document {['%.5f' % c for c in dcos]} | query {['%.4f' % c for c in qcos]} | {doc.total_tokens + qry.total_tokens} tokens"
    )
    assert min(dcos) >= 0.998, dcos
    # The trap A127 closes. Measured range for a query vector against stored documents:
    # 0.83 to 0.955 (3 Nov 2026, this test; the 2 Nov figure of 0.82 to 0.90 was 3 chunks).
    # The claim is that it is clearly below what a document call reaches, not a fixed number.
    assert max(qcos) < 0.98 and min(dcos) - max(qcos) > 0.03, (dcos, qcos)
