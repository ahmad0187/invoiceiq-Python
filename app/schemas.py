"""Shapes shared by the extractors, the validator and the API."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedLineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class ExtractedInvoice(BaseModel):
    """What an extractor returns for one document. Every field is optional on purpose:
    missing data is reported by the validator instead of being invented."""

    vendor: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    bill_to: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    line_items: list[ExtractedLineItem] = Field(default_factory=list)


class Issue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str


class LineItemOut(ExtractedLineItem):
    id: int


class InvoiceOut(BaseModel):
    id: int
    filename: str
    vendor: str | None
    invoice_number: str | None
    invoice_date: date | None
    due_date: date | None
    bill_to: str | None
    currency: str | None
    subtotal: float | None
    tax: float | None
    total: float | None
    status: str
    extractor: str
    issues: list[Issue]
    line_items: list[LineItemOut]
    created_at: str


class InvoiceUpdate(BaseModel):
    """Fields a reviewer can correct by hand. Only the fields sent are changed."""

    vendor: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    bill_to: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
