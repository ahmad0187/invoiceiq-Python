from datetime import date

import pytest

from app.extract.pdf_text import extract_text
from app.extract.rules import extract, parse_amount, parse_date
from tests.conftest import sample


@pytest.mark.parametrize("text,expected", [
    ("Invoice Date: 2026-03-31", date(2026, 3, 31)),
    ("Date of issue 14 March 2026", date(2026, 3, 14)),
    ("Invoice Date: April 2, 2026", date(2026, 4, 2)),
    ("Due: 18/03/2026", date(2026, 3, 18)),           # day > 12, so day-first
    ("Due: 03/04/2026", date(2026, 3, 4)),            # ambiguous, month-first by default
    ("14th Sept 2026", date(2026, 9, 14)),
    ("no date here", None),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_parse_date_day_first_hint():
    assert parse_date("03/04/2026", prefer_month_first=False) == date(2026, 4, 3)


@pytest.mark.parametrize("text,expected", [("$1,200.00", 1200.0), ("€45.50", 45.5), ("GBP 758.32", 758.32), ("", None)])
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


EXPECTED = {
    "01": dict(vendor="Acme Cloud Hosting LLC", invoice_number="ACH-2026-0412", invoice_date=date(2026, 3, 31),
               due_date=date(2026, 4, 30), currency="USD", subtotal=184.0, tax=14.72, total=198.72, items=3),
    "02": dict(vendor="Brightline Studio", invoice_number="BLS-118", invoice_date=date(2026, 3, 14),
               due_date=date(2026, 3, 28), currency="EUR", subtotal=4490.0, tax=898.0, total=5388.0, items=4),
    "03": dict(vendor="Northwind Office Supplies Inc.", invoice_number="NOS-55821", invoice_date=date(2026, 4, 2),
               due_date=date(2026, 5, 2), currency="USD", subtotal=454.26, tax=0.0, total=454.26, items=7),
    "04": dict(vendor="Kestrel Logistics Ltd", invoice_number="KL/2026/0098", invoice_date=date(2026, 3, 18),
               due_date=date(2026, 4, 17), currency="GBP", subtotal=548.6, tax=109.72, total=758.32, items=3),
}


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_extracts_sample_invoices(key):
    text, pages = extract_text(sample(key))
    inv = extract(text)
    exp = dict(EXPECTED[key])
    assert len(inv.line_items) == exp.pop("items")
    for field, value in exp.items():
        assert getattr(inv, field) == value, field
    assert pages == 1


def test_line_item_with_numbers_in_description():
    inv = extract(extract_text(sample("01"))[0])
    first = inv.line_items[0]
    assert first.description == "Cloud VPS - 4 vCPU / 8 GB (March)"
    assert (first.quantity, first.unit_price, first.amount) == (2, 48.0, 96.0)
