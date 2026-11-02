"""Step 5 helper: drop repeated passages before anything is re-ranked or labelled.

Plain words: the same passage can come back from the search twice. In the corpus,
4,871 chunk ids sit on two points each (measured 2 Nov 2026 on one court's
judgments). Left alone, both copies could take two of the eight gate slots and get two
different source labels (S1 and S4), so one answer could cite identical text twice
with every verifier check passing. So we keep the first copy of each passage and drop
the rest.

Two rules, applied in this order:
1. Same chunk id (`record_id`): keep one copy, drop the others.
2. Same text: keep one copy, drop the others. The text is compared after collapsing
   runs of whitespace, so copies that differ only by spacing are the same.

Which copy is kept: the higher-scoring one, EXCEPT when a corpus passage and an
uploaded passage are duplicates. Then the corpus copy always wins, whatever the scores.
It carries a citation string and a source URL, and the verifier can check a quote
against the dataset; the uploaded copy has neither.

Load-bearing, not an optimisation: `gate.ratings` is keyed by `record_id`, so a
duplicate reaching the gate would silently collapse a rating instead of raising an
error. The gate spy in tests/trust/test_dedupe.py is what guards that. Do not remove
this step.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from core.contracts import Passage


def text_key(text: str) -> str | None:
    """Hash of the passage body with whitespace collapsed. None for an empty body: empty
    passages are never merged with each other on text, only on chunk id."""
    body = " ".join(text.split())
    return hashlib.sha256(body.encode()).hexdigest() if body else None


def dedupe_passages(passages: Iterable[Passage]) -> list[Passage]:
    """Input: passages, best first. Output: the same list in the same order with the
    repeats (same chunk id, or same text) removed. Corpus passages are considered before
    uploaded ones, so an uploaded duplicate of a corpus passage is always the one
    dropped; among corpus passages, or among uploads, the earlier (higher-scoring) one
    is kept."""
    items = list(passages)
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    keep: set[int] = set()
    for uploads_pass in (False, True):
        for i, p in enumerate(items):
            if (p.kind == "upload") != uploads_pass:
                continue
            if p.record_id in seen_ids:
                continue
            key = text_key(p.text)
            if key is not None and key in seen_text:
                continue
            seen_ids.add(p.record_id)
            if key is not None:
                seen_text.add(key)
            keep.add(i)
    return [p for i, p in enumerate(items) if i in keep]
