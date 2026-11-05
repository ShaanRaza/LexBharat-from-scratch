"""Builds citation_forms.json from the practice judgments (20 real Supreme Court
judgments, tests/fixtures/practice). Run by hand when the practice fixtures change:

    .venv/bin/python tests/trust/fixtures/build_citation_forms.py

The JSON holds REAL citation strings found in the dataset (the stored `citation` of
each judgment and the AIR / SCC / SCR / "X v. Y" strings that appear inside the judgment
texts) plus phrases that look a little like citations but are not. The tests
(tests/trust/test_citation_forms.py) use it for both directions: spellings that MUST be
caught when recalled, and strings that must NOT be touched."""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
rows = [
    json.loads(line)
    for line in gzip.open(ROOT / "tests/fixtures/practice/judgments.jsonl.gz", "rt")
]
text = "\n".join(r["full_text"] for r in rows)


def uniq(found: list[str], keep: int) -> list[str]:
    seen: dict[str, None] = {}
    for f in found:
        f = " ".join(f.split())
        seen.setdefault(f)
    return sorted(seen)[:keep]


air = uniq(re.findall(r"\bA\.?I\.?R\.?\s*\d{4}\s*[A-Z][A-Za-z.]{1,5}\s*\d+", text), 30)
scc = uniq(re.findall(r"\(\d{4}\)\s*\d+\s*SCC\s*\d+", text), 10)
scr = uniq(re.findall(r"\[\d{4}\]\s*\d?\s*S\.?C\.?R\.?\s*\d+", text), 30)
cases = uniq(
    re.findall(
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\s+v\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}",
        text,
    ),
    40,
)

NOT_CITATIONS = [
    "Article 21 of the Constitution protects life and personal liberty",
    "Section 438 of the Code of Criminal Procedure, 1973 deals with anticipatory bail",
    "under Section 138 of the Negotiable Instruments Act, 1881",
    "Order 39 Rule 1 of the Code of Civil Procedure",
    "the amendment of 1973 (as revised) applies to every pending case",
    "the Act of 1973 (4 of 1973) came into force in April",
    "the compensation was Rs. 4 lakh in 2019",
    "air quality in 1973 was not an issue before the Court",
    "the SCC members met in 1973 to decide the matter",
    "members of the SC and ST communities are protected by that law",
    "in the 1973 judgment the Court sat in a bench of five",
    "Article 14 v. Article 19 is a common framing of the argument",
    "Chapter 4 v. Chapter 5 of the Code lays down different periods",
    "the State appealed within thirty days of the order",
    "the appellant and the respondent were heard on 12 March 1978",
]

out = {
    "source": "tests/fixtures/practice/judgments.jsonl.gz (20 real SC judgments)",
    "stored_citation_strings": [r["citation"] for r in rows],
    "in_text": {"air": air, "scc": scc, "scr": scr, "case_names": cases},
    "not_citations": NOT_CITATIONS,
}
(Path(__file__).with_name("citation_forms.json")).write_text(
    json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(
    {k: len(v) for k, v in out["in_text"].items()}, len(out["stored_citation_strings"])
)
