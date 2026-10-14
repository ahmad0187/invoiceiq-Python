"""Database tables (SQLModel on SQLite by default; any SQLAlchemy URL works)."""
# Note: no `from __future__ import annotations` here; SQLModel needs real types for relationships.
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Invoice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    filename: str
    stored_path: str
    vendor: str | None = Field(default=None, index=True)
    invoice_number: str | None = Field(default=None, index=True)
    invoice_date: date | None = None
    due_date: date | None = None
    bill_to: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    # ready | needs_review | approved
    status: str = Field(default="needs_review", index=True)
    extractor: str = "rules"
    issues: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)

    line_items: list["LineItem"] = Relationship(
        back_populates="invoice", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class LineItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None

    invoice: Invoice | None = Relationship(back_populates="line_items")
