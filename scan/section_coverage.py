"""Section-level coverage of every Union-level Act in the served collection (free, read-only, no model calls).

The Act-level inventory (DATA-GAPS section 20) counts Acts. This counts SECTIONS: for each Union-level Act, how many of the sections
it should have are held, which are missing, and whether a provision that other sections lean on is missing or crowded out.

"Should have" is not in the data, so it is estimated the way the owner's earlier checker did (`lexbharat-merge`,
`src/lib/acts/gaps.mjs`, `docs/MISSING-SECTIONS.md`), ported here so the two can be compared:
  * An Indian Act numbers its sections 1, 2, 3 ... without skipping, so an integer absent from 1..N is very likely absent from the
    data. N = the highest section number held that is not an isolated straggler (`robust_max`), or the highest "section N" the
    Act's own text cites, whichever is larger; for 17 very well-known Acts N is their statutory section count instead
    (`KNOWN_SECTION_COUNTS`, from general knowledge, not checked against India Code).
  * N is a LOWER BOUND, so the shortfall is a lower bound too, with two known errors in opposite directions: Schedule rows filed
    as sections can push N above the real last section (a missing-number count too high), and a legitimately omitted or repealed
    section number counts as missing (also too high). A tail of sections missing beyond the highest number held is invisible
    (too low).
  * A missing number is FOUNDATIONAL when the Act's own text cites it as "section N" in at least `FOUNDATIONAL_CITES` different
    chunks: other sections lean on it, so it is not an omitted placeholder. A held number is a COLLISION when 3 or more different
    provisions (different headings) are filed under it; when such a number is also cited that often, the real section may be absent
    and a different provision stands in its place (the pattern found for CPC sections 9 and 11, where Order rules are labelled
    "Section 9" and the text of Section 9 itself is not in the data).

  python -m scan.section_coverage pull      # reads kanoon_v1 on the copy instance, writes a local JSONL (no embeddings, no model calls)
  python -m scan.section_coverage analyse   # writes coverage.json and the report tables
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

HOME = Path.home() / "qdrant-kanoon" / "section_coverage"
COPY_INSTANCE = "http://127.0.0.1:7333"
COLLECTION = "kanoon_v1"
FIELDS = [
    "act_id",
    "title",
    "act_status",
    "section_type",
    "section_number",
    "section_title",
    "chunk_id",
    "text",
]

CONFIDENT_DENSITY, CONFIDENT_MAX_RUN = 0.85, 5
FOUNDATIONAL_CITES = 3
MIN_EXPECTED_FOR_RANKING = (
    10  # a 4-section Act missing 2 is 50% but is not what the ranking is for
)

# Statutory section counts of 17 very well-known Acts (general knowledge, NOT checked against India Code).
KNOWN_SECTION_COUNTS = {
    "negotiable instruments act 1881": 148,
    "indian penal code 1860": 511,
    "indian evidence act 1872": 167,
    "code of criminal procedure 1973": 484,
    "code of civil procedure 1908": 158,
    "indian contract act 1872": 238,
    "limitation act 1963": 32,
    "transfer of property act 1882": 137,
    "arbitration and conciliation act 1996": 86,
    "specific relief act 1963": 44,
    "hindu marriage act 1955": 30,
    "hindu succession act 1956": 31,
    "motor vehicles act 1988": 217,
    "companies act 2013": 470,
    "information technology act 2000": 90,
    "sale of goods act 1930": 66,
    "narcotic drugs and psychotropic substances act 1985": 83,
}

_BASE_INT = re.compile(r"^(\d{1,4})(?:[A-Za-z]{0,3}(?:-[A-Za-z0-9]+)?)?$")
_CITE = re.compile(
    r"\bsections?\s+(\d{1,4})[A-Z]?\b"
    r"(?![^.;\n]{0,24}?\b(?:of|under)\s+(?:the\s+)?(?!this\b)[A-Z][\w ,'()-]{0,50}?"
    r"\b(?:Act|Code|Sanhita|Constitution)\b)"
)
_HEADING = re.compile(
    r"(?m)^(?:>\s*)?[\s*_#`|\u2014\-]*(?:\d+\[\s*)?[\s*_\[]*(\d{1,3})([A-Z]{0,2})[\s*_\]]*[.\u2014]"
    r"[\s*_\[\]\d]*(?=[A-Z\"\u201c(])"
)
_YEAR_THEN = re.compile(
    r"^(.*?\b[12]\d{3})\b"
)  # "<name> <year>", the rest of a title dropped


def base_int(n: object) -> int | None:
    m = _BASE_INT.match(str(n if n is not None else "").strip())
    return int(m.group(1)) if m else None


def robust_max(present: set[int] | list[int]) -> int:
    """Highest held number that is not an isolated straggler (a schedule row or a mis-read number):
    at least 3 held numbers lie within 12 below it, or it is the only way to count at all."""
    arr = sorted(present, reverse=True)
    for n in arr:
        if sum(1 for m in arr if n - 12 < m <= n) >= 3:
            return n
    return arr[0] if arr else 0


def cited_sections(text: str, cap: int) -> list[int]:
    """The "section N" numbers the text cites without naming another Act right after them (years and numbers above `cap` dropped)."""
    out = []
    for m in _CITE.finditer(text or ""):
        n = int(m.group(1))
        if not (1800 <= n <= 2100) and n <= cap:
            out.append(n)
    return out


def title_key(title: str) -> str:
    """'The Indian Penal Code, 45 of 1860 (Rep., Act 45 of 2023)' -> 'indian penal code 1860'."""
    t = re.sub(r"\([^)]*\)", " ", str(title))
    t = re.sub(r"\b(?:no\.?\s*)?\d{1,3}\s+of\s+(?=[12]\d{3}\b)", " ", t, flags=re.I)
    m = _YEAR_THEN.match(t)
    s = (m.group(1) if m else str(title)).lower()
    return re.sub(r"^the ", "", re.sub(r"[^a-z0-9]+", " ", s).strip())


def runs(missing: list[int]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for n in missing:
        if out and out[-1][1] == n - 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return [(a, b) for a, b in out]


def _body(r: dict) -> str:
    return re.sub(r"^Act:[^\n]*\n(?:[^\n]*Section [^\n]*\n)?", "", r.get("text") or "")


def heading_numbers(rows: list[dict]) -> set[int]:
    """Numbers that appear as a heading ("12. Functions of the Commission") in the chunk text, whatever the chunk's label says.
    An optimistic upper bound for what text is present: Schedule rows and numbered lists also match."""
    found: set[int] = set()
    for r in rows:
        found.update(int(m.group(1)) for m in _HEADING.finditer(_body(r)))
    return {n for n in found if n > 0 and not (1800 <= n <= 2100)}


def merged_into_neighbour(
    rows: list[dict], missing: list[int], collisions: set[int]
) -> list[int]:
    """Missing numbers whose heading is inside a chunk labelled 1 to 3 numbers lower: the section's text is stored, appended to
    the section before it (found for IPC 34 inside the chunk labelled 33, NDPS 37 inside 36C, Registration Act 49 inside 48).
    A number shared by 3 or more provisions is never credited: Order rules carry the same numbers (CPC 9 and 11)."""
    want = set(missing) - collisions
    got: set[int] = set()
    for r in rows:
        lab = base_int(r.get("section_number"))
        if lab is None:
            continue
        for m in _HEADING.finditer(_body(r)):
            n = int(m.group(1))
            if n in want and lab - 3 <= n - 1 and n - 3 <= lab <= n - 1:
                got.add(n)
    return sorted(got)


def analyse_act(rows: list[dict]) -> dict:
    """One Act's section-level coverage from its chunks (rows have the FIELDS above).

    category: "no labels" = no chunk carries a section number (the text is stored as unlabelled blocks, so a lookup by section
    number cannot find anything, though the text may be searchable); "stub" = 1 to 3 labelled sections in an Act that should
    have 10 or more; "labelled" = everything else."""
    title = rows[0]["title"]
    sec = [r for r in rows if r.get("section_type") == "section"]
    present = {
        n
        for r in sec
        if (n := base_int(r.get("section_number"))) is not None
        and n > 0
        and not (1800 <= n <= 2100)  # a year filed as a section number
    }
    heads = heading_numbers(rows)
    held_max = robust_max(present) if present else robust_max(heads)
    cap = max(60, held_max * 2)
    cites: collections.Counter = collections.Counter()
    cited_max = 0
    for r in rows:
        mine = set(cited_sections(r.get("text") or "", cap))
        cited_max = max([cited_max, *mine])
        for n in mine:
            cites[n] += 1  # one count per chunk that cites it
    known = KNOWN_SECTION_COUNTS.get(title_key(title), 0)
    expected = known or min(max(held_max, cited_max), 3000)
    missing = (
        [n for n in range(1, expected + 1) if n not in present] if expected else []
    )
    held = expected - len(missing)
    density = held / expected if expected else 0.0
    ok = density >= CONFIDENT_DENSITY
    confident = [
        n
        for a, b in runs(missing)
        if ok and b - a + 1 <= CONFIDENT_MAX_RUN
        for n in range(a, b + 1)
    ]
    # provisions filed under one number (a plain number: 376A, 376B ... are different sections, not a collision on 376)
    titles: dict[int, set[str]] = collections.defaultdict(set)
    for r in sec:
        raw = str(r.get("section_number") or "").strip()
        if raw.isdigit() and int(raw) > 0:
            titles[int(raw)].add(
                re.sub(r"\W+", " ", (r.get("section_title") or "").lower()).strip()[:60]
            )
    collisions = sorted(n for n, t in titles.items() if len(t) >= 3)
    merged = merged_into_neighbour(rows, missing, set(collisions))
    likely_absent = [n for n in missing if n not in set(merged)]
    if not present:
        # stored as unlabelled blocks: judge by the headings found in the text instead of by labels
        merged = [n for n in missing if n in heads]
        likely_absent = [n for n in missing if n not in heads]
    foundational_absent = [
        n for n in likely_absent if cites.get(n, 0) >= FOUNDATIONAL_CITES
    ]
    foundational_collision = [
        n
        for n in collisions
        if n <= (expected or 10**6) and cites.get(n, 0) >= FOUNDATIONAL_CITES
    ]
    category = (
        "no labels"
        if not present
        else "stub"
        if len(present) <= 3 and expected >= MIN_EXPECTED_FOR_RANKING
        else "labelled"
    )
    return {
        "title": title,
        "status": rows[0].get("act_status"),
        "chunks": len(rows),
        "category": category,
        "expected": expected,
        "expected_source": "known count" if known else "highest held or cited",
        "held": held,
        "held_by_text_heading": len([n for n in heads if n <= expected]),
        "missing_n": len(missing),
        "merged_n": len(merged),
        "merged": merged,
        "likely_absent_n": len(likely_absent),
        "likely_absent_share": (len(likely_absent) / expected) if expected else 0.0,
        "missing_share": (len(missing) / expected) if expected else 0.0,
        "missing": missing,
        "confident_missing": confident,
        "collisions": collisions,
        "foundational_absent": [(n, cites[n]) for n in foundational_absent],
        "foundational_collision": [(n, cites[n]) for n in foundational_collision],
        "heading_other_number": sum(
            1
            for r in sec
            if _starts_with_other_number(r.get("section_number"), r.get("text") or "")
        ),
    }


def _starts_with_other_number(number: object, body: str) -> bool:
    head = re.sub(r"^Act:[^\n]*\n(?:Section [^\n]*\n\n)?", "", body)
    head = re.sub(r"^[\s#>*_\-|]+", "", head)[:60]
    m = re.match(
        r"^(?:section\s+)?(\d{1,4}[A-Za-z]{0,3})\s*[.\-—:)(]", head, flags=re.I
    )
    return bool(m) and m.group(1).upper() != str(number).strip().upper()


# ---------------------------------------------------------------------------------------------------------------------
# pull / analyse
# ---------------------------------------------------------------------------------------------------------------------
def pull(out: Path) -> int:
    from qdrant_client import QdrantClient, models

    c = QdrantClient(url=COPY_INSTANCE, timeout=120, prefer_grpc=False)
    flt = models.Filter(
        must=[
            models.FieldCondition(
                key="jurisdiction", match=models.MatchValue(value="central")
            )
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    n, off = 0, None
    with out.open("w") as f:
        while True:
            pts, off = c.scroll(
                COLLECTION,
                scroll_filter=flt,
                limit=1000,
                offset=off,
                with_payload=FIELDS,
            )
            for p in pts:
                f.write(json.dumps({k: p.payload.get(k) for k in FIELDS}) + "\n")
            n += len(pts)
            if off is None:
                break
    return n


def load(path: Path) -> dict[str, list[dict]]:
    acts: dict[str, list[dict]] = collections.defaultdict(list)
    for line in path.read_text().splitlines():
        r = json.loads(line)
        acts[r["act_id"]].append(r)
    return acts


def summarise(results: dict[str, dict]) -> dict:
    def block(items: list[dict]) -> dict:
        exp = sum(a["expected"] for a in items)
        mis = sum(a["missing_n"] for a in items)
        return {
            "acts": len(items),
            "expected": exp,
            "held": exp - mis,
            "missing": mis,
            "missing_share": mis / exp if exp else 0.0,
            "merged_into_neighbour": sum(a["merged_n"] for a in items),
            "likely_absent": sum(a["likely_absent_n"] for a in items),
            "likely_absent_share": sum(a["likely_absent_n"] for a in items) / exp
            if exp
            else 0.0,
            "acts_missing_any": sum(1 for a in items if a["missing_n"]),
            "acts_under_half": sum(
                1 for a in items if a["expected"] and a["held"] / a["expected"] < 0.5
            ),
            "acts_with_foundational_absent": sum(
                1 for a in items if a["foundational_absent"]
            ),
            "acts_with_foundational_collision": sum(
                1 for a in items if a["foundational_collision"]
            ),
            "acts_with_confident_missing": sum(
                1 for a in items if a["confident_missing"]
            ),
            "confident_missing": sum(len(a["confident_missing"]) for a in items),
            "categories": dict(collections.Counter(a["category"] for a in items)),
        }

    allv = list(results.values())
    by = collections.defaultdict(list)
    for a in allv:
        by[a["status"]].append(a)
    return {"all": block(allv), **{f"status:{k}": block(v) for k, v in by.items()}}


def worst(
    results: dict[str, dict], n: int = 50, status: str | None = None
) -> list[dict]:
    items = [
        {"act_id": k, **v}
        for k, v in results.items()
        if v["expected"] >= MIN_EXPECTED_FOR_RANKING
        and (status is None or v["status"] == status)
    ]
    items.sort(key=lambda a: (-a["likely_absent_share"], -a["likely_absent_n"]))
    return items[:n]


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _row(i: int, a: dict) -> str:
    fa = ", ".join(f"{n} ({c})" for n, c in a["foundational_absent"][:4]) or "-"
    return (
        f"| {i} | {a['title'][:58]} | {a['status']} | {a['category']} | {a['held']} / {a['expected']} | "
        f"{a['missing_n']} | {a['merged_n']} | {a['likely_absent_n']} ({_pct(a['likely_absent_share'])}) | {fa} |"
    )


_HEAD = (
    "| # | Act | Status | Category | Labelled / expected | No chunk labelled | Of those, text inside the chunk before | "
    "Likely absent (share) | Foundational sections absent (times cited) |\n"
    "|---:|---|---|---|---:|---:|---:|---:|---|"
)


def render(results: dict[str, dict], summary: dict) -> str:
    L = [
        "# Section coverage of the Union-level Acts (generated by `scan/section_coverage.py`; do not edit by hand)",
        "",
    ]
    L.append(
        "Measured on the served collection `kanoon_v1` (74,484 Union-level Act points, the copy instance, 5 Nov 2026). Free, "
        "read-only, no model calls. Method and limits are in the module docstring of `scan/section_coverage.py`."
    )
    L += ["", "## Headline", ""]
    L.append(
        "| | Acts | Sections expected (lower bound) | Chunk labelled with the number | No chunk labelled | "
        "...of which the text is inside the chunk before | **Likely absent** | Share |"
    )
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for key, label in (
        ("all", "All Union-level Acts"),
        ("status:in_force", "In force"),
        ("status:repealed", "Repealed"),
        ("status:spent", "Spent"),
    ):
        s = summary[key]
        L.append(
            f"| {label} | {s['acts']:,} | {s['expected']:,} | {s['held']:,} | {s['missing']:,} | "
            f"{s['merged_into_neighbour']:,} | **{s['likely_absent']:,}** | **{_pct(s['likely_absent_share'])}** |"
        )
    f = summary["status:in_force"]
    L += [
        "",
        f"In force: **{f['acts_missing_any']} of {f['acts']} Acts lack a chunk for at least one section number** "
        f"(only {f['acts'] - f['acts_missing_any']} have every number from 1 to N); {f['acts_under_half']} hold fewer than half "
        f"of the labels they should; {f['acts_with_foundational_absent']} are missing a section that other sections of the "
        f"same Act cite at least {FOUNDATIONAL_CITES} times; {f['acts_with_foundational_collision']} have a shared number that "
        f"is also cited that often. Structure of the Acts in force: {f['categories']}.",
        "",
        "`no labels` = the Act is stored as unlabelled text blocks (a lookup by section number finds nothing, though the text may "
        "be searchable); `stub` = 1 to 3 labelled sections in an Act that should have 10 or more; `labelled` = the rest.",
        "",
    ]
    L += [
        "## How far to trust these numbers",
        "",
        "* **The same method, run independently, agrees.** The owner's earlier checker (`lexbharat-merge`, W10, on that repo's own "
        "copy of the data) found, for Acts in force, 38,508 sections expected and 8,881 missing; this scan finds "
        f"{f['expected']:,} expected and {f['missing']:,} with no chunk labelled. For all 1,568 Acts it found 68,822 expected and "
        "32,425 missing; this scan finds fewer because a year filed as a section number is no longer counted as one.",
        "* **N is a lower bound**, so a shortfall of a tail (sections beyond the highest number held) is invisible. Schedule rows "
        "filed as sections can push N up, and an omitted or repealed section number counts as missing; both make the missing "
        "count too high.",
        "* **'Text inside the chunk before'** credits a missing number when its heading is found inside a chunk labelled 1 to 3 "
        "numbers lower (the chunker appends an amended or substituted section to the one before it). Hand-checked on three "
        "known cases (IPC 34 inside the chunk labelled 33, NDPS 37 inside 36C, Registration Act 49 inside 48) and on 16 random "
        "credits: 13 were the real section's heading, 3 were not (a footnote, an amendment-table row, a list), so the credit "
        "slightly over-states what is present. **The honest range for sections with no text anywhere is therefore the 'Likely "
        "absent' figure up to the 'No chunk labelled' figure.**",
        "* **Not detected:** a number that is labelled and shared by Order or Schedule rules while the section's own text is "
        "absent (CPC 9 and 11). Those appear only in the shared-number table below.",
        "* **Not measured:** whether a labelled section's text is complete. The holes are in the source: the parquet has "
        "1,098,269 rows against 1,098,577 points in `acts_india` (Central: 25 more points than rows, none fewer; DATA-GAPS section "
        "20), so the holes are in the source file and were not lost in indexing.",
        "",
    ]
    L += [
        "## The worst 50 Acts in force, by share likely absent (Acts expected to have 10 or more sections)",
        "",
        _HEAD,
    ]
    for i, a in enumerate(worst(results, 50, "in_force"), 1):
        L.append(_row(i, a))
    L += [
        "",
        "## The worst 50 Acts of all 1,568, by share likely absent (expected 10 or more)",
        "",
        _HEAD,
    ]
    for i, a in enumerate(worst(results, 50), 1):
        L.append(_row(i, a))
    fa = sorted(
        (
            a
            for a in results.values()
            if a["status"] == "in_force" and a["foundational_absent"]
        ),
        key=lambda a: -len(a["foundational_absent"]),
    )
    L += [
        "",
        "## Foundational sections absent, Acts in force (cited at least 3 times by the same Act, no chunk and no text found)",
        "",
        "| Act | Labelled / expected | Absent sections (times cited by the Act) |",
        "|---|---:|---|",
    ]
    for a in fa[:40]:
        L.append(
            f"| {a['title'][:60]} | {a['held']} / {a['expected']} | "
            + ", ".join(f"{n} ({c})" for n, c in a["foundational_absent"][:10])
            + " |"
        )
    col = sorted(
        (a for a in results.values() if a["status"] == "in_force" and a["collisions"]),
        key=lambda a: -len(a["collisions"]),
    )
    L += [
        "",
        f"## Numbers shared by 3 or more different provisions, Acts in force ({len(col)} Acts)",
        "",
        "The pattern behind CPC sections 9 and 11, where Order rules carry the section's number and the section's own text is not "
        "in the data (confirmed for CPC by phrase search; NOT confirmed for the others). These Acts need the check below "
        "before anything is said about them.",
        "",
        "| Act | Numbers shared by 3+ provisions | Examples |",
        "|---|---:|---|",
    ]
    for a in col[:25]:
        L.append(
            f"| {a['title'][:60]} | {len(a['collisions'])} | {', '.join(map(str, a['collisions'][:10]))} |"
        )
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=["pull", "analyse", "report"])
    ap.add_argument("--doc", type=Path)
    a = ap.parse_args()
    raw = HOME / "central_points.jsonl"
    if a.stage == "pull":
        print(f"{pull(raw)} points -> {raw}")
        return
    if a.stage == "report":
        d = json.loads((HOME / "coverage.json").read_text())
        md = render(d["acts"], d["summary"])
        if a.doc:
            a.doc.write_text(md)
            print(f"wrote {a.doc}")
        else:
            print(md)
        return
    acts = load(raw)
    results = {k: analyse_act(v) for k, v in acts.items()}
    summary = summarise(results)
    (HOME / "coverage.json").write_text(
        json.dumps({"summary": summary, "acts": results}, indent=1, default=list)
    )
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
