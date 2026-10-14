"""Rule-based invoice extractor.

Works offline with no API key. It reads common labels ("Invoice No", "Due Date",
"Subtotal", "VAT", "Total Due"...) and line-item rows shaped like
`description  qty  unit-price  amount`. It is deliberately conservative: when it is not
sure about a field it leaves it empty, and the validator reports what is missing.
"""
from __future__ import annotations

import re
from datetime import date

from ..schemas import ExtractedInvoice, ExtractedLineItem

SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₨": "PKR", "¥": "JPY", "₹": "INR"}
CODES = ("USD", "EUR", "GBP", "PKR", "AED", "CAD", "AUD", "INR", "JPY", "CHF")

# An amount with two decimals, optionally with a currency symbol or code and thousands separators.
AMOUNT = r"(?:[$€£₨¥₹]|(?:USD|EUR|GBP|PKR|AED|CAD|AUD|INR|CHF)\s?)?-?\d{1,3}(?:,\d{3})*\.\d{2}|(?:[$€£₨¥₹])?-?\d+\.\d{2}"
AMOUNT_RE = re.compile(AMOUNT)

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9


def parse_amount(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", text)
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _amounts(line: str) -> list[float]:
    return [a for a in (parse_amount(m) for m in AMOUNT_RE.findall(line)) if a is not None]


def detect_currency(text: str) -> str | None:
    counts = {code: text.count(sym) for sym, code in SYMBOLS.items()}
    for code in CODES:
        counts[code] = counts.get(code, 0) + len(re.findall(rf"\b{code}\b", text))
    best = max(counts.items(), key=lambda kv: kv[1])
    return best[0] if best[1] else None


def parse_date(text: str, prefer_month_first: bool = True) -> date | None:
    """Understands 2026-03-31, 31/03/2026, 03/31/2026, 14 March 2026, March 14, 2026, 14 Mar 2026."""
    s = text.strip().lower().replace(",", " ")
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", s)
    if m:
        return _safe_date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a > 12:
            return _safe_date(y, b, a)          # day first
        if b > 12:
            return _safe_date(y, a, b)          # month first
        return _safe_date(y, a, b) if prefer_month_first else _safe_date(y, b, a)
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?\s+(\d{4})\b", s)
    if m and m[2] in MONTHS:
        return _safe_date(int(m[3]), MONTHS[m[2]], int(m[1]))
    m = re.search(r"\b([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})\b", s)
    if m and m[1] in MONTHS:
        return _safe_date(int(m[3]), MONTHS[m[1]], int(m[2]))
    return None


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


INVOICE_NO_RE = re.compile(
    r"\binvoice\s*(?:no\.?|number|num\.?|#)\s*[:#.]?\s*([A-Z0-9][A-Z0-9\-/_.]*\d[A-Z0-9\-/_.]*)", re.I)
INVOICE_NO_FALLBACK_RE = re.compile(r"\b(?:inv|ref(?:erence)?)\s*(?:no\.?|#)?\s*[:#]\s*([A-Z0-9][A-Z0-9\-/_.]*\d[A-Z0-9\-/_.]*)", re.I)
DUE_LABEL_RE = re.compile(r"\b(?:due\s*date|payment\s*due|due\s*by|due\s*on|pay\s*by)\b", re.I)
ISSUE_LABEL_RE = re.compile(r"\b(?:invoice\s*date|date\s*of\s*issue|issue\s*date|issued(?:\s*on)?|date)\b", re.I)
SUBTOTAL_RE = re.compile(r"^\s*sub[\s\-]?total\b", re.I)
TAX_RE = re.compile(r"^\s*(?:sales\s*tax|tax|vat|gst|hst|pst)\b", re.I)
TOTAL_LABELS = [  # most specific first
    re.compile(r"^\s*(?:balance\s*due|amount\s*due|total\s*due|grand\s*total|total\s*amount(?:\s*due)?|amount\s*payable)\b", re.I),
    re.compile(r"^\s*total\b", re.I),
]
ITEM_HEADER_RE = re.compile(r"\b(?:description|item|service|product)s?\b.*\b(?:amount|total|price)\b", re.I)
ITEM_ROW_RE = re.compile(rf"^(?P<desc>.+?)\s+(?P<qty>\d+(?:\.\d+)?)\s+(?P<unit>{AMOUNT})\s+(?P<amt>{AMOUNT})$")
ITEM_ROW_SHORT_RE = re.compile(rf"^(?P<desc>[A-Za-z].+?)\s+(?P<amt>{AMOUNT})$")
STOP_ROW_RE = re.compile(r"^\s*(?:sub[\s\-]?total|total|tax|vat|gst|amount\s*due|balance|discount|shipping)\b", re.I)


def extract(text: str) -> ExtractedInvoice:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    currency = detect_currency(text)
    month_first = currency in (None, "USD", "CAD")  # US-style dates for dollar invoices

    inv = ExtractedInvoice(currency=currency)
    inv.vendor = _vendor(lines)
    m = INVOICE_NO_RE.search(text) or INVOICE_NO_FALLBACK_RE.search(text)
    if m:
        inv.invoice_number = m[1].rstrip(".")

    for ln in lines:
        if inv.due_date is None and DUE_LABEL_RE.search(ln):
            inv.due_date = parse_date(ln, month_first)
        elif inv.invoice_date is None and ISSUE_LABEL_RE.search(ln) and not DUE_LABEL_RE.search(ln):
            inv.invoice_date = parse_date(ln, month_first)

    inv.bill_to = _bill_to(lines)

    for ln in lines:
        amounts = _amounts(ln)
        if not amounts:
            continue
        if inv.subtotal is None and SUBTOTAL_RE.search(ln):
            inv.subtotal = amounts[-1]
        elif inv.tax is None and TAX_RE.search(ln):
            inv.tax = amounts[-1]
    for label in TOTAL_LABELS:
        for ln in lines:
            if label.search(ln) and not SUBTOTAL_RE.search(ln) and _amounts(ln):
                inv.total = _amounts(ln)[-1]
                break
        if inv.total is not None:
            break

    inv.line_items = _line_items(lines)
    return inv


def _vendor(lines: list[str]) -> str | None:
    for ln in lines[:6]:
        low = ln.lower()
        if re.fullmatch(r"(tax\s+)?invoice|receipt|bill", low):
            continue
        if "@" in ln or re.search(r"\d{3,}", ln) or len(ln) > 80:
            continue
        if re.search(r"[A-Za-z]{2}", ln):
            return re.sub(r"^(tax\s+)?invoice\s*[-:]\s*", "", ln, flags=re.I).strip()
    return None


def _bill_to(lines: list[str]) -> str | None:
    for i, ln in enumerate(lines):
        m = re.match(r"^(?:bill(?:ed)?\s*to|customer|client)\s*:?\s*(.*)$", ln, re.I)
        if not m:
            continue
        if m[1].strip():
            return m[1].strip()
        parts = []
        for nxt in lines[i + 1:i + 4]:
            if ITEM_HEADER_RE.search(nxt) or re.search(r":", nxt) or _amounts(nxt):
                break
            parts.append(nxt)
        return ", ".join(parts) or None
    return None


def _line_items(lines: list[str]) -> list[ExtractedLineItem]:
    start = next((i + 1 for i, ln in enumerate(lines) if ITEM_HEADER_RE.search(ln)), None)
    candidates = lines[start:] if start is not None else lines
    items: list[ExtractedLineItem] = []
    for ln in candidates:
        if start is not None and STOP_ROW_RE.search(ln):
            break
        m = ITEM_ROW_RE.match(ln)
        if m:
            items.append(ExtractedLineItem(description=m["desc"].strip(), quantity=float(m["qty"]),
                                           unit_price=parse_amount(m["unit"]), amount=parse_amount(m["amt"])))
        elif start is not None:
            m = ITEM_ROW_SHORT_RE.match(ln)
            if m and not STOP_ROW_RE.search(ln):
                items.append(ExtractedLineItem(description=m["desc"].strip(), amount=parse_amount(m["amt"])))
    return items
