"""How much OCR noise sits in the served Supreme Court text, read as exposure for verifier check 3.

Plain words: check 3 (core/verify.py `normalise`) turns punctuation into spaces and collapses
spaces; it keeps every word and every letter as stored. So a quote written the way a person
would type it fails if the stored text carries OCR damage inside that stretch of words: a margin
letter ("D  E") between two words, two words glued ("nameThe"), `l` for `1`, a page header in
the middle of a sentence, a hyphen left from a line break.

This script does NOT test the verifier. It cuts each sampled chunk into windows of 12 words (the
size of a short quote) and reports the share of windows that contain at least one such artifact.
That share is an EXPOSURE rate: an upper bound on quotes that could fail for OCR reasons, not a
measured failure rate (there is no clean copy of the text to compare against).

Reads the scratch sqlite dump made by scan/sc/dump_text.py. Touches no collection.
Usage: python scan/sc/ocr_noise.py SC_TEXT.db OUT.json [CHUNKS_PER_ERA]
Pipeline: none of the 11 steps; offline measurement.
"""

# ruff: noqa: E501  (regex comments)
from __future__ import annotations

import json
import re
import sqlite3
import sys
import zlib
from collections import Counter

WINDOW = 12
ERAS = [(1950, 1969), (1970, 1989), (1990, 2009), (2010, 2025)]

ARTIFACTS = {
    # a margin letter A-H (the printed column marker) sitting between lower-case words
    "margin_letter": re.compile(r"[a-z,;]\s{1,3}(?:[A-H]\s{1,3}){1,4}(?=[a-z0-9(])"),
    # two words glued: a lower-case run then a capital then lower-case, e.g. "nameThe"
    "glued_words": re.compile(r"\b[a-z]{2,}[A-Z][a-z]{2,}\b"),
    # a digit read as l or I inside or beside a number
    "l_for_1": re.compile(
        r"\b[lI]\s+(?:SCC|SCR|S\.C\.R|AIR)\b|\b\d+[lI]\d*\b|\b[lI]\d{2,}\b"
    ),
    # a running page header inside the text
    "page_header": re.compile(
        r"SUPREME COURT REPORTS|Digital Supreme Court Reports|\[\d{4}\]\s*(?:SUPP\.?\s*)?\d*\s*S\.?C\.?R\.?\s*\d+",
        re.I,
    ),
    # a word split by a line-break hyphen left in place
    "hyphen_split": re.compile(r"\b[a-z]{2,}-\s+[a-z]{2,}\b"),
    # mismatched brackets, e.g. (2010] or [2010)
    "bracket_swap": re.compile(r"\(\d{4}\]|\[\d{4}\)"),
}


def body_of(text: str) -> str:
    return text.split("\n\n", 1)[1] if "\n\n" in text else text


def windows(body: str) -> list[str]:
    spans = [m.span() for m in re.finditer(r"\S+", body)]
    return [
        body[spans[i][0] : spans[i + WINDOW - 1][1]]
        for i in range(0, len(spans) - WINDOW + 1, WINDOW)
    ]


def measure(db: str, per_era: int) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out: dict = {"window_words": WINDOW, "per_era_chunks": per_era, "eras": {}}
    for lo, hi in ERAS:
        rows = con.execute(
            "SELECT text FROM ch WHERE CAST(year AS INTEGER) BETWEEN ? AND ? "
            "ORDER BY (rowid * 2654435761) % 1000003 LIMIT ?",
            (lo, hi, per_era),
        ).fetchall()
        n = hit_any = 0
        by: Counter = Counter()
        for (blob,) in rows:
            text = (
                zlib.decompress(blob).decode("utf-8")
                if isinstance(blob, bytes)
                else blob
            )
            for w in windows(body_of(text)):
                n += 1
                found = [k for k, rx in ARTIFACTS.items() if rx.search(w)]
                hit_any += bool(found)
                by.update(found)
        out["eras"][f"{lo}-{hi}"] = {
            "chunks": len(rows),
            "windows": n,
            "windows_with_any": hit_any,
            "share_any": round(hit_any / n, 4) if n else None,
            "by_type": {k: round(by[k] / n, 4) if n else None for k in ARTIFACTS},
        }
    return out


if __name__ == "__main__":
    result = measure(sys.argv[1], int(sys.argv[3]) if len(sys.argv) > 3 else 3000)
    with open(sys.argv[2], "w") as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result, indent=1))
