"""Chooses an extractor and runs it on one PDF."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .. import config
from ..schemas import ExtractedInvoice
from . import llm, rules
from .pdf_text import extract_text

log = logging.getLogger("invoiceiq")


class NoTextError(Exception):
    pass


@dataclass
class ExtractionResult:
    invoice: ExtractedInvoice
    extractor: str
    pages: int


def active_extractor() -> str:
    if config.EXTRACTOR == "rules":
        return "rules"
    if config.EXTRACTOR == "claude" or (config.EXTRACTOR == "auto" and config.ANTHROPIC_API_KEY):
        return "claude"
    return "rules"


def run(path: str | Path) -> ExtractionResult:
    text, pages = extract_text(path)
    if len(text.strip()) < 30:
        raise NoTextError("No selectable text found. This looks like a scanned image; run OCR first.")

    if active_extractor() == "claude":
        try:
            return ExtractionResult(llm.extract(text), "claude", pages)
        except Exception as exc:  # network, quota, or schema problem: never lose the upload
            log.warning("Claude extraction failed, using rules instead: %s", exc)
            return ExtractionResult(rules.extract(text), "rules (fallback)", pages)
    return ExtractionResult(rules.extract(text), "rules", pages)
