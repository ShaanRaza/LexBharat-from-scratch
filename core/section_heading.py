# ruff: noqa: E501
"""Which section is this chunk ABOUT? Read from the chunk's own heading, never from its label (pipeline step 5).

A stored `section_number` label is wrong for about 17% of Union-level Act chunks (lane D, measured 5 Nov 2026), and the
"Section N:" header line the chunker built is wrong the same way, because it is built from the label. The chunk's BODY
still prints the real heading ("**139. Return of income.—**"). This module reads that and nothing else; it is the one
place that does, so search (core/search.py) and any later check agree.

    parse_heading(text, section_type=None) -> (number | None, kind)

kind is "section", "order_rule", "schedule" or "none". number is None when the first thing in the body is not a heading
(a continuation: "( _a_ )", "(1)", a lower-case sentence: the later pieces of a long section, chunk ids ending _d1, _d2),
or when it only looks like one (a footnote item "1. Ins. by Act 21 of 2021", an amendment instruction).

    own_section(payload) -> (number | None, kind, source)

reads the payload's `body_section` / `body_kind` when the collection carries them (lane D's build), else the supplement
chunks' `heading_section` (taken from the Act's own number, with Orders kept apart), else the text. Pure functions, no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# decoration the markdown conversion puts before a heading: "> ", "## ", "**", "_", "[", a footnote digit before a
# bracket ("2[90.") and the word Section.
_DECOR = r"(?:[>#*_\s]|\d{1,2}\s*\[|\[)*"
_NUM = r"(\d{1,3}[A-Z]{0,3}|[IVXL]{1,6})"
_HEAD = re.compile(rf"^{_DECOR}(?:Section\s+)?{_NUM}\s*\.(?=[\s*_\-—–\[(]|$)")
_CHAPTER_PREFIX = re.compile(
    r"^[\s>#*_]*(?:CHAPTER|PART|SCHEDULE|THE\s+[A-Z]+\s+SCHEDULE)\b[^\n]{0,100}?(?=\*\*)",
    re.I,
)
# a numbered line that is really footnote text or an amendment instruction, not a section
_FOOTNOTE = re.compile(
    r"^\s*(?:Subs\.?|Ins\.?|Omitted|Rep\.?|Added|Certain words|The words?|The brackets|Clauses?|Sub-sections?|"
    r"See\b|Cf\.|Came|Words?|Figures?|Entry|Entries|Proviso|Renumbered|Re-numbered|Vide|"
    r"The\s+(?:proviso|explanation|second|first|third|following|entry|expression|figures?|letters?|clause)|"
    r"(?:In|For|After|Before|Insert|Omit)\s+(?:section|sub-section|clause|the\b|sub-clause|rule|paragraph|schedule)|"
    r"Subs\b|Sub\.|Substituted)\b",
    re.I,
)
_ORDER = re.compile(r"\bORDER\s+([IVXLC]+[A-Z]?)\b", re.I)
_RULE = re.compile(r"\brule\s+(\d+[A-Z]?)\b", re.I)
_SCHEDULE_WORD = re.compile(r"^[\s>#*_]*(?:THE\s+)?(?:[A-Z]+\s+)?SCHEDULE\b", re.I)
_TABLE = re.compile(r"\|\s*-{3,}")


def _body(text: str) -> str:
    """The text after the two header lines ("Act: ..." and "Section N: ..." / a chapter line)."""
    parts = text.split("\n", 2)
    return parts[2] if len(parts) == 3 else parts[-1]


def _after_schedule_words(head: str) -> str:
    m = _SCHEDULE_WORD.match(head)
    rest = head[m.end() :] if m else head
    mm = re.search(r"\n\s*", rest)
    return rest[mm.end() :] if mm else rest


def _strip_order_title(head: str) -> str:
    lines = head.split("\n")
    return "\n".join(lines[1:]) if len(lines) > 1 else ""


def parse_heading(text: str, section_type: str | None = None) -> tuple[str | None, str]:
    """The chunk's own heading number and kind, from the body. `(None, "none")` when the body does not open with one."""
    body = _body(text or "").lstrip()
    head = body[:400]
    if section_type == "schedule" or _SCHEDULE_WORD.match(head):
        m = _HEAD.match(_after_schedule_words(head))
        return (
            (f"Schedule Article {m.group(1)}", "schedule") if m else (None, "schedule")
        )
    mo = _ORDER.search(head[:160])
    if mo and re.match(r"^[\s>#*_\[]*(?:THE\s+)?ORDER\b", head, re.I):
        mr = _RULE.search(head[:300])
        o = mo.group(1).upper()
        if mr:
            return f"Order {o} Rule {mr.group(1).upper()}", "order_rule"
        mh = _HEAD.match(_strip_order_title(head))
        return (
            (f"Order {o} Rule {mh.group(1)}", "order_rule")
            if mh
            else (f"Order {o}", "order_rule")
        )
    # a chapter title on the same line as the heading: "## CHAPTER XIV ... **142. Specific legacy..**"
    cp = _CHAPTER_PREFIX.match(head)
    cand = head[cp.end() :] if cp else head
    m = _HEAD.match(cand)
    if not m:
        return None, "none"
    rest = cand[m.end() :].lstrip(" *_[>")
    if _FOOTNOTE.match(rest):
        return None, "none"
    if _TABLE.search(head):  # a table row numbered like a section: a Schedule article
        return f"Schedule Article {m.group(1)}", "schedule"
    return m.group(1).upper(), "section"


def own_section(
    payload: Mapping[str, Any], text: str = ""
) -> tuple[str | None, str, str]:
    """(number, kind, where it was read) for a stored chunk, by preference:
    1. `body_section` / `body_kind`, when the collection carries them (the parse above, done once at build time);
    2. a supplement chunk's `heading_section`, which comes from the Act's own numbering, not a label;
    3. the body of the text, parsed here.
    `(None, "none", ...)` means the chunk opens with no heading (a continuation); the caller then falls back to its label."""
    if "body_section" in payload:
        n = payload.get("body_section")
        return (
            (str(n).upper() if n else None),
            str(payload.get("body_kind") or ("section" if n else "none")),
            "body_section",
        )
    if payload.get("source_kind") == "supplement_indiacode":
        h = str(payload.get("heading_section") or "")
        if h:
            kind = (
                "order_rule"
                if h.startswith("Order")
                else "schedule"
                if h.startswith("Schedule")
                else "section"
            )
            return (h.upper() if kind == "section" else h), kind, "heading_section"
    n, kind = parse_heading(
        text or str(payload.get("text") or ""), payload.get("section_type")
    )
    return n, kind, "text"
