"""Text extraction from uploaded files: PyMuPDF for text PDFs, Tesseract for scans.
The ONLY file that imports those libraries. Every page keeps its page number so a
citation can jump to the exact passage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from adapters.guard import refuse_in_production


@dataclass(frozen=True)
class PageText:
    page: int  # 1-based
    text: str


@dataclass(frozen=True)
class OcrResult:
    pages: tuple[PageText, ...]
    readable: bool  # False = low quality: fail early, do not charge
    used_ocr: bool = False


class TextExtractor(Protocol):
    async def extract(self, data: bytes, filename: str) -> OcrResult: ...


class PdfExtractor:
    """Real. PyMuPDF/Tesseract imported lazily. Tesseract path not wired; scans are
    reported unreadable until it is. Not verified."""

    async def extract(self, data: bytes, filename: str) -> OcrResult:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        pages = tuple(PageText(i + 1, p.get_text()) for i, p in enumerate(doc))
        chars = sum(len(p.text.strip()) for p in pages)
        return OcrResult(pages, readable=chars >= 50 * max(len(pages), 1))


class FakeExtractor:
    """UTF-8 bytes as text, one page per form feed; under 20 chars = unreadable."""

    def __init__(self) -> None:
        refuse_in_production()

    async def extract(self, data: bytes, filename: str) -> OcrResult:
        text = data.decode("utf-8", errors="ignore")
        pages = tuple(PageText(i + 1, t) for i, t in enumerate(text.split("\f")))
        return OcrResult(pages, readable=len(text.strip()) >= 20)
