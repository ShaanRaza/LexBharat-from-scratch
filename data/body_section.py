"""Which section is this chunk ABOUT? Read from the chunk's own first heading line (A186).

Plain words. A kanoon_v1 Act chunk carries a stored label (`section_number`) and a header line
"Section N: ..." built from it. Where the label is wrong (CPC Order-rules under "Section 11", the
Income-tax return of income under "3", RBI s.43 under "42"), the header is wrong the same way, so a
lookup on either cannot find the chunk. The chunk's BODY still prints the real heading, for example
"**139. Return of income.—**". This module reads that and nothing else.

    parse_body_section(text, section_type=None) -> (body_section | None, body_kind)

body_kind is "section", "order_rule", "schedule" or "none". None means the first thing in the body is
not a heading (a continuation: "( _a_ )", "(1)", a lower-case sentence), which is the usual case for
the second and later pieces of a long section (chunk ids ending _d1, _d2, _p1, _p2).

What is NOT a section heading, and is refused: a footnote item ("1. Ins. by Act 21 of 2021") and a
heading that follows more than a chapter title.
Pure function, no I/O.
"""

from __future__ import annotations

import re

# decoration the markdown conversion puts before a heading: "> ", "## ", "**", "_", "[", a footnote
# digit before a bracket ("2[90.") and the word Section.
_DECOR = r"(?:[>#*_\s]|\d{1,2}\s*\[|\[)*"
_NUM = r"(\d{1,3}[A-Z]{0,3}|[IVXL]{1,6})"
_HEAD = re.compile(rf"^{_DECOR}(?:Section\s+)?{_NUM}\s*\.(?=[\s*_\-—–\[(]|$)")
_CHAPTER_PREFIX = re.compile(
    r"^[\s>#*_]*(?:CHAPTER|PART|SCHEDULE|THE\s+[A-Z]+\s+SCHEDULE)\b[^\n]{0,100}?(?=\*\*)",
    re.I,
)
# a numbered line that is really footnote text or a note, not a section
_FOOTNOTE = re.compile(
    r"^\s*(?:Subs\.?|Ins\.?|Omitted|Rep\.?|Added|Certain words|The words?|The brackets|Clauses?|Sub-sections?|"
    r"See\b|Cf\.|Came|Words?|Figures?|Entry|Entries|Proviso|Renumbered|Re-numbered|Vide|"
    r"The\s+(?:proviso|explanation|second|first|third|following|entry|expression|figures?|letters?|clause)|"
    r"(?:In|For|After|Before|Insert|Omit)\s+(?:section|sub-section|clause|the\b|sub-clause|rule|paragraph|schedule)|"
    r"Subs\b|Sub\.|Substituted|Section\s+\d+)\b",
    re.I,
)
_ORDER = re.compile(r"\bORDER\s+([IVXLC]+[A-Z]?)\b", re.I)
_RULE = re.compile(r"\brule\s+(\d+[A-Z]?)\b", re.I)
_SCHEDULE_WORD = re.compile(r"^[\s>#*_]*(?:THE\s+)?(?:[A-Z]+\s+)?SCHEDULE\b", re.I)
_TABLE = re.compile(r"\|\s*-{3,}")


def _body(text: str) -> str:
    """The text after the two header lines ("Act: ..." and "Section N: ..." / chapter line)."""
    parts = text.split("\n", 2)
    return parts[2] if len(parts) == 3 else parts[-1]


def parse_body_section(
    text: str, section_type: str | None = None
) -> tuple[str | None, str]:
    body = _body(text).lstrip()
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
    # a leading chapter title on the same line as the heading: "## CHAPTER XIV ... **142. Specific legacy..**"
    head = _skip_title_lines(head)
    cp = _CHAPTER_PREFIX.match(head)
    cand = head[cp.end() :] if cp else head
    m = _HEAD.match(cand)
    if not m:
        return None, "none"
    rest = cand[m.end() :].lstrip(" *_[>")
    if _FOOTNOTE.match(rest):
        return None, "none"
    if _TABLE.search(
        head
    ):  # a table row numbered like a section: a Schedule article, not a section
        return f"Schedule Article {m.group(1)}", "schedule"
    return m.group(1).upper(), "section"


def _after_schedule_words(head: str) -> str:
    m = _SCHEDULE_WORD.match(head)
    rest = head[m.end() :] if m else head
    mm = re.search(r"\n\s*", rest)
    return rest[mm.end() :] if mm else rest


def _strip_order_title(head: str) -> str:
    lines = head.split("\n")
    return "\n".join(lines[1:]) if len(lines) > 1 else ""


def _skip_title_lines(head: str) -> str:
    """Drop the chapter / part title block that can precede a heading, up to four lines:
    markdown headings ("## CHAPTER XI"), CHAPTER / PART lines and all-capitals title lines."""
    lines = head.split("\n")
    i = 0
    while i < len(lines) and i < 8:
        ln = lines[i].strip()
        if not ln:
            i += 1
            continue
        letters = [c for c in ln if c.isalpha()]
        caps = bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.8
        if _HEAD.match(ln) and not caps:
            break
        if re.search(r"\*\*\s*(?:Section\s+)?\d{1,3}[A-Z]{0,3}\s*\.", ln):
            break  # the heading is on this very line, after an inline chapter title
        if (
            ln.startswith("#")
            or re.match(r"^(?:CHAPTER|PART)\b", ln, re.I)
            or (caps and not _HEAD.match(ln))
        ):
            i += 1
            continue
        break
    return "\n".join(lines[i:])


# every bold heading anywhere in the chunk: "**9A. Anti-dumping duty**", "## **39. Punishment ...**",
# "> 7 **—** [ **43. Publication ...**", "**2[19A. Return of plaint.—**"
_BOLD_HEAD = re.compile(
    r"\*\*\s*(?:\d{1,2}\s*\[\s*)?(\d{1,3}[A-Z]{0,3})\s*\.\s*(?=[A-Z\[*_])"
)


def all_headings(text: str, first: str | None = None) -> list[str]:
    """Section numbers of every bold heading in the chunk body, in order, plus `first` (the heading
    parse_body_section found at the very start). Catches a chunk that starts in the middle of one section and
    contains the heading of the next, which a first-heading rule cannot see. Footnote items ("**12.** Subs.
    by Act") are refused as in parse_body_section."""
    body = _body(text)
    out: list[str] = [first] if first else []
    for m in _BOLD_HEAD.finditer(body):
        rest = body[m.end() : m.end() + 60].lstrip(" *_[>")
        if _FOOTNOTE.match(rest):
            continue
        n = m.group(1).upper()
        if n not in out:
            out.append(n)
    return out
