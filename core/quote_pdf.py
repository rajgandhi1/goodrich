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
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


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

    # ── Layout constants ────────────────────────────────────────────────────
    LEFT,  RIGHT  = 20,  575          # page left / right edges
    H_TOP, H_BTM  = 10,  148          # "top" coords of header top / bottom
    DIVX          = 377               # vertical divider: left section | SALES QUOTATION
    LOGO_X        = 25                # logo left edge
    ADDR_X        = 116               # address text left edge (right of logo)

    # ── Outer border box (full header) ──────────────────────────────────────
    c.setLineWidth(0.6)
    c.rect(LEFT, _top(H_BTM), RIGHT - LEFT, H_BTM - H_TOP)

    # ── Vertical divider ────────────────────────────────────────────────────
    c.line(DIVX, _top(H_TOP), DIVX, _top(H_BTM))

    # ── Horizontal line in right section, below "SALES QUOTATION" title ────
    c.line(DIVX, _top(50), RIGHT, _top(50))

    c.setLineWidth(0.4)

    # ── Logo ────────────────────────────────────────────────────────────────
    if logo_path and os.path.exists(logo_path):
        try:
            image = ImageReader(logo_path)
            iw, ih = image.getSize()
            w = 88
            h = w * ih / iw
            if h > 95:
                h = 95
                w = h * iw / ih
            c.drawImage(image, LOGO_X, _top(130), width=w, height=h,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # ── Company name – centred in the address section (right of logo) ───────
    addr_center = (ADDR_X + DIVX) / 2          # ≈ 246
    _draw(c, addr_center, 26, COMPANY_NAME, size=10.5, bold=True, align="center")

    # ── Address lines ────────────────────────────────────────────────────────
    for i, line in enumerate(ADDRESS_LINES):
        _draw(c, ADDR_X, 39 + i * 11.5, line, size=7.5)

    # ── Right section: "SALES QUOTATION" centred in its box ─────────────────
    right_center = (DIVX + RIGHT) / 2          # ≈ 476
    _draw(c, right_center, 33, "SALES QUOTATION", size=8.5, bold=True, align="center")

    # ── Quote details (below the horizontal separator at top=50) ────────────
    lx = DIVX + 8                              # labels left edge  ≈ 385
    _draw(c, lx,      65, "QUOTE :",  size=8, bold=True)
    _draw(c, lx,      79, quote_data.get("quote_no", ""),    size=8)
    _draw(c, lx,      98, "DATE :",   size=8, bold=True)
    _draw(c, lx + 43, 98, quote_data.get("quote_date", ""), size=8)
    _draw(c, lx,     113, "REVNO:",   size=8, bold=True)
    _draw(c, lx + 43,113, quote_data.get("rev_no", "0"),    size=8)
    _draw(c, lx,     130, "REVDATE:", size=8, bold=True)
    _draw(c, lx + 52,130, quote_data.get("rev_date", ""),   size=8)

    # ── PAN / CIN / GSTIN line ───────────────────────────────────────────────
    if show_pan:
        _draw(c,  31, 163, "IT PAN No.:AABCG2902K",       size=7.5)
        _draw(c, 216, 163, "CIN : U27209TN1987PTC014031", size=7.5)
        _draw(c, 424, 163, "GSTIN NO : 33AABCG2902K1ZY",  size=7.5)
        pass  # PAN separator drawn by _draw_buyer_block's outer rect


_HDR_BTM   = 148   # "top" coord of header box bottom
_BUYER_BTM = 358   # "top" coord of buyer-block bottom (= items table top)
_PAN_SEP   = 170   # separator below the PAN line
_FIELD_SEP = 262   # separator above the customer-fields rows
_COL_DIV   = 318   # vertical divider between left and right field columns

L, R = 20, 575.2   # page left / right margins (match items table)


def _draw_buyer_block(c: canvas.Canvas, quote_data: dict):
    c.setStrokeColorRGB(*BLACK)

    # ── Outer border for the entire PAN + buyer section ────────────────────
    # Closed box: left wall, right wall, top (= header bottom), bottom (= table top)
    c.setLineWidth(0.5)
    c.rect(L, _top(_BUYER_BTM), R - L, _BUYER_BTM - _HDR_BTM)

    # ── Internal horizontal dividers ────────────────────────────────────────
    c.setLineWidth(0.4)
    c.line(L, _top(_PAN_SEP),   R, _top(_PAN_SEP))    # below PAN row
    c.line(L, _top(_FIELD_SEP), R, _top(_FIELD_SEP))  # above customer-fields

    # ── Vertical divider between left and right field columns ───────────────
    c.setLineWidth(0.4)
    c.line(_COL_DIV, _top(_FIELD_SEP), _COL_DIV, _top(_BUYER_BTM))

    # ── Content ─────────────────────────────────────────────────────────────
    _draw(c, 25,  180, "Name & Address of the Buyer :", size=8)
    _draw(c, 555, 180, "GGPL/MKT/REC03", size=8, align="right")

    buyer_lines = str(quote_data.get("buyer_name_address", "")).splitlines()
    for i, (ytop, line) in enumerate(zip([194, 211, 228, 244, 260], buyer_lines)):
        _draw(c, 26, ytop, line, size=8)

    label_x, value_x = 24, 109
    rows = [
        (270, "Customer Enq No", quote_data.get("customer_enq_no", ""), "Followed By",  quote_data.get("rep_name", "")),
        (287, "Kind Attention",  quote_data.get("attention", ""),        "Designation",  quote_data.get("rep_designation", "")),
        (306, "Designation",     quote_data.get("designation", ""),      "Contact No",   quote_data.get("rep_contact", "")),
        (325, "Contact No",      quote_data.get("contact_no", ""),       "Email ID",     quote_data.get("rep_email", "")),
        (343, "Email ID",        quote_data.get("email", ""),            "",             ""),
    ]
    for top, label, value, rlabel, rvalue in rows:
        _draw(c, label_x,  top, label, size=8)
        _draw(c, 101,      top, ":",   size=8)
        _draw_wrapped(c, value_x, top, value, 200, size=8, leading=9, max_lines=1)
        if rlabel:
            _draw(c, _COL_DIV + 6,  top, rlabel, size=8)
            _draw(c, _COL_DIV + 75, top, ":",    size=8)
            _draw_wrapped(c, _COL_DIV + 82, top, rvalue, 160, size=8, leading=9, max_lines=2)


# ── Items table — built with reportlab.platypus.Table ───────────────────────
# Column x-dividers; col widths derived automatically
ITEM_COLS   = [20, 45.5, 83.8, 177.8, 345.5, 404.8, 437.8, 503.8, 575.2]
_ITEM_COL_W = [ITEM_COLS[i+1] - ITEM_COLS[i] for i in range(len(ITEM_COLS)-1)]

_TBL_TOP = 358   # "top" coord of table top edge
_TBL_BTM = 687   # "top" coord of table bottom edge

_PS_HDR  = ParagraphStyle('hdr',  fontName='Helvetica-Bold', fontSize=8,
                           leading=10, alignment=TA_CENTER)
_PS_DESC = ParagraphStyle('desc', fontName='Helvetica',      fontSize=8,
                           leading=10, alignment=TA_LEFT)

_ITEM_TSTYLE = TableStyle([
    # Fonts
    ('FONTNAME',      (0, 0), (-1,  0), 'Helvetica-Bold'),
    ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
    ('FONTSIZE',      (0, 0), (-1, -1), 8),
    # Per-column horizontal alignment
    ('ALIGN',  (0, 0), (0, -1), 'CENTER'),   # Sl. No.
    ('ALIGN',  (1, 0), (2, -1), 'CENTER'),   # Cust SL.NO, Item Code
    ('ALIGN',  (3, 0), (3,  0), 'CENTER'),   # Description — header only
    ('ALIGN',  (3, 1), (3, -1), 'LEFT'),     # Description — data
    ('ALIGN',  (4, 0), (4, -1), 'RIGHT'),    # Quantity
    ('ALIGN',  (5, 0), (5, -1), 'CENTER'),   # UOM
    ('ALIGN',  (6, 0), (7, -1), 'RIGHT'),    # Unit Price & Total
    # Vertical alignment — middle of cell
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    # Grid: thin lines for data cells, slightly thicker for header borders
    ('GRID',       (0, 0), (-1, -1), 0.3, colors.black),
    ('LINEABOVE',  (0, 0), (-1,  0), 0.5, colors.black),
    ('LINEBELOW',  (0, 0), (-1,  0), 0.5, colors.black),
    # Cell padding (matches reference PDF look)
    ('TOPPADDING',    (0, 0), (-1, -1), 5),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('LEFTPADDING',   (0, 0), (-1, -1), 3),
    ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
])


def _item_description(item: dict) -> str:
    if item.get("status") == "regret":
        return "REGRET - CANNOT PRODUCE"
    return item.get("ggpl_description") or item.get("description") or ""


def _make_items_table(items_slice: list[dict], prices_slice: list[float]) -> Table:
    """Build a platypus Table for a slice of items."""
    header = [
        Paragraph("Sl.<br/>No.",            _PS_HDR),
        Paragraph("Cust<br/>SL.NO",         _PS_HDR),
        Paragraph("Customer<br/>Item Code",  _PS_HDR),
        Paragraph("Material Description",    _PS_HDR),
        Paragraph("Quantity",                _PS_HDR),
        Paragraph("UOM",                     _PS_HDR),
        Paragraph("Unit Price<br/>INR",      _PS_HDR),
        Paragraph("TOTAL PRICE<br/>INR",     _PS_HDR),
    ]
    rows = [header]
    for i, (item, unit) in enumerate(zip(items_slice, prices_slice)):
        qty   = _num(item.get("quantity"))
        total = qty * unit
        rows.append([
            str(i + 1),                              # Sl. No.
            "",                                      # Cust SL.NO (blank)
            "",                                      # Item Code  (blank)
            Paragraph(_item_description(item), _PS_DESC),  # wraps automatically
            _fmt_qty(qty),                           # Quantity
            item.get("uom") or "NOS",                # UOM
            _fmt_amount(unit),                       # Unit Price
            _fmt_amount(total),                      # Total Price
        ])
    t = Table(rows, colWidths=_ITEM_COL_W, repeatRows=1)
    t.setStyle(_ITEM_TSTYLE)
    return t


def _draw_items_page(c: canvas.Canvas, items: list[dict], quote_data: dict, start: int):
    _draw_buyer_block(c, quote_data)

    unit_prices = quote_data.get("unit_prices", [])
    TABLE_X = ITEM_COLS[0]                         # 20 pt
    TABLE_W = ITEM_COLS[-1] - ITEM_COLS[0]         # 555.2 pt
    AVAIL_H = _TBL_BTM - _TBL_TOP                  # 329 pt available

    # ── Estimate how many items fit before building the table ────────────────
    desc_inner_w = _ITEM_COL_W[3] - 6              # usable description cell width
    HDR_APPROX   = 32                              # header row height estimate
    used_h, n_fit = 0, 0
    for item in items[start:]:
        n_lines = min(len(_wrap(_item_description(item), desc_inner_w, "Helvetica", 8)), 4)
        row_h   = max(22, n_lines * 10) + 10       # content + top+bottom padding
        if used_h + row_h > AVAIL_H - HDR_APPROX:
            break
        used_h += row_h
        n_fit  += 1
    n_fit = max(1, n_fit)

    items_slice  = items[start : start + n_fit]
    prices_slice = [_num(unit_prices[start + i] if start + i < len(unit_prices) else 0)
                    for i in range(n_fit)]

    # ── Build & draw the table ───────────────────────────────────────────────
    t = _make_items_table(items_slice, prices_slice)
    _, tbl_h = t.wrapOn(c, TABLE_W, AVAIL_H)

    tbl_pdf_y = _top(_TBL_TOP) - tbl_h             # lower-left in PDF coords
    t.drawOn(c, TABLE_X, tbl_pdf_y)

    # ── Extend column dividers into the blank rows below the table ───────────
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(0.3)
    for x in ITEM_COLS:
        c.line(x, tbl_pdf_y, x, _top(_TBL_BTM))

    # ── Bottom border of the whole table area ────────────────────────────────
    c.setLineWidth(0.5)
    c.line(TABLE_X, _top(_TBL_BTM), ITEM_COLS[-1], _top(_TBL_BTM))

    _draw(c, 298, 705, "PAGE TURN OVER", size=8, bold=True, align="center")
    return start + n_fit


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
    total_qty, subtotal, _, __, gst_amt, grand_total = _totals(items, quote_data)

    c.setStrokeColorRGB(*BLACK)

    # ── Layout constants (match reference PDF coordinates exactly) ─────────────
    PL, PR   = 20, 575.2        # page left / right
    HDR_BTM  = 148              # header box bottom
    TOT_TOP  = 154              # top line of totals band
    TOT_BTM  = 169              # bottom line of totals band
    SIG_TOP  = 717              # top of signature area
    SIG_BTM  = 785              # bottom of signature area (footer is below)

    # ── ONE outer rect spanning header-bottom → signature-bottom ──────────────
    # (header itself already drew its own rect; this continues the left/right walls)
    c.setLineWidth(0.5)
    c.rect(PL, _top(SIG_BTM), PR - PL, SIG_BTM - HDR_BTM)

    # ── Internal horizontal section separators ────────────────────────────────
    c.setLineWidth(0.4)
    c.line(PL, _top(TOT_TOP), PR, _top(TOT_TOP))   # totals band top
    c.line(PL, _top(TOT_BTM), PR, _top(TOT_BTM))   # totals band bottom
    c.line(PL, _top(SIG_TOP), PR, _top(SIG_TOP))   # signature area top

    # ── Totals row (centred in the totals band) ────────────────────────────────
    mid_y = (TOT_TOP + TOT_BTM) / 2 + 3            # ≈ 164
    _draw(c, 352, mid_y, "Total Qty :",    size=8, bold=True, align="right")
    _draw(c, 431, mid_y, _fmt_qty(total_qty),               size=8, align="right")
    _draw(c, 501, mid_y, "Total Amount :", size=8, bold=True, align="right")
    _draw(c, 552, mid_y, _fmt_amount(subtotal, comma=True), size=8, align="right")

    # ── GST table (right column, no inner borders — matches reference) ─────────
    GST_X1 = 392    # name column left
    GST_X2 = 480    # pct right-align
    GST_X3 = 492    # % symbol
    GST_X4 = 569    # amount right-align
    GST_ROW_H = 17

    gst_y = 186     # first GST row text y (in pdfplumber-style top coords)
    for name, pct, amount in _gst_rows(quote_data, gst_amt):
        _draw(c, GST_X1, gst_y, name, size=8)
        _draw(c, GST_X2, gst_y, f"{pct:.2f}", size=8, align="right")
        _draw(c, GST_X3, gst_y, "%", size=8)
        _draw(c, GST_X4, gst_y, _fmt_amount(amount, comma=True), size=8, align="right")
        gst_y += GST_ROW_H

    # Thin rule above TOTAL, then bold TOTAL row
    c.setLineWidth(0.3)
    c.line(383, _top(gst_y), PR, _top(gst_y))
    _draw(c, 501, gst_y + 9, "TOTAL", size=8, bold=True, align="right")
    _draw(c, GST_X4, gst_y + 9, _fmt_amount(grand_total, comma=True), size=8, bold=True, align="right")

    # ── Terms & Conditions (left column, beside GST table) ────────────────────
    _draw(c, 32, 180, "Terms & Conditions :", size=7.5, bold=True)

    terms = [
        ("1. Price Basis",          quote_data.get("price_basis", "FOR BASIS")),
        ("2. Validity",             f"{quote_data.get('validity_days', '7')} DAYS"),
        ("3. Packing &\nforwarding charges", quote_data.get("packing", "INCLUSIVE")),
        ("4. Freight",              quote_data.get("freight", "INCLUSIVE")),
        ("5. Taxes and Duties",     f"Taxes and duties shall be paid at actuals as applicable at the time of shipment-present GST is {_num(quote_data.get('gst_pct'), 18):g}%"),
        ("6. Payment Terms",        quote_data.get("payment_terms", "30% ADVANCE & 70% BALANCE BEFORE DISPATCH OF MATERIAL")),
        ("7. Bank Charges",         quote_data.get("bank_charges", "Bank Charges at the customer side, shall to be customer account, unless agreed prior by Goodrich .")),
        ("8. Delivery Terms",       quote_data.get("delivery", "")),
        ("9. Insurance",            quote_data.get("insurance", "TO YOUR ACCOUNT")),
        ("10. Inspection",          quote_data.get("inspection", "")),
        ("11. HSN Code",            quote_data.get("hsn_code", "84841010")),
        ("12. LD Clause",           quote_data.get("ld_clause", "Not Applicable")),
        ("13. Cancellation",        quote_data.get("cancellation", "Products are manufactured on order and hence Goodrich will not be able to accept cancellation of order or reduction in quantity. The product shall to invoiced as per the PO.")),
        ("14. Minimum Order Value", quote_data.get("min_order_value", "Minimum Order Value is INR 10,000,No order can be processed below the same. If it is processed, INR 3500 shall be paid extra on document charges.")),
    ]

    top = 193
    GST_END_Y = gst_y + GST_ROW_H   # y below the TOTAL row
    for label, value in terms:
        label_lines = str(label).splitlines()
        for i, line in enumerate(label_lines):
            _draw(c, 30, top + i * 10, line, size=8)
        _draw(c, 148, top, ":", size=8)
        # Narrower text area while we're beside the GST table
        txt_width = (383 - 170) if top < GST_END_Y else 390
        used = _draw_wrapped(c, 166, top, value, txt_width, size=8, leading=10, max_lines=4)
        top += max(14, 10 * max(len(label_lines), used))

    # ── Part of Quote + Technical Notes + General Terms ───────────────────────
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

    # ── Signature area (between SIG_TOP and SIG_BTM) ──────────────────────────
    sig_div = PL + (PR - PL) * 2 / 3   # vertical divider ≈ x=390
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(0.4)
    c.line(sig_div, _top(SIG_TOP), sig_div, _top(SIG_BTM))

    sig_mid_x = (sig_div + PR) / 2
    _draw(c, sig_mid_x, SIG_TOP + 18, "For Goodrich Gasket Pvt. Ltd.", size=8, bold=True, align="center")
    _draw(c, sig_mid_x, SIG_TOP + 54, "Authorised Signatory",         size=8, bold=True, align="center")

    # ── Footer (outside all borders) ─────────────────────────────────────────
    _draw(c, 30,  SIG_BTM + 12, "Record Created on.:        Revision No :03        Revision Date : 10.10.2019", size=7)
    _draw(c, 298, SIG_BTM + 24, "This is a Computer Generated Document Signature not Required", size=7, align="center")


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
