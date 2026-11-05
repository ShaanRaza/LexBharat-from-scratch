"""Plain-text guards for the two helpers that produce QUESTIONS, not answers
(follow-up suggestions and the "Improve my question" helper).

Neither helper may cite anything. Citations only come from the verifier. So both reject
any text that looks like a citation, and these rules are plain Python, not a model.
Not a pipeline step; nothing here touches the 11 steps."""

from __future__ import annotations

import re

# [S1], (S2), [S1, S3], full-width brackets, a bare S1..S8 label, or ANY bracketed span.
_FULL_WIDTH = str.maketrans("［］（）【】", "[]()[]")
_MARKER = re.compile(r"\[[^\]]*\]|\(\s*S\s*\d+[^)]*\)|\bS\s*[1-8]\b", re.IGNORECASE)
# Quoted words would be a quotation from a record: not a question.
_QUOTES = re.compile(r"[\"“”‘’`]")
# Citation-shaped text: "(2020) 1 SCC 1", "AIR 1978 SC 597", "A v. B", "A versus B".
_SHAPES = (
    re.compile(r"\(\s*\d{4}\s*\)\s*\d+\s*[A-Z][A-Za-z.]*\s*\d+"),
    re.compile(r"\b(?:AIR|SCC|SCR|SCALE|INSC)\b[\s.]*\d"),
    re.compile(r"\b\d{4}\s+(?:SCC|SCR|AIR|SCALE|INSC)\b"),
    re.compile(r"\b[A-Z][\w.&'-]*\s+(?:v\.?|vs\.?|versus)\s+[A-Z]"),
)


def normalise(text: str) -> str:
    return " ".join(text.translate(_FULL_WIDTH).split())


def has_citation_marker(text: str) -> bool:
    """True if the text carries a source marker, label or any bracketed span."""
    return bool(_MARKER.search(text.translate(_FULL_WIDTH)))


def citation_shapes(text: str) -> set[str]:
    """Citation-shaped strings in the text (case citations, 'A v. B')."""
    t = normalise(text)
    return {m.group(0).strip().lower() for p in _SHAPES for m in p.finditer(t)}


def has_quotes(text: str) -> bool:
    return bool(_QUOTES.search(text))
