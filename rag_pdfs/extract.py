from __future__ import annotations

from pathlib import Path
import re
from collections.abc import Iterable

from .models import ElementKind, PdfElement


CAPTION_RE = re.compile(
    r"^\s*(fig(?:ure)?\.?|table|chart|scheme|图|表)\s*"
    r"([0-9]+|[ivxlcdm]+|[一二三四五六七八九十]+)?[\s\-.:：、)]",
    re.IGNORECASE,
)
SECTION_RE = re.compile(
    r"^\s*((#{1,6}\s+)|([0-9]+(\.[0-9]+){0,4}\s+)|"
    r"((chapter|section)\s+[0-9ivxlcdm]+[\s:.-]))",
    re.IGNORECASE,
)


def load_pdf_elements(pdf_path: Path | str) -> list[PdfElement]:
    """Extract text lines from a PDF and classify likely headings/captions."""

    path = Path(pdf_path).expanduser().resolve()
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install the pdf-rag extra to read PDFs: uv sync --extra pdf-rag") from exc

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return elements_from_text_pages(pages, source=str(path))


def elements_from_text_pages(pages: Iterable[str], source: str | None = None) -> list[PdfElement]:
    elements: list[PdfElement] = []
    order = 0
    for page_number, page_text in enumerate(pages, start=1):
        for raw_line in page_text.splitlines():
            text = " ".join(raw_line.split())
            if not text:
                continue
            elements.append(
                PdfElement(
                    page=page_number,
                    order=order,
                    text=text,
                    kind=classify_line(text),
                    source=source,
                )
            )
            order += 1
    return elements


def classify_line(text: str) -> ElementKind:
    if CAPTION_RE.match(text):
        return "caption"
    if _looks_like_heading(text):
        return "heading"
    return "body"


def _looks_like_heading(text: str) -> bool:
    if len(text) > 120:
        return False
    if SECTION_RE.match(text):
        return True
    alpha = re.sub(r"[^A-Za-z]", "", text)
    return len(alpha) >= 4 and alpha.upper() == alpha
