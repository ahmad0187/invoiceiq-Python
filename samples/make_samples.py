"""Generates the fictional sample invoices in samples/ (different layouts on purpose).

Run: python samples/make_samples.py
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parent
ss = getSampleStyleSheet()
H = ParagraphStyle("h", parent=ss["Heading1"], fontSize=20, spaceAfter=2)
P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=10, leading=14)
SMALL = ParagraphStyle("s", parent=P, fontSize=8.5, textColor=colors.grey)


def money(v: float, sym: str) -> str:
    return f"{sym}{v:,.2f}"


def items_table(rows, sym, widths):
    data = [["Description", "Qty", "Unit Price", "Amount"]]
    for d, q, u in rows:
        data.append([d, f"{q:g}", money(u, sym), money(q * u, sym)])
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def totals_table(lines, widths):
    t = Table(lines, colWidths=widths, hAlign="RIGHT")
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 11),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
    ]))
    return t


def build(name, size, story):
    SimpleDocTemplate(str(OUT / name), pagesize=size, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm, title=name).build(story)
    print("wrote", name)


# 1. Clean US invoice, ISO dates, 8% sales tax.
rows = [("Cloud VPS - 4 vCPU / 8 GB (March)", 2, 48.00), ("Managed backups", 2, 9.50), ("SSL certificate (1 year)", 1, 69.00)]
sub = sum(q * u for _, q, u in rows); tax = round(sub * 0.08, 2)
build("01-acme-cloud-hosting.pdf", LETTER, [
    Paragraph("Acme Cloud Hosting LLC", H),
    Paragraph("500 Market Street, Suite 210, San Francisco, CA 94105 · billing@acmecloud.example", SMALL),
    Spacer(1, 10), Paragraph("<b>INVOICE</b>", P),
    Paragraph("Invoice Number: ACH-2026-0412", P),
    Paragraph("Invoice Date: 2026-03-31", P),
    Paragraph("Due Date: 2026-04-30", P), Spacer(1, 8),
    Paragraph("<b>Bill To:</b><br/>Bright Smile Dental<br/>214 Maple Avenue, Suite 3", P), Spacer(1, 12),
    items_table(rows, "$", [95 * mm, 18 * mm, 30 * mm, 32 * mm]), Spacer(1, 8),
    totals_table([["Subtotal", money(sub, "$")], ["Sales Tax (8%)", money(tax, "$")], ["Total Due", money(sub + tax, "$")]], [40 * mm, 32 * mm]),
])

# 2. EU agency invoice, long dates, 20% VAT, euro amounts.
rows = [("Brand identity workshop", 1, 1200.00), ("Logo design - 3 concepts", 1, 1800.00), ("Brand guidelines document", 1, 950.00), ("Social media templates", 12, 45.00)]
sub = sum(q * u for _, q, u in rows); tax = round(sub * 0.20, 2)
build("02-brightline-studio.pdf", A4, [
    Paragraph("Brightline Studio", H),
    Paragraph("Keizersgracht 120, 1015 CW Amsterdam · VAT NL8541.22.090.B01", SMALL), Spacer(1, 14),
    Table([["Invoice #", "BLS-118"], ["Date of issue", "14 March 2026"], ["Payment due", "28 March 2026"]],
          colWidths=[35 * mm, 50 * mm], style=[("FONT", (0, 0), (-1, -1), "Helvetica", 10)]), Spacer(1, 8),
    Paragraph("<b>Bill To:</b> Northwind Coffee Roasters, Utrecht", P), Spacer(1, 12),
    items_table(rows, "€", [92 * mm, 16 * mm, 32 * mm, 34 * mm]), Spacer(1, 8),
    totals_table([["Subtotal", money(sub, "€")], ["VAT 20%", money(tax, "€")], ["Total", money(sub + tax, "€")]], [36 * mm, 34 * mm]),
    Spacer(1, 16), Paragraph("Please pay by bank transfer to IBAN NL91 ABNA 0417 1643 00 within 14 days.", SMALL),
])

# 3. Office supplies, many line items, US month-name dates, no tax.
rows = [("A4 copy paper, box of 5 reams", 4, 32.50), ("Black ballpoint pens (50 pack)", 2, 14.99), ("Stapler, heavy duty", 1, 27.00),
        ("Whiteboard markers (12 pack)", 3, 11.25), ("Desk organizer", 2, 18.40), ("Printer toner HP 58A", 2, 89.99), ("Sticky notes (24 pads)", 1, 16.75)]
sub = sum(q * u for _, q, u in rows)
build("03-northwind-office-supplies.pdf", LETTER, [
    Paragraph("Northwind Office Supplies Inc.", H), Paragraph("12 Commerce Way, Austin, TX 78701", SMALL), Spacer(1, 10),
    Paragraph("INVOICE NO: NOS-55821", P), Paragraph("Invoice Date: April 2, 2026", P), Paragraph("Due Date: May 2, 2026", P), Spacer(1, 6),
    Paragraph("Bill To: Kestrel Logistics Ltd, 8 Harbour Road, Bristol", P), Spacer(1, 12),
    items_table(rows, "$", [95 * mm, 18 * mm, 30 * mm, 32 * mm]), Spacer(1, 8),
    totals_table([["Subtotal", money(sub, "$")], ["Tax", money(0, "$")], ["Amount Due", money(sub, "$")]], [40 * mm, 32 * mm]),
])

# 4. UK logistics invoice with a deliberate arithmetic error in the total (validator should flag it).
rows = [("Pallet delivery Bristol to Leeds", 3, 145.00), ("Tail-lift surcharge", 3, 25.00), ("Fuel surcharge", 1, 38.60)]
sub = sum(q * u for _, q, u in rows); tax = round(sub * 0.20, 2)
build("04-kestrel-logistics-error.pdf", A4, [
    Paragraph("Kestrel Logistics Ltd", H), Paragraph("8 Harbour Road, Bristol BS1 5TY · VAT GB 293 4417 08", SMALL), Spacer(1, 10),
    Paragraph("Invoice No: KL/2026/0098", P), Paragraph("Invoice Date: 18/03/2026", P), Paragraph("Due Date: 17/04/2026", P), Spacer(1, 6),
    Paragraph("Bill To: Acme Cloud Hosting LLC", P), Spacer(1, 12),
    items_table(rows, "£", [95 * mm, 18 * mm, 30 * mm, 32 * mm]), Spacer(1, 8),
    totals_table([["Subtotal", money(sub, "£")], ["VAT (20%)", money(tax, "£")], ["Balance Due", money(sub + tax + 100, "£")]], [40 * mm, 32 * mm]),
])
