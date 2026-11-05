"""Compare text extracted from a bucket PDF with the text we already store for the same case.

Plain words: for cases we hold, take the bucket's English PDF (pdftotext), take our stored chunks
(rebuilt without their overlap), strip the layout-parser markers ([SECTION] ##, [TITLE] #) and compare:
size, OCR artifact rates per 1,000 words (scan/sc/ocr_noise.py), words not in a dictionary, and a
word-level diff. Reads the scratch sqlite dump; touches no collection.
Usage: python scan/sc/pdf_vs_stored.py SC_TEXT.db PDF_DIR OUT.json
Pipeline: none of the 11 steps; offline measurement before an ingest decision.
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import measure_refs  # noqa: E402
import ocr_noise  # noqa: E402

MARK = re.compile(
    r"\[(?:SECTION|TITLE|PARAGRAPH|TABLE|FOOTNOTE)\]\s*#*\s*|^#+\s*", re.M
)
WORD = re.compile(r"[A-Za-z]{3,}")


def dictionary() -> set[str]:
    return {w.strip().lower() for w in open("/usr/share/dict/words", errors="ignore")}


def stored_text(db: sqlite3.Connection, cid: str) -> str:
    rows = db.execute(
        "select chunk_id, idx, cs, ce, text from ch where case_id=?", (cid,)
    ).fetchall()
    text = measure_refs.rebuild(rows)
    return MARK.sub(" ", text)


def pdf_text(path: Path) -> str:
    return subprocess.run(  # noqa: S603  (fixed argv, a local file we chose)
        ["pdftotext", "-layout", str(path), "-"],  # noqa: S607
        capture_output=True,
        text=True,
    ).stdout


def rates(text: str, vocab: set[str]) -> dict:
    words = text.split()
    n = len(words) or 1
    out = {"words": len(words)}
    for k, rx in ocr_noise.ARTIFACTS.items():
        out[k + "_per_1000w"] = round(1000 * len(rx.findall(text)) / n, 2)
    alpha = WORD.findall(text)
    out["oov_share_pct"] = round(
        100 * sum(w.lower() not in vocab for w in alpha) / max(1, len(alpha)), 2
    )
    out["non_ascii_per_1000w"] = round(1000 * sum(ord(c) > 127 for c in text) / n, 2)
    return out


def norm_words(text: str) -> list[str]:
    return re.sub(r"[^A-Za-z0-9 ]", " ", text).split()


def main(db_path: str, pdf_dir: str, out: str) -> None:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    vocab = dictionary()
    res = {}
    for pdf in sorted(Path(pdf_dir).glob("*.pdf")):
        cid = pdf.stem
        a, b = stored_text(db, cid), pdf_text(pdf)
        wa, wb = norm_words(a), norm_words(b)
        sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
        res[cid] = {
            "stored": rates(a, vocab),
            "pdf": rates(b, vocab),
            "word_diff_ratio": round(sm.ratio(), 4),
            "stored_only_words": sum(
                i2 - i1
                for t, i1, i2, _, _ in sm.get_opcodes()
                if t in ("delete", "replace")
            ),
            "pdf_only_words": sum(
                j2 - j1
                for t, _, _, j1, j2 in sm.get_opcodes()
                if t in ("insert", "replace")
            ),
        }
        print(cid, res[cid]["word_diff_ratio"], flush=True)
    Path(out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
