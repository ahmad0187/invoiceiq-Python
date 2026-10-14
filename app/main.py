"""InvoiceIQ: upload invoices, extract the data, catch errors, export to Excel."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from . import config, export
from .db import get_session, init_db
from .extract.pdf_text import PdfReadError
from .extract.pipeline import NoTextError, active_extractor, run
from .models import Invoice, LineItem
from .schemas import ExtractedInvoice, ExtractedLineItem, InvoiceOut, InvoiceUpdate, Issue
from .validate import status_for, validate

APP_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="InvoiceIQ", version="1.0.0", lifespan=lifespan,
              description="Extract, validate and export invoice data from PDFs.")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


# ------------------------------------------------------------------ helpers
def _to_out(inv: Invoice) -> InvoiceOut:
    return InvoiceOut(
        id=inv.id, filename=inv.filename, vendor=inv.vendor, invoice_number=inv.invoice_number,
        invoice_date=inv.invoice_date, due_date=inv.due_date, bill_to=inv.bill_to, currency=inv.currency,
        subtotal=inv.subtotal, tax=inv.tax, total=inv.total, status=inv.status, extractor=inv.extractor,
        issues=[Issue(**i) for i in inv.issues or []],
        line_items=[{"id": li.id, "description": li.description, "quantity": li.quantity,
                     "unit_price": li.unit_price, "amount": li.amount} for li in inv.line_items],
        created_at=inv.created_at.isoformat(),
    )


def _as_extracted(inv: Invoice) -> ExtractedInvoice:
    return ExtractedInvoice(
        vendor=inv.vendor, invoice_number=inv.invoice_number, invoice_date=inv.invoice_date,
        due_date=inv.due_date, bill_to=inv.bill_to, currency=inv.currency, subtotal=inv.subtotal,
        tax=inv.tax, total=inv.total,
        line_items=[ExtractedLineItem(description=li.description, quantity=li.quantity,
                                      unit_price=li.unit_price, amount=li.amount) for li in inv.line_items],
    )


def _find_duplicate(session: Session, vendor: str | None, number: str | None, exclude_id: int | None = None) -> int | None:
    if not vendor or not number:
        return None
    q = select(Invoice.id).where(Invoice.vendor == vendor, Invoice.invoice_number == number)
    if exclude_id is not None:
        q = q.where(Invoice.id != exclude_id)
    return session.exec(q.order_by(Invoice.id)).first()


def _revalidate(session: Session, inv: Invoice) -> None:
    dup = _find_duplicate(session, inv.vendor, inv.invoice_number, exclude_id=inv.id)
    issues = validate(_as_extracted(inv), duplicate_of=dup)
    inv.issues = [i.model_dump() for i in issues]
    if inv.status != "approved" or issues:
        inv.status = status_for(issues)


def _get(session: Session, invoice_id: int) -> Invoice:
    inv = session.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return inv


# ------------------------------------------------------------------ pages
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"extractor": active_extractor()})


# ------------------------------------------------------------------ API
@app.get("/api/health")
def health():
    return {"ok": True, "extractor": active_extractor()}


@app.post("/api/invoices", response_model=list[InvoiceOut], status_code=201)
async def upload(files: list[UploadFile] = File(...), session: Session = Depends(get_session)):
    if len(files) > 20:
        raise HTTPException(400, "Upload up to 20 files at a time.")
    results = []
    for f in files:
        data = await f.read()
        name = Path(f.filename or "invoice.pdf").name[:150]
        if not data.startswith(b"%PDF-"):
            raise HTTPException(400, f"{name} is not a PDF.")
        if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"{name} is larger than {config.MAX_UPLOAD_MB} MB.")

        stored = config.UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"
        stored.write_bytes(data)
        try:
            result = run(stored)
        except (PdfReadError, NoTextError) as exc:
            stored.unlink(missing_ok=True)
            raise HTTPException(422, f"{name}: {exc}") from exc

        x = result.invoice
        inv = Invoice(filename=name, stored_path=str(stored), extractor=result.extractor,
                      **x.model_dump(exclude={"line_items"}))
        inv.line_items = [LineItem(**li.model_dump()) for li in x.line_items]
        dup = _find_duplicate(session, x.vendor, x.invoice_number)
        issues = validate(x, duplicate_of=dup)
        inv.issues = [i.model_dump() for i in issues]
        inv.status = status_for(issues)
        session.add(inv)
        session.commit()
        session.refresh(inv)
        results.append(_to_out(inv))
    return results


@app.get("/api/invoices", response_model=list[InvoiceOut])
def list_invoices(status: str | None = Query(None, pattern="^(ready|needs_review|approved)$"),
                  q: str | None = None, session: Session = Depends(get_session)):
    query = select(Invoice).order_by(Invoice.id.desc())
    if status:
        query = query.where(Invoice.status == status)
    if q:
        like = f"%{q}%"
        query = query.where((Invoice.vendor.ilike(like)) | (Invoice.invoice_number.ilike(like)))
    return [_to_out(i) for i in session.exec(query).all()]


@app.get("/api/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, session: Session = Depends(get_session)):
    return _to_out(_get(session, invoice_id))


@app.patch("/api/invoices/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: int, body: InvoiceUpdate, session: Session = Depends(get_session)):
    inv = _get(session, invoice_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)
    inv.status = "needs_review"
    _revalidate(session, inv)
    session.add(inv)
    session.commit()
    session.refresh(inv)
    return _to_out(inv)


@app.post("/api/invoices/{invoice_id}/approve", response_model=InvoiceOut)
def approve(invoice_id: int, session: Session = Depends(get_session)):
    inv = _get(session, invoice_id)
    errors = [i for i in inv.issues or [] if i["severity"] == "error"]
    if errors:
        raise HTTPException(409, "Fix the errors on this invoice before approving it.")
    inv.status = "approved"
    session.add(inv)
    session.commit()
    session.refresh(inv)
    return _to_out(inv)


@app.delete("/api/invoices/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: int, session: Session = Depends(get_session)):
    inv = _get(session, invoice_id)
    Path(inv.stored_path).unlink(missing_ok=True)
    session.delete(inv)
    session.commit()
    return Response(status_code=204)


@app.get("/api/invoices/{invoice_id}/file", include_in_schema=False)
def invoice_file(invoice_id: int, session: Session = Depends(get_session)):
    inv = _get(session, invoice_id)
    return FileResponse(inv.stored_path, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{inv.filename}"'})


@app.get("/api/export")
def export_invoices(format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
                    status: str | None = Query(None, pattern="^(ready|needs_review|approved)$"),
                    session: Session = Depends(get_session)):
    query = select(Invoice).order_by(Invoice.id)
    if status:
        query = query.where(Invoice.status == status)
    invoices = session.exec(query).all()
    if format == "csv":
        return Response(export.to_csv(invoices), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="invoices.csv"'})
    return Response(export.to_xlsx(invoices),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="invoices.xlsx"'})
