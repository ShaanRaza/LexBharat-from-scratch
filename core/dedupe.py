"""Step 5 helper: drop repeated passages before anything is re-ranked or labelled.

Plain words: the same passage can come back from the search twice. In the corpus,
4,871 chunk ids sit on two points each (measured 2 Nov 2026 on one court's
judgments). Left alone, both copies could take two of the eight gate slots and get two
different source labels (S1 and S4), so one answer could cite identical text twice
with every verifier check passing. So we keep one copy of each repeated passage.

Two rules, applied in this order:
1. Same chunk id (`record_id`): keep one copy, drop the others.
2. Same text AND the same source document: keep one copy, drop the others. The source
   document is the case (`case_id`) for a judgment and the Act (`act_slug`, the
   payload's `act_id`) for a provision. Text is compared after collapsing runs of
   whitespace, so copies that differ only by spacing are the same.

Identical text from two DIFFERENT documents is never merged. Short titles, repealed
placeholders and definitions repeat word for word across state adaptations of a central
Act; those are different authorities, and dropping one would let an answer cite the
wrong Act with every verifier check passing. A passage whose document is unknown
(uploads, or a record missing its `case_id` / `act_id`) is never merged on text.

Which copy is kept: the higher-scoring one, except that when a corpus passage and an
uploaded passage share a chunk id the corpus copy wins, whatever the scores (it carries
a citation string and a source URL, and the verifier can check a quote against the
dataset).

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


def source_document(p: Passage) -> str | None:
    """The document a passage belongs to: its case, or its Act. None when unknown."""
    if p.kind == "judgment" and p.case_id:
        return f"case:{p.case_id}"
    if p.kind == "act_section" and p.act_slug:
        return f"act:{p.act_slug}"
    return None


def dedupe_passages(passages: Iterable[Passage]) -> list[Passage]:
    """Input: passages, best first. Output: the same list in the same order with the
    repeats removed (same chunk id, or same text inside the same source document).
    Corpus passages are considered before uploaded ones; otherwise the earlier
    (higher-scoring) copy is kept."""
    items = list(passages)
    seen_ids: set[str] = set()
    seen_text: set[tuple[str, str]] = set()
    keep: set[int] = set()
    for uploads_pass in (False, True):
        for i, p in enumerate(items):
            if (p.kind == "upload") != uploads_pass:
                continue
            if p.record_id in seen_ids:
                continue
            doc, key = source_document(p), text_key(p.text)
            same_doc_text = (doc, key) if doc is not None and key is not None else None
            if same_doc_text is not None and same_doc_text in seen_text:
                continue
            seen_ids.add(p.record_id)
            if same_doc_text is not None:
                seen_text.add(same_doc_text)
            keep.add(i)
    return [p for i, p in enumerate(items) if i in keep]
