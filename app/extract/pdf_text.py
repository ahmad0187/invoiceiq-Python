"""Pulls the text layer out of a PDF."""
from __future__ import annotations

import logging
from pathlib import Path

import pdfplumber

# pdfminer logs a harmless warning for every page without a CropBox.
logging.getLogger("pdfminer").setLevel(logging.ERROR)


class PdfReadError(Exception):
    pass


def extract_text(path: str | Path, max_pages: int = 20) -> tuple[str, int]:
    """Returns (text of up to `max_pages` pages, total page count)."""
    try:
        with pdfplumber.open(str(path)) as pdf:
            pages = pdf.pages
            text = "\n".join((p.extract_text() or "") for p in pages[:max_pages])
            return text, len(pages)
    except Exception as exc:  # pdfplumber raises several unrelated exception types
        raise PdfReadError("This file could not be read as a PDF.") from exc
