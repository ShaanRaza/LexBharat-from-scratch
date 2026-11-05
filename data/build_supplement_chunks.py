#!/usr/bin/env python3
"""Chunk India Code PDFs of central Acts into section records. DRY RUN: writes a manifest and a
local JSONL file; it never talks to Qdrant, Voyage or any network service.

Plain words. `kanoon_v1` is missing the Constitution and its copies elsewhere are ~12% fragments;
several other central Acts are held incompletely. The owner has India Code text PDFs. This script
turns each PDF into one record per section (per article for the Constitution, per rule for the
CPC's Orders, per article for the Stamp Act's Schedule I) so the records can be reviewed BEFORE
anything is embedded or served. Nothing here is served.

What a record is (field names copied from a central-Act point in `kanoon_v1`):
  chunk_id / act_id    IND_SUPP_*  -- a prefix the dataset never uses, so a supplement record
                       can never be mistaken for a Vaquill dataset record.
  source_kind          "supplement_indiacode"; source_url is the India Code page for the Act.
  as_of / as_of_basis  per Act, the date printed in that PDF ("printed"), or the download date
                       from SOURCES.md ("download date") when the PDF prints none.
  act_status           "not_checked" and section_status "not_checked" -- never "in_force".
                       Omitted / repealed sections are stored as such ("omitted" / "repealed").
  amendment_notes      the footnotes ("Subs. by ...", "Ins. by ...") that belong to the section.
  state_amendment_text state amendments printed in the PDF under the central text (Stamp Act, CPC);
                       kept apart so state text is never read as the central section.

How the three kinds of text are told apart (layout, not guesswork; counts are in the manifest):
  page furniture   `pdftotext -layout` page breaks (\\f); lone page numbers; the diagonal
                   "India Code" watermark shows up as the fragments e / od / aC / di / In;
                   the Constitution's running header "N  THE CONSTITUTION OF INDIA / (Part ..)".
  footnotes        at the foot of a page, the first line at the left margin that starts
                   "<n>. Subs. by / Ins. by / Added / Omitted / The words / See ..." begins the
                   footnote block; every later line on that page is footnote text.
  body             everything above it. A section is only recognised if its number is printed in
                   the Act's own "Arrangement of sections" (so a numbered list item inside a
                   section is not mistaken for a new section) and comes after the previous one.

    .venv/bin/python data/build_supplement_chunks.py --pdf-dir <copy of the pdfs> --out-dir <dir>
Reads PDFs only (copy them first; this script never edits the originals).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

PREFIX = "IND_SUPP_"
SOURCE_KIND = "supplement_indiacode"
STATUS = (
    "not_checked"  # never "in_force": nobody has determined it (CLAUDE.md section 6)
)
SPLIT_LIMIT = 1711  # p95 of kanoon_v1 central-Act point text, in characters (Measured 5 Nov 2026, n=74,484)
SHORT = 30  # a section body shorter than this many characters is listed in the manifest
DOWNLOAD_DATE = (
    "2026-10-24"  # SOURCES.md: "found 2026-10-24"; the Constitution 2026-10-25
)

# slug, file, title, act number, year, mode
ACTS = [
    (
        "constitution",
        "constitution-of-india.pdf",
        "The Constitution of India",
        "",
        "1950",
        "constitution",
    ),
    (
        "contract1872",
        "contract-act-1872.pdf",
        "The Indian Contract Act, 1872",
        "9",
        "1872",
        "sections",
    ),
    (
        "cpc1908",
        "cpc-1908.pdf",
        "The Code of Civil Procedure, 1908",
        "5",
        "1908",
        "cpc",
    ),
    (
        "hma1955",
        "hindu-marriage-act-1955.pdf",
        "The Hindu Marriage Act, 1955",
        "25",
        "1955",
        "sections",
    ),
    (
        "limitation1963",
        "limitation-act-1963.pdf",
        "The Limitation Act, 1963",
        "36",
        "1963",
        "sections",
    ),
    (
        "nia1881",
        "ni-act-1881.pdf",
        "The Negotiable Instruments Act, 1881",
        "26",
        "1881",
        "sections",
    ),
    (
        "pca1988",
        "prevention-of-corruption-act-1988.pdf",
        "The Prevention of Corruption Act, 1988",
        "49",
        "1988",
        "sections",
    ),
    (
        "sra1963",
        "specific-relief-act-1963.pdf",
        "The Specific Relief Act, 1963",
        "47",
        "1963",
        "sections",
    ),
    (
        "stamp1899",
        "stamp-act-1899.pdf",
        "The Indian Stamp Act, 1899",
        "2",
        "1899",
        "stamp",
    ),
]

STATES = (
    "Andhra Pradesh|Arunachal Pradesh|Assam|Bihar|Chhattisgarh|Goa|Gujarat|Haryana|"
    "Himachal Pradesh|Jharkhand|Karnataka|Kerala|Madhya Pradesh|Maharashtra|Manipur|Meghalaya|"
    "Mizoram|Nagaland|Odisha|Orissa|Punjab|Rajasthan|Sikkim|Tamil Nadu|Telangana|Tripura|"
    "Uttar Pradesh|Uttarakhand|West Bengal|Delhi|Jammu and Kashmir|Pondicherry|Puducherry|"
    "Chandigarh|Madras|Bombay|Calcutta|Allahabad|Patna|Andaman and Nicobar Islands|"
    "Lakshadweep|Dadra and Nagar Haveli|Daman and Diu"
)
STATE_LINE = re.compile(rf"^\s*(?:{STATES})(?:\s*\(.*\))?\s*$")
STATE_HEAD = re.compile(r"^\s*(?:STATE|HIGH COURT)S?'?\s+AMENDMENTS?\b.*$", re.I)

WM_LINE = re.compile(r"^\s*(?:e|od|aC|di|In)\s*$")
WM_TAIL = re.compile(r"\s{3,}(?:e|od|aC|di|In)(?=\s{3,}|\s*$)")
PAGE_NO = re.compile(r"^\s{15,}\d{1,3}\s*$")
RUN_HEAD = re.compile(
    r"^\s*(?:\d{1,3}\s+)?THE CONSTITUTION OF INDIA(?:\s+\d{1,3})?\s*$"
)
RUN_PART = re.compile(r"^\s*\((?:Part|Schedule|Appendix)[^)]*\)\s*$")
# a footnote line: left margin, "<n>." and an amendment-style first word
FOOT = re.compile(
    r"^ {0,1}(\d{1,3})\.?\s+(?:Subs\.?|Subs by|Ins\.?|Added|Omitted|Rep\.|The words?|The brackets|"
    r"Certain words|See\b|Cf\.|As to|Cls?\.|Clauses?|Sub-sections?|Sections?|Ss?\.|Arts?\.|"
    r"Articles?|Entries|Entry|Provisions?|Paras?\.?|Renumbered|Re-numbered|Vide|Now|Came|"
    r"The (?:Act|Code|Repealing|Marriage|Hindu|Child|Lokpal|Prevention|Specific|Explanation|"
    r"proviso|second|Indian|provisions|word)|This (?:rule|section|article|Act))"
)
FOOT_ITEM = re.compile(r"^ {0,1}(\d{1,3})\.\s")
LABEL = re.compile(
    r"^\s{0,12}(?:\d{1,3}(?=[\s\[])\s*)?[*\[]{0,2}\s*(\d{1,3}(?:-?[A-Z]{1,3})?)\.\s*(?=[A-Za-z“\"‘\[(*]|\d{1,2}\[)"
)
REPEALED = re.compile(r"^\W{0,3}(?:\[\s*Repeal|Rep\.|Repealed)", re.I)
OMITTED = re.compile(r"^\W{0,3}(?:Omitted|\*\s*\*\s*\*|\[?\s*Omitted)", re.I)
ASON = re.compile(
    r"\[\s*As on (?:the )?(\d{1,2})(?:st|nd|rd|th)?[ ,]+([A-Za-z]+),? (\d{4})\s*\]"
)
MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "january february march april may june july august september october november december".split()
    )
}


@dataclass
class Rec:
    label: str  # the Act's own number: "11", "21A", "Preamble", "FIRST SCHEDULE", "Appendix I"
    kind: str  # section | article | rule | schedule | appendix | preamble | schedule_article
    heading: str = ""
    lines: list[str] = field(default_factory=list)
    state_lines: list[str] = field(default_factory=list)
    pages: set[int] = field(default_factory=set)
    order: str = ""  # CPC: the Order a rule belongs to
    part: str = ""
    part_title: str = ""
    chapter: str = ""
    chapter_title: str = ""
    notes: list[str] = field(default_factory=list)
    stub: bool = False
    in_state: bool = False
    forced_status: str = ""
    state_block: str = ""
    variant: int = 1  # 2 = the same Order number printed a second time


# ---------------------------------------------------------------------------------------------
# 1. Pages: strip furniture, split off footnotes
# ---------------------------------------------------------------------------------------------
def pdf_text(pdf: Path) -> str:
    return subprocess.run(  # noqa: S603, S607  (fixed argv, no shell; pdftotext is a local tool)
        ["pdftotext", "-layout", str(pdf), "-"],  # noqa: S607
        capture_output=True,
        check=True,
        text=True,
    ).stdout


def clean_line(line: str) -> str:
    return WM_TAIL.sub("", line).rstrip()


def split_page(
    raw: str, constitution: bool
) -> tuple[list[str], dict[int, str], Counter]:
    """(body lines, {footnote number: text}, counts of what was dropped)."""
    drop: Counter = Counter()
    lines: list[str] = []
    for ln in raw.split("\n"):
        if WM_LINE.match(ln):
            drop["watermark_lines"] += 1
            continue
        c = clean_line(ln)
        if PAGE_NO.match(c):
            drop["page_numbers"] += 1
            continue
        lines.append(c)
    if (
        constitution
    ):  # running head: "30  THE CONSTITUTION OF INDIA" + "(Part V.-The Union)"
        for i, ln in enumerate(lines[:6]):
            if RUN_HEAD.match(ln):
                del lines[i]
                drop["running_headers"] += 1
                break
        for i, ln in enumerate(lines[:6]):
            if RUN_PART.match(ln):
                del lines[i]
                drop["running_headers"] += 1
                break
    cut = next((i for i, ln in enumerate(lines) if FOOT.match(ln)), len(lines))
    notes: dict[int, str] = {}
    cur = None
    for ln in lines[cut:]:
        m = FOOT_ITEM.match(ln)
        if m:
            cur = int(m.group(1))
            notes[cur] = ln.strip()
        elif cur is not None and ln.strip():
            notes[cur] += " " + ln.strip()
    drop["footnotes"] += len(notes)
    return lines[:cut], notes, drop


# ---------------------------------------------------------------------------------------------
# 2. The Act's own table of contents
# ---------------------------------------------------------------------------------------------
def toc_labels(lines: list[str]) -> list[str]:
    seen: list[str] = []
    # skip the "List of amending Acts" that precedes the arrangement (its "47. The ... Act, 1983"
    # lines would otherwise be taken for section 47)
    start = next(
        (
            i
            for i, ln in enumerate(lines)
            if re.match(r"^\s*(?:ARRANGEMENT|ARRENGMENT|SECTIONS|ARTICLES)\b", ln)
        ),
        0,
    )
    for ln in lines[start:]:
        m = LABEL.match(ln)
        lab = m.group(1).replace("-", "") if m else ""
        if m and lab not in seen:
            seen.append(lab)
    return seen


def toc_lines(lines: list[str]) -> dict[str, str]:
    """label -> the printed Arrangement line (used only to spot '[Repealed.]' entries)."""
    out: dict[str, str] = {}
    start = next(
        (
            i
            for i, ln in enumerate(lines)
            if re.match(r"^\s*(?:ARRANGEMENT|ARRENGMENT|SECTIONS|ARTICLES)\b", ln)
        ),
        0,
    )
    for ln in lines[start:]:
        m = LABEL.match(ln)
        if m:
            out.setdefault(m.group(1).replace("-", ""), ln.strip())
    return out


# ---------------------------------------------------------------------------------------------
# 3. Segmentation
# ---------------------------------------------------------------------------------------------
def segment(
    stream: list[tuple[int, str]],
    toc: list[str],
    kind: str,
    order: str = "",
    chunk_state: bool = True,
) -> tuple[list[Rec], Counter]:
    """Split a stream of (page, line) into one Rec per section. A line starts a section only if
    its number is in `toc`, comes later in `toc` than the previous section, and (inside a
    "STATE AMENDMENTS" block) -- the same rule, so a state-inserted "3A" that the central Act does
    not print is never taken for a central section."""
    out: list[Rec] = []
    stats: Counter = Counter()
    idx = {lab: i for i, lab in enumerate(toc)}
    prev = -1
    in_state = False
    part = part_title = chap = chap_title = ""
    pend = None  # "PART"/"CHAPTER" waiting for its title line
    for k, (pg, ln) in enumerate(stream):
        s = ln.strip()
        mp = (
            re.match(r"^(PART|CHAPTER)\s+([IVXLC]+[A-Z]?|\d+)\s*\.?$", s)
            if len(ln) - len(ln.lstrip()) > 12
            else None
        )
        if mp:
            pend = mp.group(1)
            if pend == "PART":
                part, part_title = mp.group(2), ""
            else:
                chap, chap_title = mp.group(2), ""
            continue
        if pend and s and not LABEL.match(ln):
            if pend == "PART" and not part_title:
                part_title = s
            elif pend == "CHAPTER" and not chap_title:
                chap_title = s
            pend = None
        if chunk_state and (STATE_HEAD.match(ln) or STATE_LINE.match(ln)) and out:
            in_state = True
            stats["state_amendment_blocks"] += 1 if STATE_HEAD.match(ln) else 0
            out[-1].state_lines.append(s)
            continue
        m = LABEL.match(ln)
        if m:
            lab = m.group(1).replace("-", "")
            if (
                lab not in idx
                and len(lab) >= 3
                and lab[1:] in idx
                and idx[lab[1:]] == prev + 1
            ):
                lab = lab[1:]  # a footnote marker glued to the number ("860." for 60)
                stats["label_repaired_from_glued_footnote_marker"] += 1
            # the heading is finished by an em dash on this line or within the next two lines
            ahead = " ".join(x for _, x in stream[k : k + 3])
            shaped = bool(
                re.search(r"[—–]|--|\[\s*Repeal|Rep\.|Omitted|\*\*\*", ahead[:260])
            )
            if (
                lab in idx
                and idx[lab] > prev
                and idx[lab] <= prev + 45
                and (shaped or idx[lab] == prev + 1)
            ):
                prev = idx[lab]
                in_state = False
                rec = Rec(
                    lab,
                    kind,
                    order=order,
                    part=part,
                    part_title=part_title,
                    chapter=chap,
                    chapter_title=chap_title,
                )
                rec.pages.add(pg)
                rec.lines.append(
                    re.sub(
                        r"^.*?(?=" + re.escape(m.group(1)) + r"\.)", "", s, count=1
                    ).strip()
                )
                out.append(rec)
                continue
            if lab in {r.label for r in out}:
                stats["repeat_label_lines_rejected"] += 1
        if not out:
            stats["lines_before_first_section"] += 1
            continue
        rec = out[-1]
        rec.pages.add(pg)
        (rec.state_lines if in_state else rec.lines).append(s)
    return out, stats


def stubs(
    recs: list[Rec],
    toc: list[str],
    tl: dict[str, str],
    stream,
    stats: Counter,
    kind: str = "section",
) -> list[Rec]:
    """Arrangement entries that say [Repealed.]/[Omitted.] but have no heading in the body (the
    body prints only asterisks and a footnote). They are kept as stored-as-repealed stubs, never
    dropped; the footnote is attached through the page match, and `stub_from_toc` is recorded."""
    have = {r.label for r in recs if r.kind == kind}
    out = []
    for lab in toc:
        if lab in have:
            continue
        line = tl.get(lab, "")
        if re.search(r"Repeal|Omitted|\bRep\b", line, re.I):
            r = Rec(lab, kind)
            r.lines = [line.strip()]
            r.stub = True
            out.append(r)
            stats["stubs_from_arrangement"] += 1
    return out


def split_heading(first: str) -> tuple[str, str]:
    """('Short title', 'This Act may be called ...') from '1. Short title.-This Act ...'."""
    m = re.match(
        r"^\d{1,3}[A-Z]{0,3}\.\s*(.*?)(?:\.\s*[—–]|\s*[—–]\s*|\.?\s*--)(.*)$", first
    )
    if m:
        return m.group(1).strip(" .["), m.group(2).strip()
    return first.split(".", 1)[-1].strip()[:120], ""


def status_of(rec: Rec) -> str:
    body = " ".join(rec.lines)
    after = re.sub(r"^\d{1,3}[A-Z]{0,3}\.\s*", "", body)
    head, rest = split_heading(rec.lines[0]) if rec.lines else ("", "")
    probe = (rest or after)[:140]
    whole = after[:200]
    if (
        REPEALED.match(after)
        or REPEALED.match(probe)
        or re.search(r"\]\s*Rep\. ?by", whole[:160])
    ):
        return "repealed"
    if len(body) < 400 and re.search(r"\bRep\.\s*by|\[\s*Repealed", whole):
        return "repealed"
    if len(body) < 300 and re.search(r"\[\s*Omitted|\bOmitted by\b", whole):
        return "omitted"
    if OMITTED.match(after) or OMITTED.match(probe) or re.match(r"^Omitted\b", head):
        return "omitted"
    if (
        len(re.sub(r"[\s*]", "", rest)) == 0
        and re.search(r"\*\s*\*\s*\*", whole)
        and len(body) < 120
    ):
        return "omitted"
    return STATUS


# ---------------------------------------------------------------------------------------------
# 4. One Act
# ---------------------------------------------------------------------------------------------
def build_act(pdf: Path, spec: tuple, urls: dict[str, str]) -> dict:
    slug, fname, title, actno, year, mode = spec
    raw = pdf_text(pdf)
    pages_raw = raw.split("\f")
    drop: Counter = Counter()
    stream: list[tuple[int, str]] = []
    page_notes: dict[int, dict[int, str]] = {}
    for pno, pr in enumerate(pages_raw):
        body, notes, d = split_page(pr, mode == "constitution")
        drop.update(d)
        page_notes[pno] = notes
        stream.extend((pno, ln) for ln in body)
    # The Statement of Objects and Reasons printed after the Act is not law: cut it, count it.
    sor = next(
        (
            i
            for i, (_, ln) in enumerate(stream)
            if re.match(r"^\s{10,}STATEMENT OF OBJECTS AND REASONS\s*$", ln)
        ),
        None,
    )
    sor_chars = 0
    if sor is not None:
        sor_chars = sum(len(ln) for _, ln in stream[sor:])
        stream = stream[:sor]
    head_text = "\n".join(pages_raw[:3])
    m = ASON.search(head_text)
    if m and m.group(2).lower() in MONTHS:
        as_of = f"{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
        basis = "printed"
    else:
        as_of, basis = (
            (DOWNLOAD_DATE if slug != "constitution" else "2026-10-25"),
            "download date",
        )

    recs, stats = parse(mode, stream)
    if sor_chars:
        stats["statement_of_objects_chars_cut"] = sor_chars
    if "_stamp_sched_page" in stats:
        recs += stamp_schedule_nl(pdf, stats.pop("_stamp_sched_page"), stats)
    # footnotes -> sections: a footnote belongs to a section if its number is a marker in the text
    unattached = Counter()
    for pno, notes in page_notes.items():
        for num, txt in notes.items():
            owners = [r for r in recs if pno in r.pages and marker(r, num)]
            if owners:
                owners[0].notes.append(txt)
            else:
                unattached["footnotes_not_attached"] += 1
    stats.update(unattached)

    out = []
    for i, r in enumerate(recs):
        heading, rest = (
            split_heading(r.lines[0])
            if r.kind in ("section", "article", "rule")
            else (r.heading or r.label, "")
        )
        body = (
            "\n".join([rest] + r.lines[1:]).strip()
            if rest
            else "\n".join(r.lines[1:]).strip()
        )
        if r.kind in ("preamble", "schedule", "appendix", "schedule_article"):
            body = "\n".join(r.lines).strip()
        if r.kind in ("section", "article", "rule") and status_of(r) != STATUS:
            # a repealed / omitted entry keeps its whole printed line ("Rep. by Act ..."): that
            # line IS its content, and it is stored as repealed/omitted, never dropped
            body = re.sub(r"^\d{1,3}[A-Z]{0,3}\.\s*", "", " ".join(r.lines)).strip()
            heading = status_of(r)
        body = clean_body(body)
        out.append((r, heading, body))
    return {
        "spec": spec,
        "as_of": as_of,
        "as_of_basis": basis,
        "source_url": urls.get(fname, ""),
        "pages": len(pages_raw) - 1,
        "recs": out,
        "toc": stats.pop("_toc", None),
        "stats": dict(stats),
        "dropped": dict(drop),
    }


def marker(rec: Rec, num: int) -> bool:
    text = " ".join(rec.lines)
    return bool(
        re.search(
            rf"(?<![\d.])\b{num}\s*(?:\[|\*\*\*)|(?<=[A-Za-z,;:)”’\"]){num}\b(?!\d)",
            text,
        )
    )


def clean_body(t: str) -> str:
    t = re.sub(r"(?<![\d.])\b(\d{1,3})(?=\s*\[)", "", t)  # footnote marker before "["
    t = re.sub(r"(?<![\d.])\b\d{1,3}(?=\*\*\*)", "", t)  # marker before ***
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def parse(mode: str, stream: list[tuple[int, str]]) -> tuple[list[Rec], Counter]:
    lines = [ln for _, ln in stream]
    stats: Counter = Counter()

    def first(pat: str, start: int = 0) -> int | None:
        rx = re.compile(pat)
        for i in range(start, len(lines)):
            if rx.match(lines[i]):
                return i
        return None

    if mode in ("sections", "stamp"):
        body0 = first(r"^\s{1,9}1\.\s+Short title.*[—–-]") or 0
        toc = toc_labels(lines[:body0])
        if mode == "stamp":
            sched = first(r"^\s*SCHEDULE\s+(?:1|I)\s*$", body0)
        else:  # a closing "THE SCHEDULE" (Limitation Act: the periods of limitation)
            sched = first(r"^\s{8,}(?:THE )?SCHEDULE\s*$", body0)
        end = sched if sched else len(stream)
        recs, st = segment(stream[body0:end], toc, "section")
        stats.update(st)
        stats["_toc"] = toc  # type: ignore[assignment]
        recs += stubs(recs, toc, toc_lines(lines[:body0]), stream, stats)
        if mode == "stamp" and sched:
            stats["_stamp_sched_page"] = stream[sched][0]
        elif sched:
            recs += schedule_rows(stream[sched:], stats)
        return recs, stats

    if mode == "constitution":
        body0 = (
            first(r"^\s{1,9}1\.\s+Name and territory of the Union", 1000)
            or first(r"^\s{1,9}1\.\s+Name and territory.*[—–]")
            or 0
        )
        # TOC: from the 'ARRANGEMENT OF ARTICLES' region before the body
        toc_start = first(r"^\s*(?:ARTICLES|ARRANGEMENT)") or 0
        toc = toc_labels(lines[toc_start:body0])
        sch0 = first(r"^\s*\[?\s*FIRST SCHEDULE\s*$", body0)
        recs, st = segment(
            stream[body0 : sch0 or len(stream)], toc, "article", chunk_state=False
        )
        stats.update(st)
        stats["_toc"] = toc  # type: ignore[assignment]
        recs += stubs(
            recs, toc, toc_lines(lines[toc_start:body0]), stream, stats, "article"
        )
        # preamble
        pi = first(r"^\s*WE,? THE PEOPLE OF INDIA")
        if pi is not None:
            pj = next(
                (
                    j
                    for j in range(pi, len(lines))
                    if re.search(
                        r"THIS CONSTITUTION\.?\s*$|THIS CONSTITUTION\W*$", lines[j]
                    )
                ),
                pi + 8,
            )
            r = Rec(
                "Preamble",
                "preamble",
                "Preamble",
                lines[pi : pj + 1],
                pages={stream[pi][0]},
            )
            recs.insert(0, r)
        if sch0 is not None:
            recs += schedules(
                stream,
                sch0,
                r"^\s*\[?\s*(?:THE )?(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH) SCHEDULE\b",
                r"^\s*APPENDIX (I{1,3}V?|IV|V)\b\.?",
            )
        return recs, stats

    if mode == "cpc":
        first_sched_toc = first(r"^\s*THE FIRST SCHEDULE\s*$")
        body0 = first(r"^\s{1,9}1\.\s+Short title.*[—–-]") or 0
        sched = first(r"^\s*THE FIRST SCHEDULE\s*$", body0)
        toc_sec = toc_labels(lines[:first_sched_toc])
        recs, st = segment(stream[body0:sched], toc_sec, "section")
        stats.update(st)
        stats["_toc"] = toc_sec  # type: ignore[assignment]
        recs += stubs(recs, toc_sec, toc_lines(lines[:first_sched_toc]), stream, stats)
        # Orders: the TOC lists each Order's rules after its "ORDER X" heading
        # Seen in the PDF: "ORDER XX", "[ORDER XXA", "*[ORDER XV-A aC" (watermark), "InORDER XLIII" (watermark
        # glued on). A quote mark before ORDER means a STATE-inserted Order, which is not matched.
        order_rx = re.compile(
            r"^\s*(?:In\s*)?[*\[]{0,2}\s*ORDER\s+([IVXL]+)(?:[-\s]?([A-Z]))?\]?(?:\s+(?:e|od|aC|di|In))?\s*$"
        )

        def order_no(m):
            return m.group(1) + (m.group(2) or "")

        toc_orders: dict[str, list[str]] = {}
        cur = None
        for ln in lines[first_sched_toc:sched]:
            mo = order_rx.match(ln)
            if mo:
                cur = order_no(mo)
                toc_orders.setdefault(cur, [])
                continue
            m = LABEL.match(ln)
            if cur and m and m.group(1) not in toc_orders[cur]:
                toc_orders[cur].append(m.group(1))
        app0 = first(r"^\s*APPENDIX\s+[A-H]\s*$", sched + 1)
        orders_stream = stream[sched + 1 : app0 or len(stream)]
        starts = [i for i, (_, ln) in enumerate(orders_stream) if order_rx.match(ln)]
        seen_orders: Counter = Counter()
        for a, b in zip(starts, starts[1:] + [len(orders_stream)]):
            ordno = order_no(order_rx.match(orders_stream[a][1]))
            seen_orders[ordno] += 1
            variant = seen_orders[
                ordno
            ]  # Order XI is printed twice (the second: commercial courts)
            toc_o = toc_orders.get(ordno, []) if variant == 1 else []
            if not toc_o:  # an Order the printed arrangement omits (Order XV-A): accept 1, 1A, 2 ... in order
                toc_o = [f"{i}{x}" for i in range(1, 90) for x in ("", "A", "B", "C")]
                stats["orders_not_in_arrangement"] += 1
            rs, st2 = segment(orders_stream[a + 1 : b], toc_o, "rule", order=ordno)
            for r in rs:
                r.order = ordno
                r.variant = variant
            if variant > 1:
                stats["orders_printed_more_than_once"] += 1
            recs += rs
            stats["orders_found"] += 1
            stats.update({f"orders:{k}": v for k, v in st2.items()})
        stats["orders_in_toc"] = len(toc_orders)
        if app0 is not None:
            recs += schedules(
                stream, app0, r"^\s*APPENDIX\s+([A-H])\s*$", None, kind="appendix"
            )
        return recs, stats

    raise ValueError(mode)


def schedules(stream, start, rx_s, rx_app, kind="schedule"):
    """One record per Schedule (and per Appendix): the text up to the next heading."""
    rxs = re.compile(rx_s)
    rxa = re.compile(rx_app) if rx_app else None
    heads = []
    in_app = False
    for i in range(start, len(stream)):
        ln = stream[i][1]
        m = rxs.match(ln)
        if rxa and rxa.match(ln) and len(ln) - len(ln.lstrip()) > 8:
            in_app = True  # an Appendix quotes amending text that repeats "FIRST SCHEDULE" etc.
        if m and not in_app and len(ln) - len(ln.lstrip()) > 8:
            heads.append(
                (
                    i,
                    f"{'Appendix' if kind == 'appendix' else m.group(1).title() + ' Schedule'}"
                    + (f" {m.group(1)}" if kind == "appendix" else ""),
                    kind,
                )
            )
        elif rxa and rxa.match(ln) and len(ln) - len(ln.lstrip()) > 8:
            heads.append((i, "Appendix " + rxa.match(ln).group(1), "appendix"))
    recs = []
    for (i, label, k), nxt in zip(heads, [h[0] for h in heads[1:]] + [len(stream)]):
        r = Rec(label, k, label)
        r.lines = [x for _, x in stream[i:nxt]]
        r.pages = {p for p, _ in stream[i:nxt]}
        recs.append(r)
    return recs


def schedule_rows(stream, stats):
    """A closing Schedule laid out as numbered rows ("21. For compensation ..."): one record per
    row, numbers rising by at most 3, so a numbered line inside a row's own text is not a new row.
    The table is three columns; the row text keeps pdftotext's reading order."""
    row = re.compile(r"^\s{0,6}(\d{1,3})\.\s+[A-Z]")
    out: list[Rec] = []
    last = 0
    head = Rec("Schedule (heading)", "schedule", "Schedule")
    cur = head
    for pg, ln in stream:
        m = row.match(ln)
        if m and last < int(m.group(1)) <= last + 3:
            last = int(m.group(1))
            cur = Rec(m.group(1), "schedule_article", f"Schedule, Article {m.group(1)}")
            out.append(cur)
        cur.pages.add(pg)
        cur.lines.append(ln.strip())
    stats["schedule_rows"] = len(out)
    return ([head] if any(x.strip() for x in head.lines) else []) + out


STATE_NAME_ALONE = re.compile(rf"^\s*({STATES}|Uttaranchal)\s*[.\-–—]*\s*$")


def stamp_tail_blocks(tail: list[tuple[int, str]], stats) -> list[Rec]:
    """Everything from "SCHEDULE 1-A" on is STATE material (1-A is the Orissa schedule; the rest are
    state amendments), cut at each line that is only a state's name. Evidence that the cut is
    reliable: each block's own "[Vide <State> Act ...]" citations name the state in its heading
    (13 of 14 blocks agree; the last also holds one Uttarakhand citation). The central
    "SCHEDULE II ... [Enactments repealed.]" line at the very end is split off as its own record."""
    lines = [(p, ln) for p, ln in tail]
    sch2 = next(
        (k for k, (_, ln) in enumerate(lines) if re.match(r"^\s*SCHEDULE II\b", ln)),
        len(lines),
    )
    cuts = (
        [0]
        + [
            k
            for k, (_, ln) in enumerate(lines[:sch2])
            if k > 0 and STATE_NAME_ALONE.match(ln)
        ]
        + [sch2]
    )
    out: list[Rec] = []
    head = " ".join(ln for _, ln in lines[:6])
    first_state = re.search(r"\(([A-Z]+(?: [A-Z]+)?) AMENDMENT\)", head)
    for n, (a, b) in enumerate(zip(cuts, cuts[1:])):
        if n == 0:
            state = first_state.group(1).title() if first_state else "unattributed"
        else:
            state = STATE_NAME_ALONE.match(lines[a][1]).group(1).strip()
        r = Rec(
            f"State block {n + 1}: {state}",
            "schedule",
            f"{state} (Schedule 1-A and later state amendments)",
        )
        r.lines = [ln.strip() for _, ln in lines[a:b]]
        r.pages = {p for p, _ in lines[a:b]}
        r.state_block = state
        out.append(r)
    if sch2 < len(lines):
        r = Rec("Schedule II", "schedule", "Schedule II")
        r.lines = [ln.strip() for _, ln in lines[sch2:]]
        r.pages = {p for p, _ in lines[sch2:]}
        r.forced_status = "repealed"
        out.append(r)
    stats["stamp_state_blocks"] = len(cuts) - 1
    return out


def stamp_schedule_nl(pdf: Path, first_page: int, stats):
    """Schedule I of the Stamp Act from the NON-layout text (the layout text interleaves the two
    columns; reading order keeps each article's heading with its rows). One record per numbered
    Article heading in upper case, in Schedule I only (it ends at "SCHEDULE 1-A"). Everything after
    that heading is kept as ONE record per Schedule, flagged: the PDF mixes state schedules into it
    and they cannot be separated reliably."""
    raw = subprocess.run(  # noqa: S603, S607
        ["pdftotext", "-f", str(first_page + 1), str(pdf), "-"],  # noqa: S607
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    pages = raw.split("\f")
    stream: list[tuple[int, str]] = []
    for i, pr in enumerate(pages):
        body, notes, _ = split_page(pr, False)
        while body and (
            not body[-1].strip() or re.fullmatch(r"\s*\d{1,3}\s*", body[-1])
        ):
            body.pop()
        stream += [(first_page + i, ln) for ln in body]
    # Article headings as printed: "8. APPRAISEMENT", "2[36. LETTER", "4 [37. LETTER", "[49. Promissory note"
    # and a lone "60." with the heading on the next line.
    art = re.compile(
        r"^(?:\d{1,2}\s?(?=\[))?\[?(\d{1,3}[A-Z]{0,2})\.(?:\s*[A-Z]{3,}|\s*[A-Z][a-z]|\s*$)"
    )
    i1a = next(
        (
            i
            for i, (_, ln) in enumerate(stream)
            if re.match(r"^\s*SCHEDULE\s+1-?A\s*$", ln)
        ),
        len(stream),
    )
    out: list[Rec] = []
    seen: set[str] = set()
    last = 4  # Schedule I as printed starts at Article 5
    cur = None
    for pg, ln in stream[:i1a]:
        m = art.match(ln)
        accepted = False
        if m:
            n = int(re.match(r"\d+", m.group(1)).group(0))
            if m.group(1) not in seen and last - 4 <= n <= last + 4:
                accepted = True
                seen.add(m.group(1))
                last = max(last, n)
                cur = Rec(
                    m.group(1), "schedule_article", f"Schedule I, Article {m.group(1)}"
                )
                out.append(cur)
        if cur is not None:
            cur.pages.add(pg)
            if (
                STATE_HEAD.match(ln)
                or STATE_LINE.match(ln)
                or re.match(r"^\s*\[?Vide .*Act", ln)
            ):
                cur.in_state = True
            if accepted:
                cur.in_state = False
            (cur.state_lines if cur.in_state else cur.lines).append(ln.strip())
    # An Article printed only as asterisk lines (omitted) leaves a gap in the numbers: store a stub
    have = {r.label for r in out}
    nums = sorted(int(re.match(r"\d+", r.label).group(0)) for r in out)
    for n in range(nums[0], nums[-1] + 1) if nums else []:
        if str(n) in have or any(re.match(rf"{n}[A-Z]", h) for h in have):
            continue
        prev = max(
            (r for r in out if int(re.match(r"\d+", r.label).group(0)) < n),
            key=lambda r: int(re.match(r"\d+", r.label).group(0)),
        )
        if sum(1 for x in prev.lines if x.strip("* ") == "") >= 1 and any(
            set(x.strip()) <= {"*", " "} and x.strip() for x in prev.lines
        ):
            st = Rec(str(n), "schedule_article", f"Schedule I, Article {n}")
            st.lines = [
                "[not printed: asterisk lines between Articles %d and %d]"
                % (n - 1, n + 1)
            ]
            st.forced_status = "omitted"
            st.stub = True
            out.append(st)
            stats["schedule_stubs_from_asterisks"] += 1
    out.sort(key=lambda r: (int(re.match(r"\d+", r.label).group(0)), r.label))
    if i1a < len(stream):
        out += stamp_tail_blocks(stream[i1a:], stats)
    stats["stamp_schedule_articles"] = sum(
        1 for r in out if r.kind == "schedule_article"
    )
    return out


def stamp_schedule(stream, stats):
    """Schedule I of the Stamp Act: one record per numbered Article (an upper-case heading at the
    left margin, numbers rising). The table is two columns; the text keeps both columns' lines in
    reading order as pdftotext gave them, so the duty column is NOT reliably aligned to its row.
    This is a known limit and is stated in the manifest."""
    art = re.compile(
        r"^\s{0,3}\[?(\d{1,3}[A-Z]{0,2})\.\s+(?:[A-Z][A-Z0-9 ,.;:'’“”()\-—/&\[\]]{5,})"
    )
    out: list[Rec] = []
    last = 0
    cur = None
    for pg, ln in stream:
        m = art.match(ln)
        if m:
            num = int(re.match(r"\d+", m.group(1)).group(0))
            if (
                num >= last
                and num <= last + 6
                and (not out or m.group(1) != out[-1].label)
            ):
                last = num
                cur = Rec(
                    m.group(1), "schedule_article", f"Schedule I, Article {m.group(1)}"
                )
                cur.pages.add(pg)
                cur.lines.append(ln.strip())
                out.append(cur)
                continue
        if cur is not None:
            cur.pages.add(pg)
            cur.lines.append(ln.strip())
    stats["stamp_schedule_articles"] = len(out)
    return out


# ---------------------------------------------------------------------------------------------
# 5. Payload + manifest
# ---------------------------------------------------------------------------------------------
def chunk_id(slug: str, r: Rec) -> str:
    lab = re.sub(r"[^A-Za-z0-9]+", "", r.label)
    if r.kind == "rule":
        v = f"_v{r.variant}" if r.variant > 1 else ""
        return f"{PREFIX}{slug}_o{r.order}{v}_r{lab}"
    pre = {
        "article": "art",
        "section": "s",
        "schedule": "sch",
        "appendix": "app",
        "preamble": "pre",
        "schedule_article": "sch1_art",
    }[r.kind]
    return f"{PREFIX}{slug}_{pre}{lab}"


def payload(a: dict, r: Rec, heading: str, body: str, ordinal: int, total: int) -> dict:
    slug, fname, title, actno, year, mode = a["spec"]
    status = r.forced_status or (
        status_of(r) if r.kind in ("section", "article", "rule") else STATUS
    )
    unit = {
        "article": "Article",
        "rule": "Rule",
        "schedule": "",
        "appendix": "",
        "preamble": "",
    }.get(r.kind, "Section")
    label = f"{unit} {r.label}".strip() if unit else r.label
    if r.kind == "rule":
        label = f"Order {r.order} Rule {r.label}"
    head = f"Act: {title}{f' (Act {actno} of {year})' if actno else ''} | India | {'State amendment (' + r.state_block + ')' if r.state_block else 'Central'} | Status not checked\n{label}: {heading}\n"
    return {
        "chunk_id": chunk_id(slug, r),
        "act_id": f"{PREFIX}{slug}",
        "doc_type": "legislation",
        "country_code": "IN",
        "language_code": "en",
        "text": head + body,
        "chunk_index": ordinal,
        "total_chunks": total,
        "section_number": r.label,
        "sub_section": "",
        "section_title": heading,
        "section_type": r.kind,
        "section_priority": 80,
        "chapter": r.chapter,
        "chapter_title": r.chapter_title,
        "part": r.part,
        "part_title": r.part_title,
        "order_number": r.order,
        "order_variant": r.variant,
        "is_repealed": status == "repealed",
        "title": title,
        "act_number": actno,
        "year": year,
        "category": "central",
        "state": r.state_block.lower() if r.state_block else "central",
        "jurisdiction": "central",
        "act_status": STATUS,
        "section_status": status,
        "stub_from_arrangement": r.stub,
        "state_amendment": bool(r.state_block),
        "amendment_state": r.state_block,
        "amendment_notes": r.notes,
        "amendment_count": len(r.notes),
        "state_amendment_text": "\n".join(r.state_lines),
        "data_source": SOURCE_KIND,
        "extraction_source": "pdf",
        "source_kind": SOURCE_KIND,
        "source_url": a["source_url"],
        "source_file": fname,
        "as_of": a["as_of"],
        "as_of_basis": a["as_of_basis"],
        "page_start": min(r.pages) + 1 if r.pages else None,
        "page_end": max(r.pages) + 1 if r.pages else None,
    }


BOUNDARY = re.compile(
    r"^\s*(?:\(\d+[A-Za-z]?\)|\([a-z]{1,3}\)|\([ivx]+\)|Provided|Explanation|Illustrations?|Exception|"
    r"\[?Vide |State block|\d{1,3}[A-Z]{0,2}\.\s)"
)


def _cut_long_line(ln: str, budget: int) -> list[str]:
    """A single line longer than the budget: cut after a sentence end, else a space, else hard."""
    out = []
    while len(ln) > budget:
        cut = max(ln.rfind(". ", 0, budget), ln.rfind("; ", 0, budget)) + 2
        if cut < budget // 2:
            cut = ln.rfind(" ", 0, budget) + 1
        if cut < budget // 2:
            cut = budget
        out.append(ln[:cut])
        ln = ln[cut:]
    return [*out, ln]


def split_body(body: str, budget: int) -> list[str]:
    """Cut `body` into parts of at most `budget` characters, EXACTLY: ''.join(parts) == body.
    Preferred cut: just before a line that starts a rule, sub-clause, proviso, explanation,
    illustration, state citation or a blank-line paragraph; failing that between lines; a single
    line longer than the budget is cut at a sentence end or a space."""
    if len(body) <= budget:
        return [body]
    pieces = [
        x for ln in body.splitlines(keepends=True) for x in _cut_long_line(ln, budget)
    ]
    parts: list[str] = []
    cur: list[str] = []
    size = 0
    best = 0  # index in `cur` of the last natural boundary
    for pc in pieces:
        if size + len(pc) > budget and cur:
            cut = best if best > 0 else len(cur)
            parts.append("".join(cur[:cut]))
            cur = cur[cut:]
            size = sum(len(x) for x in cur)
            best = 0
        if cur and (BOUNDARY.match(pc) or not cur[-1].strip()):
            best = len(cur)
        cur.append(pc)
        size += len(pc)
    if cur:
        parts.append("".join(cur))
    assert "".join(parts) == body and all(len(x) <= budget for x in parts)
    return parts


def split_payload(p: dict, limit: int = SPLIT_LIMIT) -> list[dict]:
    """One payload -> its parts. Every part keeps the two-line header so it reads on its own, a
    `parent_id` (the unsplit record's chunk_id) and a `part_number`; notes and state text stay on
    part 1 only so nothing is stored twice."""
    head, body = p["text"].split("\n", 2)[:2], p["text"].split("\n", 2)[2]
    head_s = "\n".join(head) + "\n"
    parts = split_body(body, max(400, limit - len(head_s)))
    out = []
    off = 0
    for n, part in enumerate(parts, 1):
        q = dict(p)
        q.update(
            text=head_s + part,
            chunk_id=p["chunk_id"] if len(parts) == 1 else f"{p['chunk_id']}_p{n:02d}",
            parent_id=p["chunk_id"],
            part_number=n,
            total_parts=len(parts),
            char_start=off,
            char_end=off + len(part),
        )
        if n > 1:
            q.update(amendment_notes=[], amendment_count=0, state_amendment_text="")
        out.append(q)
        off += len(part)
    return out


def parse_sources(path: Path) -> dict[str, str]:
    urls: dict[str, str] = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        m = re.match(
            r"\|\s*([\w.-]+\.pdf)\s*\|.*?(https://indiacode\.gov\.in/\S+?)\s*\|\s*$", ln
        )
        if m:
            urls[m.group(1)] = m.group(2)
    return urls


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--pdf-dir", type=Path, required=True, help="a COPY of the PDF folder"
    )
    ap.add_argument(
        "--sources", type=Path, help="SOURCES.md (default: <pdf-dir>/SOURCES.md)"
    )
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--split-limit", type=int, default=SPLIT_LIMIT)
    a = ap.parse_args(argv)
    urls = parse_sources(a.sources or a.pdf_dir / "SOURCES.md")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    a_chunks = (a.out_dir / "supplement_chunks.jsonl").open("w", encoding="utf-8")
    with (a.out_dir / "supplement_records.jsonl").open("w", encoding="utf-8") as fh:
        for spec in ACTS:
            res = build_act(a.pdf_dir / spec[1], spec, urls)
            recs = res["recs"]
            seen: Counter = Counter(
                r.kind + "|" + r.label + "|" + r.order + "|" + str(r.variant)
                for r, _, _ in recs
            )
            total_chars = 0
            statuses: Counter = Counter()
            short = []
            for i, (r, h, b) in enumerate(recs):
                p = payload(res, r, h, b, i, len(recs))
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
                for q in split_payload(p, a.split_limit):
                    a_chunks.write(json.dumps(q, ensure_ascii=False) + "\n")
                total_chars += len(p["text"])
                statuses[p["section_status"]] += 1
                if len(b) < SHORT:
                    short.append(
                        {
                            "label": r.label,
                            "order": r.order,
                            "status": p["section_status"],
                            "body_chars": len(b),
                        }
                    )
            toc = res["toc"] or []
            found = {r.label for r, _, _ in recs if r.kind in ("section", "article")}
            manifest.append(
                {
                    "slug": spec[0],
                    "file": spec[1],
                    "title": spec[2],
                    "mode": spec[5],
                    "as_of": res["as_of"],
                    "as_of_basis": res["as_of_basis"],
                    "source_url": res["source_url"],
                    "pages": res["pages"],
                    "records": len(recs),
                    "characters": total_chars,
                    "by_kind": dict(Counter(r.kind for r, _, _ in recs)),
                    "by_status": dict(statuses),
                    "short_sections_under_30_chars": short,
                    "duplicated_section_numbers": [k for k, v in seen.items() if v > 1],
                    "toc_labels": len(toc),
                    "toc_labels_not_found_in_body": [t for t in toc if t not in found][
                        :80
                    ],
                    "footnotes_attached": sum(len(r.notes) for r, _, _ in recs),
                    "with_state_amendment_text": sum(
                        1 for r, _, _ in recs if r.state_lines
                    ),
                    "stats": res["stats"],
                    "dropped": res["dropped"],
                }
            )
    a_chunks.close()
    (a.out_dir / "supplement_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for m in manifest:
        print(
            f"{m['slug']:15s} records={m['records']:5d} chars={m['characters']:9d} as_of={m['as_of']} ({m['as_of_basis']}) "
            f"short={len(m['short_sections_under_30_chars'])} dup={len(m['duplicated_section_numbers'])} "
            f"toc={m['toc_labels']} missing_from_body={len(m['toc_labels_not_found_in_body'])}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
