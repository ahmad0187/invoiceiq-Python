from datetime import date

from app.schemas import ExtractedInvoice, ExtractedLineItem
from app.validate import status_for, validate


def make(**kw):
    base = dict(vendor="Acme", invoice_number="A-1", invoice_date=date(2026, 3, 1), due_date=date(2026, 3, 31),
                currency="USD", subtotal=100.0, tax=10.0, total=110.0,
                line_items=[ExtractedLineItem(description="Work", quantity=2, unit_price=50, amount=100)])
    base.update(kw)
    return ExtractedInvoice(**base)


def codes(inv, **kw):
    return {i.code for i in validate(inv, today=date(2026, 6, 1), **kw)}


def test_clean_invoice_passes():
    assert codes(make()) == set()
    assert status_for(validate(make(), today=date(2026, 6, 1))) == "ready"


def test_total_mismatch_is_an_error():
    issues = validate(make(total=210.0), today=date(2026, 6, 1))
    assert [i.code for i in issues] == ["total_mismatch"]
    assert issues[0].severity == "error"
    assert "+100.00" in issues[0].message


def test_line_items_must_add_up_to_subtotal():
    assert "items_mismatch" in codes(make(subtotal=90.0, total=100.0))


def test_line_math_warning():
    bad = [ExtractedLineItem(description="Work", quantity=2, unit_price=50, amount=90)]
    assert "line_math" in codes(make(line_items=bad, subtotal=90.0, total=100.0))


def test_missing_fields_and_dates():
    found = codes(make(total=None, invoice_number=None, due_date=date(2026, 2, 1)))
    assert {"missing_total", "missing_number", "due_before_issue"} <= found


def test_duplicate_and_future_date():
    assert {"duplicate", "future_date"} <= codes(make(invoice_date=date(2027, 1, 1), due_date=None), duplicate_of=7)


def test_rounding_tolerance():
    assert codes(make(tax=10.01, total=110.0)) == set()
