"""
Generate the GGPL Sales Quotation PDF in the fixed form layout used by
the official QT00102 R1 sample.
"""
from __future__ import annotations

import io
import os
import re
from decimal import Decimal, InvalidOperation

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics


PAGE_W, PAGE_H = A4

COMPANY_NAME = "GOODRICH GASKET PRIVATE LIMITED"
ADDRESS_LINES = [
    "Regd.Office & Works :",
    "40,Velichai Village,Next to: Pasupathi Eswaran Temple,",
    "Opp.Road to: Pudupakkam Anjaneyar Hill Temple,",
    "Vandalur-Kelambakkam Road,",
    "Chennai - 600127,Tamil Nadu, India.",
    "Tel:+91-44-67400004 - 99/+91-7824017150/7824017151",
    "Fax: +91-44-67400003",
    "Email:goodrichgasket@gmail.com / info@flosil.com",
    "Web: www.goodrichgasket.com / www.flosil.com",
]
PAN_LINE = (
    "IT PAN No.:AABCG2902K        CIN : U27209TN1987PTC014031        "
    "GSTIN NO : 33AABCG2902K1ZY"
)
GENERAL_TERMS = [
    '1) The "purchase" fully acknowledges that he\\she has read the "General Terms of Quote" and agrees to mention the',
    "above clauses in the Purchase Order.",
    '2) Products will be shipped only to the "Shipping Address" mentioned in the Purchase Order.',
    "3) For any dispute jurisdiction will be Chennai city civil court or Chennai High Court Only.",
    "4) The delivery quoted is subject to standard Force Majeure conditions which will be beyond our control like Lockdowns,",
    "Natural disasters, Epidemics, Pandemics Act of God, Ordinance of all relevant Government Authorities and if there",
    "is a delay on account of the above, Goodrich shall not be considered in default in the performance of its obligations.",
    "5) The above offer pricing is ONLY applicable for the offered part numbers and quantitites despatched in one lot. GGPL",
    "reserves the right to change the prices if the order is partial or dispatch in several shipments.",
    "6) Ex-stock items are subject to prior sales.",
]

BLACK = (0, 0, 0)


def _num(value, default=0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError, InvalidOperation):
        return default


def _fmt_qty(value) -> str:
    return f"{_num(value):.2f}"


def _fmt_amount(value, comma: bool = False) -> str:
    return f"{_num(value):,.2f}" if comma else f"{_num(value):.2f}"


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\r", "\n")).strip()


def _top(y: float) -> float:
    return PAGE_H - y


def _draw(c: canvas.Canvas, x: float, top: float, text: str, size=8, bold=False, align="left"):
    font = "Helvetica-Bold" if bold else "Helvetica"
    c.setFont(font, size)
    text = str(text or "")
    y = _top(top)
    if align == "right":
        c.drawRightString(x, y, text)
    elif align == "center":
        c.drawCentredString(x, y, text)
    else:
        c.drawString(x, y, text)


def _wrap(text: str, width: float, font="Helvetica", size=8) -> list[str]:
    words = _clean(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    line = ""
    for word in words:
        trial = word if not line else f"{line} {word}"
        if pdfmetrics.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _draw_wrapped(c, x, top, text, width, size=8, leading=11, bold=False, max_lines=None):
    font = "Helvetica-Bold" if bold else "Helvetica"
    lines = _wrap(text, width, font, size)
    if max_lines:
        lines = lines[:max_lines]
    for i, line in enumerate(lines):
        _draw(c, x, top + i * leading, line, size=size, bold=bold)
    return len(lines)


def _draw_header(c: canvas.Canvas, quote_data: dict, logo_path: str | None, show_pan: bool = True):
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(0.4)

    if logo_path and os.path.exists(logo_path):
        try:
            image = ImageReader(logo_path)
            iw, ih = image.getSize()
            w = 88
            h = w * ih / iw
            if h > 95:
                h = 95
                w = h * iw / ih
            c.drawImage(image, 25, _top(130), width=w, height=h, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    _draw(c, 235, 36, COMPANY_NAME, size=10.5, bold=True, align="center")
    for i, line in enumerate(ADDRESS_LINES):
        _draw(c, 135, 49 + i * 12, line, size=8)

    _draw(c, 471, 40, "SALES QUOTATION", size=8.5, bold=True, align="center")
    _draw(c, 391, 65, "QUOTE :", size=8, bold=True)
    _draw(c, 391, 79, quote_data.get("quote_no", ""), size=8)
    _draw(c, 393, 99, "DATE :", size=8, bold=True)
    _draw(c, 431, 99, quote_data.get("quote_date", ""), size=8)
    _draw(c, 392, 115, "REVNO:", size=8, bold=True)
    _draw(c, 433, 115, quote_data.get("rev_no", "0"), size=8)
    _draw(c, 392, 133, "REVDATE:", size=8, bold=True)
    _draw(c, 444, 133, quote_data.get("rev_date", ""), size=8)

    c.line(20, _top(148), 576, _top(148))
    if show_pan:
        _draw(c, 31, 163, "IT PAN No.:AABCG2902K", size=7.5)
        _draw(c, 216, 163, "CIN : U27209TN1987PTC014031", size=7.5)
        _draw(c, 424, 163, "GSTIN NO : 33AABCG2902K1ZY", size=7.5)


def _draw_buyer_block(c: canvas.Canvas, quote_data: dict):
    _draw(c, 25, 180, "Name & Address of the Buyer :", size=8)
    _draw(c, 449, 179, "GGPL/MKT/REC03", size=8)

    buyer_lines = str(quote_data.get("buyer_name_address", "")).splitlines()
    buyer_tops = [194, 211, 228, 244, 260]
    for top, line in zip(buyer_tops, buyer_lines):
        _draw(c, 26, top, line, size=8)

    label_x, value_x = 24, 109
    right_label_x, right_value_x = 322, 387
    rows = [
        (266, "Customer Enq No", quote_data.get("customer_enq_no", ""), "Followed By", quote_data.get("rep_name", "")),
        (285, "Kind Attention", quote_data.get("attention", ""), "Designation", quote_data.get("rep_designation", "")),
        (305, "Designation", quote_data.get("designation", ""), "Contact No", quote_data.get("rep_contact", "")),
        (324, "Contact No", quote_data.get("contact_no", ""), "Email ID", quote_data.get("rep_email", "")),
        (342, "Email ID", quote_data.get("email", ""), "", ""),
    ]
    for top, label, value, rlabel, rvalue in rows:
        _draw(c, label_x, top, label, size=8)
        _draw(c, 101, top, ":", size=8)
        value_width = 285 if label == "Customer Enq No" else 205
        value_lines = 1 if label == "Customer Enq No" else 2
        _draw_wrapped(c, value_x, top, value, value_width, size=8, leading=9, max_lines=value_lines)
        if rlabel:
            _draw(c, right_label_x, top, rlabel, size=8)
            _draw(c, 379, top, ":", size=8)
            _draw_wrapped(c, right_value_x, top, rvalue, 160, size=8, leading=9, max_lines=2)


ITEM_COLS = [20, 45.5, 83.8, 177.8, 345.5, 404.8, 437.8, 503.8, 575.2]


def _draw_item_header(c: canvas.Canvas, top=363):
    c.setLineWidth(0.35)
    c.line(20, _top(358), 575.2, _top(358))
    c.line(20, _top(391), 575.2, _top(391))
    for x in ITEM_COLS:
        c.line(x, _top(358), x, _top(687))

    headers = [
        (33, top, "Sl.", "No."),
        (64, top, "Cust", "SL.NO"),
        (131, top, "Customer Item", "Code"),
        (261, top, "Material Description", ""),
        (375, top, "Quantity", ""),
        (421, top, "UOM", ""),
        (471, top, "Unit Price", "INR"),
        (537, top, "TOTAL PRICE", "INR"),
    ]
    for x, y, a, b in headers:
        _draw(c, x, y, a, size=8, bold=True, align="center")
        if b:
            _draw(c, x, y + 13, b, size=8, bold=True, align="center")


def _item_description(item: dict) -> str:
    if item.get("status") == "regret":
        return "REGRET - CANNOT PRODUCE"
    return item.get("ggpl_description") or item.get("description") or ""


def _draw_items_page(c: canvas.Canvas, items: list[dict], quote_data: dict, start: int):
    _draw_buyer_block(c, quote_data)
    _draw_item_header(c)
    unit_prices = quote_data.get("unit_prices", [])

    y = 405
    idx = start
    while idx < len(items) and y < 660:
        item = items[idx]
        qty = _num(item.get("quantity"))
        unit = _num(unit_prices[idx] if idx < len(unit_prices) else 0)
        total = qty * unit
        desc_lines = _wrap(_item_description(item), 158, "Helvetica", 8)[:4]
        row_h = max(32, 11 * len(desc_lines) + 10)

        if y + row_h > 682:
            break

        _draw(c, 34, y + 6, str(idx + 1), size=8, align="center")
        for j, line in enumerate(desc_lines):
            _draw(c, 181, y + 6 + j * 11, line, size=8)
        _draw(c, 386, y + 6, _fmt_qty(qty), size=8, align="right")
        _draw(c, 421, y + 6, item.get("uom") or "NOS", size=8, align="center")
        _draw(c, 490, y + 6, _fmt_amount(unit), size=8, align="right")
        _draw(c, 573, y + 6, _fmt_amount(total), size=8, align="right")
        y += row_h
        idx += 1

    c.line(20, _top(687), 575.2, _top(687))
    if idx < len(items):
        _draw(c, 298, 705, "PAGE TURN OVER", size=8, bold=True, align="center")
    else:
        _draw(c, 298, 705, "PAGE TURN OVER", size=8, bold=True, align="center")
    return idx


def _totals(items: list[dict], quote_data: dict):
    unit_prices = quote_data.get("unit_prices", [])
    total_qty = Decimal("0")
    subtotal = Decimal("0")
    for idx, item in enumerate(items):
        qty = Decimal(str(_num(item.get("quantity"))))
        unit = Decimal(str(_num(unit_prices[idx] if idx < len(unit_prices) else 0)))
        total_qty += qty
        subtotal += qty * unit
    discount_pct = Decimal(str(_num(quote_data.get("discount_pct"))))
    discount_amt = subtotal * discount_pct / Decimal("100")
    taxable = subtotal - discount_amt
    gst_pct = Decimal(str(_num(quote_data.get("gst_pct"), 18)))
    gst_amt = taxable * gst_pct / Decimal("100")
    return float(total_qty), float(subtotal), float(discount_amt), float(taxable), float(gst_amt), float(taxable + gst_amt)


def _gst_rows(quote_data: dict, gst_amt: float):
    gst_type = quote_data.get("gst_type", "IGST")
    gst_pct = _num(quote_data.get("gst_pct"), 18)
    if gst_type == "CGST+SGST":
        half = gst_amt / 2
        return [("CGST", gst_pct / 2, half), ("SGST", gst_pct / 2, half), ("IGST", 0, 0), ("UGST", 0, 0)]
    if gst_type == "UGST":
        return [("CGST", 0, 0), ("SGST", 0, 0), ("IGST", 0, 0), ("UGST", gst_pct, gst_amt)]
    return [("CGST", 0, 0), ("SGST", 0, 0), ("IGST", gst_pct, gst_amt), ("UGST", 0, 0)]


def _draw_terms_page(c: canvas.Canvas, items: list[dict], quote_data: dict):
    total_qty, subtotal, _discount_amt, _taxable, gst_amt, grand_total = _totals(items, quote_data)

    _draw(c, 352, 167, "Total Qty :", size=8, bold=True, align="right")
    _draw(c, 431, 167, _fmt_qty(total_qty), size=8, align="right")
    _draw(c, 501, 167, "Total Amount :", size=8, bold=True, align="right")
    _draw(c, 552, 167, _fmt_amount(subtotal, comma=True), size=8, align="right")

    _draw(c, 32, 182, "Terms & Conditions :", size=7.5, bold=True)

    terms = [
        ("1. Price Basis", quote_data.get("price_basis", "FOR BASIS")),
        ("2. Validity", f"{quote_data.get('validity_days', '7')} DAYS"),
        ("3. Packing &\nforwarding charges", quote_data.get("packing", "INCLUSIVE")),
        ("4. Freight", quote_data.get("freight", "INCLUSIVE")),
        ("5. Taxes and Duties", f"Taxes and duties shall be paid at actuals as applicable at the time of shipment-present GST is {_num(quote_data.get('gst_pct'), 18):g}%"),
        ("6. Payment Terms", quote_data.get("payment_terms", "30% ADVANCE & 70% BALANCE BEFORE DISPATCH OF MATERIAL")),
        ("7. Bank Charges", quote_data.get("bank_charges", "Bank Charges at the customer side, shall to be customer account, unless agreed prior by Goodrich .")),
        ("8. Delivery Terms", quote_data.get("delivery", "")),
        ("9. Insurance", quote_data.get("insurance", "TO YOUR ACCOUNT")),
        ("10. Inspection", quote_data.get("inspection", "")),
        ("11. HSN Code", quote_data.get("hsn_code", "84841010")),
        ("12. LD Clause", quote_data.get("ld_clause", "Not Applicable")),
        ("13. Cancellation", quote_data.get("cancellation", "Products are manufactured on order and hence Goodrich will not be able to accept cancellation of order or reduction in quantity. The product shall to invoiced as per the PO.")),
        ("14. Minimum Order Value", quote_data.get("min_order_value", "Minimum Order Value is INR 10,000,No order can be processed below the same. If it is processed, INR 3500 shall be paid extra on document charges.")),
    ]

    top = 196
    for label, value in terms:
        label_lines = str(label).splitlines()
        for i, line in enumerate(label_lines):
            _draw(c, 30, top + i * 10, line, size=8)
        _draw(c, 148, top, ":", size=8)
        used = _draw_wrapped(c, 166, top, value, 210, size=8, leading=10, max_lines=4)
        top += max(14, 10 * max(len(label_lines), used))

    gst_top = 202
    for name, pct, amount in _gst_rows(quote_data, gst_amt):
        _draw(c, 397, gst_top, name, size=8)
        _draw(c, 482, gst_top, f"{pct:.2f}", size=8, align="right")
        _draw(c, 497, gst_top, "%", size=8)
        _draw(c, 569, gst_top, _fmt_amount(amount, comma=True), size=8, align="right")
        gst_top += 18
    _draw(c, 501, gst_top + 4, "TOTAL", size=8, bold=True, align="right")
    _draw(c, 569, gst_top + 4, _fmt_amount(grand_total, comma=True), size=8, bold=True, align="right")

    top += 8
    _draw(c, 274, top, "Part of Quote", size=8, align="center")
    top += 18
    _draw(c, 31, top, "Technical Notes :", size=8, bold=True)
    top += 13
    tech_notes = quote_data.get("technical_notes") or (
        "1. Cerifications : MTC to EN10204-3.1 for metallic parts and EN10204-2.1 for non-metallic.\n"
        "2. Testing Charges for gasket will be extra at actuals for tests other than compression & sealablity test and Chemical test certificate."
    )
    for raw in str(tech_notes).splitlines():
        for line in _wrap(raw, 535, "Helvetica", 8):
            _draw(c, 31, top, line, size=8)
            top += 10

    top += 8
    _draw(c, 31, top, "GENERAL TERMS OF QUOTATION:", size=8, bold=True)
    top += 12
    for line in GENERAL_TERMS:
        _draw(c, 31, top, line, size=7.5)
        top += 10

    _draw(c, 472, 744, "For Goodrich Gasket Pvt. Ltd.", size=8, bold=True, align="center")
    _draw(c, 472, 784, "Authorised Signatory", size=8, bold=True, align="center")
    _draw(c, 30, 820, "Record Created on.:        Revision No :03        Revision Date : 10.10.2019", size=7)
    _draw(c, 298, 835, "This is a Computer Generated Document Signature not Required", size=7, align="center")


def build_quotation_pdf(
    items: list[dict],
    quote_data: dict,
    logo_path: str | None = None,
) -> bytes:
    """Return PDF bytes for the final GGPL sales quotation."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Quotation {quote_data.get('quote_no', '')}")
    c.setAuthor("Goodrich Gasket Pvt. Ltd.")

    idx = 0
    if not items:
        items = []

    while True:
        _draw_header(c, quote_data, logo_path)
        idx = _draw_items_page(c, items, quote_data, idx)
        c.showPage()
        if idx >= len(items):
            break

    _draw_header(c, quote_data, logo_path, show_pan=False)
    _draw_terms_page(c, items, quote_data)
    c.save()
    return buf.getvalue()
