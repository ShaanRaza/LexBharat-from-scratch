"""OCR adapter: reads text out of uploaded PDFs, Word files and scans.

Rule 1: the ONLY file that talks to PyMuPDF / python-docx / Tesseract (or a later
Textract swap). Used by the background worker, not by the research pipeline.

Every page keeps its page number so a citation can jump to the exact page
(docs/ARCHITECTURE.md "Uploads"). `quality` lets the worker fail unreadable scans early
without charging the user.

Only the interface and a Fake live here; no real OCR runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OcrPage:
    page_no: int
    text: str


@dataclass(frozen=True)
class OcrResult:
    pages: list[OcrPage]
    quality: float  # 0-1; below the (not yet decided) threshold means "unreadable"
    ocr_used: bool


class OcrEngine(Protocol):
    async def extract(self, data: bytes, mime_type: str) -> OcrResult: ...


class FakeOcr:
    """Treats the bytes as UTF-8 text, one page per form-feed character."""

    def __init__(self, quality: float = 1.0) -> None:
        self.quality = quality

    async def extract(self, data: bytes, mime_type: str) -> OcrResult:
        parts = data.decode("utf-8", errors="replace").split("\f")
        pages = [OcrPage(i + 1, p) for i, p in enumerate(parts)]
        return OcrResult(pages=pages, quality=self.quality, ocr_used=False)
