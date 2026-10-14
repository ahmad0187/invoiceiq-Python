"""Checks that catch extraction mistakes and real billing errors before anyone pays."""
from __future__ import annotations

from datetime import date, timedelta

from . import config
from .schemas import ExtractedInvoice, Issue


def _fmt(v: float, currency: str | None) -> str:
    return f"{currency + ' ' if currency else ''}{v:,.2f}"


def validate(inv: ExtractedInvoice, duplicate_of: int | None = None, today: date | None = None) -> list[Issue]:
    today = today or date.today()
    tol = config.AMOUNT_TOLERANCE
    cur = inv.currency
    issues: list[Issue] = []

    def add(code: str, severity: str, message: str) -> None:
        issues.append(Issue(code=code, severity=severity, message=message))

    if inv.total is None:
        add("missing_total", "error", "No total amount found.")
    if not inv.invoice_number:
        add("missing_number", "warning", "No invoice number found.")
    if not inv.vendor:
        add("missing_vendor", "warning", "No vendor name found.")
    if inv.invoice_date is None:
        add("missing_date", "warning", "No invoice date found.")

    amounts = [li.amount for li in inv.line_items if li.amount is not None]
    if amounts:
        items_sum = round(sum(amounts), 2)
        target, label = (inv.subtotal, "subtotal") if inv.subtotal is not None else (
            (inv.total, "total") if inv.tax in (None, 0) else (None, ""))
        if target is not None and abs(items_sum - target) > tol:
            add("items_mismatch", "error",
                f"Line items add up to {_fmt(items_sum, cur)}, but the {label} says {_fmt(target, cur)}.")

    for li in inv.line_items:
        if None not in (li.quantity, li.unit_price, li.amount):
            expected = round(li.quantity * li.unit_price, 2)
            if abs(expected - li.amount) > tol:
                add("line_math", "warning",
                    f"'{li.description}': {li.quantity:g} × {li.unit_price:,.2f} = {expected:,.2f}, not {li.amount:,.2f}.")

    if None not in (inv.subtotal, inv.total):
        expected_total = round(inv.subtotal + (inv.tax or 0), 2)
        if abs(expected_total - inv.total) > tol:
            diff = round(inv.total - expected_total, 2)
            add("total_mismatch", "error",
                f"Subtotal + tax = {_fmt(expected_total, cur)}, but the total says {_fmt(inv.total, cur)} "
                f"({'+' if diff > 0 else ''}{diff:,.2f}).")

    if inv.invoice_date and inv.due_date and inv.due_date < inv.invoice_date:
        add("due_before_issue", "warning", "The due date is before the invoice date.")
    if inv.invoice_date and inv.invoice_date > today + timedelta(days=1):
        add("future_date", "warning", "The invoice date is in the future.")
    if duplicate_of is not None:
        add("duplicate", "warning", f"Possible duplicate: invoice #{duplicate_of} has the same vendor and number.")

    return issues


def status_for(issues: list[Issue]) -> str:
    return "needs_review" if issues else "ready"
