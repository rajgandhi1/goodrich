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
    "Regd. Office & Works:",
    "40, Velichai Village, Next to: Pasupathi Eswaran Temple,",
    "Opp. Road to: Pudupakkam Anjaneyar Hill Temple,",
    "Vandalur-Kelambakkam Road,",
    "Chennai - 600127, Tamil Nadu, India.",
    "Tel: +91-44-67400004 - 99 / +91-7824017150/7824017151",
    "Fax: +91-44-67400003",
    "Email: goodrichgasket@gmail.com / info@flosil.com",
]
PAN_LINE = (
    "IT PAN No.:AABCG2902K        CIN : U27209TN1987PTC014031        "
    "GSTIN NO : 33AABCG2902K1ZY"
)
GENERAL_TERMS = [
    "1. Delivery Terms: Delivery is subject to final acceptance of the purchase order by Goodrich, including acceptance of commercial terms and conditions, technical deviations, and replies to technical queries. Production release note and contractual delivery date will start only after pending issues are resolved.",
    "2. Express Deliveries: Any shorter delivery requirement must be requested in writing before purchase order placement. Goodrich may accept or reject the request. Approved express delivery charges shall be borne by the customer, and LD shall not apply for express deliveries.",
    "3. Payment Terms: Payment terms shall be as negotiated and agreed. Delayed payments beyond agreed terms shall attract interest at 18% per annum on a pro-rata basis.",
    "4. Liquidated Damages LD Clause: Not applicable.",
    "5. Storage Charge: If dispatch approval or dispatch arrangement is delayed by the customer, storage charges at 1% per month plus GST shall apply on a pro-rata basis. Delays beyond 60 days will not be accepted, and the consignment may be dispatched without further notice.",
    "6. Order Cancellation or Amendment: After purchase order placement, cancellation or amendment will not be accepted. If cancelled or amended, full payment shall be made as per the original purchase order.",
    "7. Delivery Dates: If production is completed early, the customer shall settle payment and authorize dispatch.",
    '8. Acknowledgement of Terms: The purchaser acknowledges that they have read and agreed to the General Terms of Quotation and shall include these clauses in the purchase order.',
    '9. Shipping Address: Products will be shipped only to the "Shipping Address" mentioned in the purchase order.',
    "10. Jurisdiction for Disputes: For any dispute, jurisdiction will be Chennai City Civil Court or Chennai High Court only.",
    "11. Force Majeure: Delivery is subject to Force Majeure conditions beyond Goodrich control, including lockdowns, natural disasters, epidemics, pandemics, acts of God, and government ordinances. Delays due to such events shall not be considered default by Goodrich.",
    "12. Pricing Validity: Pricing is applicable only for the offered part numbers and quantities dispatched in one lot. Goodrich reserves the right to revise prices for partial or multiple shipments.",
    "13. Ex-Stock Items: Ex-stock items are subject to prior sales.",
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


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _top(y: float) -> float:
    return PAGE_H - y


def _y(glyph_top: float, size: float) -> float:
    """Convert a glyph-top top-coord (as in the reference PDF) to the
    baseline top-coord that _draw() expects.  Times ascender ≈ 0.78×size."""
    return glyph_top + size * 0.78


def _draw_page_outer_border(c: canvas.Canvas):
    """Single thick outer rect matching the reference PDF exactly."""
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(1.5)
    # Reference: x0=20.2 y0=40.2 x1=575.2 y1=819.5  (PDF coords, y=0 at bottom)
    c.rect(20.2, 40.2, 555.0, 779.3)


def _draw_page_number(c: canvas.Canvas, page_no: int):
    _draw(c, 555, 793, f"Page {page_no}", size=8, align="right")


def _draw(c: canvas.Canvas, x: float, top: float, text: str, size=8, bold=False, align="left"):
    font = "Times-Bold" if bold else "Times-Roman"
    c.setFont(font, size)
    text = str(text or "")
    y = _top(top)
    if align == "right":
        c.drawRightString(x, y, text)
    elif align == "center":
        c.drawCentredString(x, y, text)
    else:
        c.drawString(x, y, text)


def _wrap(text: str, width: float, font="Times-Roman", size=8) -> list[str]:
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
    font = "Times-Bold" if bold else "Times-Roman"
    lines = _wrap(text, width, font, size)
    if max_lines:
        lines = lines[:max_lines]
    for i, line in enumerate(lines):
        _draw(c, x, top + i * leading, line, size=size, bold=bold)
    return len(lines)


def _draw_paragraph_block(c, title: str, text: str, top: float, width: float = 535) -> float:
    value = str(text or "").strip()
    if not value:
        return top
    _draw(c, 33, top, title, size=10, bold=True)
    top += 17
    for raw in value.splitlines() or [value]:
        if not raw.strip():
            top += 9
            continue
        for line in _wrap(raw, width, "Times-Roman", 10):
            _draw(c, 33, top, line, size=10)
            top += 14
    return top + 10


def _draw_general_terms_page(c: canvas.Canvas):
    top = 171
    _draw(c, 33, top, "GENERAL TERMS OF QUOTATION:", size=10, bold=True)
    top = 195
    for term in GENERAL_TERMS:
        top = _draw_numbered_term(c, 33, top, term, 530, size=10, leading=12)
        top += 5
    top += 8
    _draw_wrapped(
        c,
        33,
        top,
        "We trust that our rates are competitive and our terms and conditions are acceptable. We look forward to receiving your valued order.",
        530,
        size=10,
        leading=12,
    )


def _draw_numbered_term(c: canvas.Canvas, x: float, top: float, text: str, width: float, size=10, leading=12) -> float:
    prefix, sep, rest = str(text or "").partition(":")
    if not sep:
        for line in _wrap(text, width, "Times-Roman", size):
            _draw(c, x, top, line, size=size)
            top += leading
        return top

    bold_prefix = f"{prefix}:"
    gap = 3
    prefix_width = pdfmetrics.stringWidth(bold_prefix, "Times-Bold", size)
    first_width = max(40, width - prefix_width - gap)
    words = _clean(rest).split()
    first_line = ""
    while words:
        trial = words[0] if not first_line else f"{first_line} {words[0]}"
        if pdfmetrics.stringWidth(trial, "Times-Roman", size) > first_width and first_line:
            break
        first_line = trial
        words.pop(0)
    _draw(c, x, top, bold_prefix, size=size, bold=True)
    if first_line:
        _draw(c, x + prefix_width + gap, top, first_line, size=size)
    top += leading
    remaining = " ".join(words)
    if remaining:
        for line in _wrap(remaining, width, "Times-Roman", size):
            _draw(c, x, top, line, size=size)
            top += leading
    return top


def _draw_other_term_row(
    c: canvas.Canvas,
    top: float,
    number: int,
    label: str,
    value: str,
    size: float = 10,
    leading: float = 14.04,
) -> float:
    num_x = 33
    label_x = 47.16
    colon_x = 177.02
    value_x = 181.94
    right_x = 563

    _draw(c, num_x, top, f"{number}.", size=size)
    _draw(c, label_x, top, label, size=size)
    _draw(c, colon_x, top, ":", size=size)

    words = _clean(value).split()
    first_line = ""
    first_width = right_x - value_x
    while words:
        trial = words[0] if not first_line else f"{first_line} {words[0]}"
        if pdfmetrics.stringWidth(trial, "Times-Roman", size) > first_width and first_line:
            break
        first_line = trial
        words.pop(0)
    if first_line:
        _draw(c, value_x, top, first_line, size=size)
    top += leading

    remaining = " ".join(words)
    if remaining:
        for line in _wrap(remaining, right_x - label_x, "Times-Roman", size):
            _draw(c, label_x, top, line, size=size)
            top += leading
    return top


def _draw_signature_block(c: canvas.Canvas, start_top: float) -> float:
    _draw(c, 33, start_top, "For Goodrich Gaskets", size=10)
    _draw(c, 33, start_top + 12, "Authorized Signatory and Company Seal", size=10)
    accepted_top = start_top + 122
    _draw(c, 33, accepted_top, "Accepted By -", size=10)
    _draw(c, 33, accepted_top + 12, "Client Name :", size=10)
    _draw(c, 33, accepted_top + 24, "Signature :", size=10)
    _draw(c, 33, accepted_top + 36, "Name and Designation :", size=10)
    _draw(c, 33, accepted_top + 48, "Date :", size=10)
    return accepted_top + 60


def _draw_header(c: canvas.Canvas, quote_data: dict, logo_path: str | None, show_pan: bool = True):
    c.setStrokeColorRGB(*BLACK)

    # ── Layout constants — matched to reference PDF measurements ─────────────
    LEFT,   RIGHT    = 20.2,  575.2    # page content left / right
    H_TOP,  H_BTM   = 21.5,  147.3    # header top / bottom (top-coords)
    LOGO_DIV         = 150.0           # vertical: logo column | company column
    DIVX             = 387.5           # vertical: company column | SALES QUOTATION
    ADDR_X           = 154.0           # address text left edge

    # ── Internal header lines (no separate header rect — outer drawn per-page) ─
    c.setLineWidth(1.0)
    c.line(LEFT,     _top(H_BTM),  RIGHT,    _top(H_BTM))   # header bottom
    c.line(LOGO_DIV, _top(H_TOP),  LOGO_DIV, _top(H_BTM))   # logo | company divider
    c.line(DIVX,     _top(H_TOP),  DIVX,     _top(H_BTM))   # company | quote divider
    c.line(DIVX,     _top(49.8),   RIGHT,    _top(49.8))     # below "SALES QUOTATION"

    # ── Logo ────────────────────────────────────────────────────────────────
    if logo_path and os.path.exists(logo_path):
        try:
            image = ImageReader(logo_path)
            iw, ih = image.getSize()
            w_max = LOGO_DIV - LEFT - 8           # ~104px wide
            h_max = H_BTM - H_TOP - 8             # ~118px tall
            w = w_max
            h = w * ih / iw
            if h > h_max:
                h = h_max
                w = h * iw / ih
            header_top_y = _top(H_TOP)
            header_bottom_y = _top(H_BTM)
            img_bottom = header_bottom_y + ((header_top_y - header_bottom_y) - h) / 2
            img_left = LEFT + (LOGO_DIV - LEFT - w) / 2
            c.drawImage(image, img_left, img_bottom, width=w, height=h,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # ── Company name – auto-shrink to fit within the centre column ───────────
    addr_center = (ADDR_X + DIVX) / 2             # ≈ 261.75
    max_name_w  = DIVX - ADDR_X - 16
    name_size   = 11.5
    while name_size > 8 and pdfmetrics.stringWidth(COMPANY_NAME, "Times-Bold", name_size) > max_name_w:
        name_size -= 0.5
    _draw(c, addr_center, _y(27.5, name_size), COMPANY_NAME, size=name_size, bold=True, align="center")

    # ── Address lines – 9 lines, 12px fixed spacing (matches reference) ───────
    for i, line in enumerate(ADDRESS_LINES):
        _draw(c, ADDR_X, _y(40.7 + i * 12, 8.5), line, size=8.5)

    # ── Right section: "SALES QUOTATION" ─────────────────────────────────────
    right_center = (DIVX + RIGHT) / 2             # ≈ 481.35
    _draw(c, right_center, _y(32.7, 9.5), "SALES QUOTATION", size=9.5, bold=True, align="center")

    # ── Quote details (y-positions matched to reference glyph-tops) ───────────
    lx = DIVX + 7                                 # ≈ 394.5
    _draw(c, lx,      _y(57.2, 9), "QUOTATION NO.:",  size=9, bold=True)
    _draw(c, lx,      _y(70.7, 9), quote_data.get("quote_no", ""),    size=9)
    _draw(c, lx,      _y(86.0, 9), "Date:",   size=9, bold=True)
    _draw(c, lx + 43, _y(86.0, 9), quote_data.get("quote_date", ""), size=9)
    _draw(c, lx,     _y(103.0, 9), "Rev. No.:",   size=9, bold=True)
    _draw(c, lx + 52,_y(103.0, 9), quote_data.get("rev_no", "0"),    size=9)
    _draw(c, lx,     _y(116.0, 9), "Rev. Date:", size=9, bold=True)
    _draw(c, lx + 58,_y(116.0, 9), quote_data.get("rev_date", ""),   size=9)
    _draw(c, lx,     _y(128.0, 8), "*Please refer to the email", size=8)
    _draw(c, lx,     _y(138.0, 8), "subject", size=8)

    # ── PAN / CIN / GSTIN (glyph-top matched to reference y=155.4) ───────────
    if show_pan:
        _draw(c,  31, _y(155.4, 8.5), "IT PAN No.:AABCG2902K",       size=8.5, bold=True)
        _draw(c, 216, _y(155.4, 8.5), "CIN : U27209TN1987PTC014031", size=8.5, bold=True)
        _draw(c, 424, _y(155.4, 8.5), "GSTIN NO : 33AABCG2902K1ZY",  size=8.5, bold=True)


_HDR_BTM   = 147.3  # "top" coord of header bottom (matches reference)
_BUYER_BTM = 358.3  # "top" coord of buyer-block bottom / table top
_PAN_SEP   = 166.1  # separator below the PAN line (matches reference)
_FIELD_SEP = 261.5  # separator above customer-fields (matches reference)
_COL_DIV   = 318    # vertical divider in buyer block (left | right fields)

L, R = 20.2, 575.2  # page left / right (match outer rect)
DEFAULT_TECHNICAL_NOTES = (
    "1. Certifications: MTC to EN10204-3.1 for metallic parts and EN10204-2.1 for non-metallic.\n"
    "2. Testing Charges for gasket will be extra at actuals for tests other than compression & sealability test and chemical analysis."
)


def _draw_buyer_block(c: canvas.Canvas, quote_data: dict):
    c.setStrokeColorRGB(*BLACK)

    # ── Internal lines only — outer rect is drawn once per page ─────────────
    c.setLineWidth(1.0)
    c.line(L, _top(_BUYER_BTM), R, _top(_BUYER_BTM))   # buyer block bottom
    c.line(L, _top(_PAN_SEP),   R, _top(_PAN_SEP))      # below PAN row
    c.line(L, _top(_FIELD_SEP), R, _top(_FIELD_SEP))    # above customer-fields
    c.line(_COL_DIV, _top(_FIELD_SEP), _COL_DIV, _top(_BUYER_BTM))  # column divider

    # ── Content (all y-coords are reference glyph-tops, converted via _y()) ─────
    _draw(c, 25,  _y(171.2, 9), "Name & Address of the Buyer :", size=9, bold=True)

    buyer_lines = str(quote_data.get("buyer_name_address", "")).splitlines()
    for ref_top, line in zip([185.7, 202.7, 219.7, 236.7, 253.7], buyer_lines):
        _draw(c, 26, _y(ref_top, 9), line, size=9)

    label_x, value_x = 24, 109
    # Reference glyph-tops for each field row
    mobile_no = quote_data.get("mobile_no") or quote_data.get("contact_no", "")
    rows = [
        (264.8, "Customer Enq No", quote_data.get("customer_enq_no", ""), "Followed By",  quote_data.get("rep_name", "")),
        (280.8, "Sender's Name",   quote_data.get("attention", ""),      "Designation",  quote_data.get("rep_designation", "")),
        (296.8, "Designation",     quote_data.get("designation", ""),    "Contact No",   quote_data.get("rep_contact", "")),
        (312.8, "Mobile Number",   mobile_no,                            "Email ID",     quote_data.get("rep_email", "")),
        (328.8, "Telephone No",    quote_data.get("telephone_no", ""),  "",             ""),
        (344.8, "Email ID",        quote_data.get("email", ""),         "",             ""),
    ]
    for ref_top, label, value, rlabel, rvalue in rows:
        top = _y(ref_top, 9)
        _draw(c, label_x,  top, label, size=9, bold=True)
        _draw(c, 101,      top, ":",   size=9)
        _draw_wrapped(c, value_x, top, value, 200, size=9, leading=10, max_lines=1)
        if rlabel:
            _draw(c, _COL_DIV + 6,  top, rlabel, size=9, bold=True)
            _draw(c, _COL_DIV + 75, top, ":",    size=9)
            _draw_wrapped(c, _COL_DIV + 82, top, rvalue, 160, size=9, leading=10, max_lines=2)


# ── Items table — built with reportlab.platypus.Table ───────────────────────
# Column x-dividers; col widths derived automatically
ITEM_COLS   = [20.2, 45.5, 83.8, 177.8, 345.5, 404.8, 437.8, 503.8, 575.2]
_ITEM_COL_W = [ITEM_COLS[i+1] - ITEM_COLS[i] for i in range(len(ITEM_COLS)-1)]
_TBL_TOP = 358   # "top" coord of table top edge
_TBL_BTM = 785   # "top" coord of table bottom edge
_PAGE_TURN_Y = 793

_PS_HDR  = ParagraphStyle('hdr',  fontName='Times-Bold',    fontSize=9,
                           leading=11, alignment=TA_CENTER)
_PS_DESC = ParagraphStyle('desc', fontName='Times-Roman', fontSize=8.4,
                          leading=10, alignment=TA_LEFT)
_PS_GGPL = ParagraphStyle('ggpl', fontName='Times-Roman', fontSize=7.2,
                          leading=8.5, alignment=TA_LEFT, textColor=colors.HexColor('#555555'))

_ITEM_TSTYLE = TableStyle([
    # Fonts
    ('FONTNAME',      (0, 0), (-1,  0), 'Times-Bold'),
    ('FONTNAME',      (0, 1), (-1, -1), 'Times-Roman'),
    ('FONTSIZE',      (0, 0), (-1, -1), 9),
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
    # Grid: 1.0 throughout to match reference PDF
    ('GRID',       (0, 0), (-1, -1), 1.0, colors.black),
    ('LINEABOVE',  (0, 0), (-1,  0), 1.0, colors.black),
    ('LINEBELOW',  (0, 0), (-1,  0), 1.0, colors.black),
    # Cell padding (matches reference PDF look)
    ('TOPPADDING',    (0, 0), (-1, -1), 5),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('LEFTPADDING',   (0, 0), (-1, -1), 3),
    ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
])


def _item_columns(quote_data: dict):
    include_customer_sl = _bool(quote_data.get("include_customer_sl_no"))
    include_customer_code = _bool(quote_data.get("include_customer_item_code"))
    first_header = "Cust<br/>SL.NO" if include_customer_sl else "Sl.<br/>No."
    columns = [
        ("serial", Paragraph(first_header, _PS_HDR), 25.3),
        ("description", Paragraph("Material Description", _PS_HDR), 0),
        ("quantity", Paragraph("Quantity", _PS_HDR), 59.3),
        ("uom", Paragraph("UOM", _PS_HDR), 33.0),
        ("unit", None, 66.0),
        ("total", None, 71.4),
    ]
    if include_customer_code:
        columns.insert(1, ("customer_item_code", Paragraph("Customer<br/>Item Code", _PS_HDR), 70.0))
    fixed_width = sum(width for _, _, width in columns)
    desc_width = ITEM_COLS[-1] - ITEM_COLS[0] - fixed_width
    return [(key, header, desc_width if key == "description" else width) for key, header, width in columns]


def _item_table_style(desc_col: int, qty_col: int, uom_col: int, unit_col: int, total_col: int) -> TableStyle:
    return TableStyle([
        ('FONTNAME',      (0, 0), (-1,  0), 'Times-Bold'),
        ('FONTNAME',      (0, 1), (-1, -1), 'Times-Roman'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8.5),
        ('ALIGN',         (0, 0), (0, -1), 'CENTER'),
        ('ALIGN',         (desc_col, 0), (desc_col, 0), 'CENTER'),
        ('ALIGN',         (desc_col, 1), (desc_col, -1), 'LEFT'),
        ('ALIGN',         (qty_col, 0), (qty_col, -1), 'RIGHT'),
        ('ALIGN',         (uom_col, 0), (uom_col, -1), 'CENTER'),
        ('ALIGN',         (unit_col, 0), (total_col, -1), 'RIGHT'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',          (0, 0), (-1, -1), 1.0, colors.black),
        ('LINEABOVE',     (0, 0), (-1,  0), 1.0, colors.black),
        ('LINEBELOW',     (0, 0), (-1,  0), 1.0, colors.black),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
    ])


def _description_cell(item: dict):
    """Return a Paragraph for the Material Description cell.

    Shows the customer's description first, with the GGPL normalized
    description below it in smaller text.
    """
    from reportlab.platypus import KeepInFrame
    if item.get("status") == "regret":
        return Paragraph("REGRET - CANNOT PRODUCE", _PS_DESC)
    ggpl = _clean(item.get("ggpl_description") or item.get("description") or "")
    cust = _clean(item.get("raw_description") or "")
    if cust and cust != ggpl:
        return KeepInFrame(0, 0, [
            Paragraph(cust, _PS_DESC),
            Paragraph(f"Goodrich: {ggpl}", _PS_GGPL),
        ], mode='shrink')
    return Paragraph(cust or ggpl, _PS_DESC)


def _make_legacy_items_table(items_slice: list[dict], prices_slice: list[float], start_serial: int = 1, currency: str = "INR", quote_data: dict | None = None) -> Table:
    """Build a platypus Table for a slice of items."""
    header = [
        Paragraph("Sl.<br/>No.",                       _PS_HDR),
        Paragraph("Cust<br/>SL.NO",                    _PS_HDR),
        Paragraph("Customer<br/>Item Code",             _PS_HDR),
        Paragraph("Material Description",               _PS_HDR),
        Paragraph("Quantity",                           _PS_HDR),
        Paragraph("UOM",                                _PS_HDR),
        Paragraph(f"Unit Price<br/>{currency}",         _PS_HDR),
        Paragraph(f"TOTAL PRICE<br/>{currency}",        _PS_HDR),
    ]
    rows = [header]
    for i, (item, unit) in enumerate(zip(items_slice, prices_slice)):
        qty = _num(item.get("quantity"))
        quoted_qty = 0 if item.get("status") == "regret" else qty
        total = quoted_qty * unit
        rows.append([
            str(start_serial + i),         # Sl. No. — continuous across pages
            str(item.get("customer_sl_no") or ""),       # Cust SL.NO
            str(item.get("customer_item_code") or ""),   # Customer item code
            _description_cell(item),       # GGPL desc + customer ref
            _fmt_qty(qty),                 # Quantity
            item.get("uom") or "NOS",      # UOM
            _fmt_amount(unit),             # Unit Price
            _fmt_amount(total),            # Total Price
        ])
    t = Table(rows, colWidths=_ITEM_COL_W, repeatRows=1)
    t.setStyle(_ITEM_TSTYLE)
    return t


def _make_items_table(items_slice: list[dict], prices_slice: list[float], start_serial: int = 1, currency: str = "INR", quote_data: dict | None = None) -> Table:
    quote_data = quote_data or {}
    include_customer_sl = _bool(quote_data.get("include_customer_sl_no"))
    columns = _item_columns(quote_data)
    keys = [key for key, _, _ in columns]
    header = [
        Paragraph(f"Unit Price<br/>{currency}", _PS_HDR) if key == "unit" else
        Paragraph(f"TOTAL PRICE<br/>{currency}", _PS_HDR) if key == "total" else
        label
        for key, label, _ in columns
    ]
    rows = [header]
    for i, (item, unit) in enumerate(zip(items_slice, prices_slice)):
        qty = _num(item.get("quantity"))
        quoted_qty = 0 if item.get("status") == "regret" else qty
        total = quoted_qty * unit
        values = {
            "serial": str(item.get("customer_sl_no") or start_serial + i) if include_customer_sl else str(start_serial + i),
            "customer_item_code": str(item.get("customer_item_code") or ""),
            "description": _description_cell(item),
            "quantity": _fmt_qty(qty),
            "uom": item.get("uom") or "NOS",
            "unit": _fmt_amount(unit),
            "total": _fmt_amount(total),
        }
        rows.append([values[key] for key in keys])
    desc_col = keys.index("description")
    qty_col = keys.index("quantity")
    uom_col = keys.index("uom")
    unit_col = keys.index("unit")
    total_col = keys.index("total")
    t = Table(rows, colWidths=[width for _, _, width in columns], repeatRows=1)
    t.setStyle(_item_table_style(desc_col, qty_col, uom_col, unit_col, total_col))
    return t


def _draw_items_page(c: canvas.Canvas, items: list[dict], quote_data: dict, start: int):
    _draw_buyer_block(c, quote_data)

    unit_prices = quote_data.get("unit_prices", [])
    currency    = quote_data.get("currency", "INR")
    TABLE_X = ITEM_COLS[0]
    TABLE_W = ITEM_COLS[-1] - ITEM_COLS[0]
    AVAIL_H = _TBL_BTM - _TBL_TOP

    def _prices_for(count: int) -> list[float]:
        return [
            _num(unit_prices[start + i] if start + i < len(unit_prices) else 0)
            for i in range(count)
        ]

    n_fit = 0
    for count in range(1, len(items) - start + 1):
        candidate = _make_items_table(
            items[start : start + count],
            _prices_for(count),
            start_serial=start + 1,
            currency=currency,
            quote_data=quote_data,
        )
        _, candidate_h = candidate.wrapOn(c, TABLE_W, AVAIL_H)
        if candidate_h > AVAIL_H:
            break
        n_fit = count
    n_fit = max(1, n_fit)

    items_slice  = items[start : start + n_fit]
    prices_slice = _prices_for(n_fit)

    # ── Build & draw the table ───────────────────────────────────────────────
    t = _make_items_table(items_slice, prices_slice, start_serial=start + 1, currency=currency, quote_data=quote_data)
    _, tbl_h = t.wrapOn(c, TABLE_W, AVAIL_H)

    tbl_pdf_y = _top(_TBL_TOP) - tbl_h             # lower-left in PDF coords
    t.drawOn(c, TABLE_X, tbl_pdf_y)

    # ── Extend column dividers into the blank rows below the table ───────────
    next_start = start + n_fit

    # ── Bottom border of the whole table area ────────────────────────────────
    if next_start < len(items):
        _draw(c, 298, _PAGE_TURN_Y, "PAGE TURN OVER", size=9, bold=True, align="center")
    return next_start


def _totals(items: list[dict], quote_data: dict):
    unit_prices = quote_data.get("unit_prices", [])
    currency = quote_data.get("currency", "INR")
    total_qty = Decimal("0")
    subtotal = Decimal("0")
    for idx, item in enumerate(items):
        qty = Decimal("0") if item.get("status") == "regret" else Decimal(str(_num(item.get("quantity"))))
        unit = Decimal(str(_num(unit_prices[idx] if idx < len(unit_prices) else 0)))
        total_qty += qty
        subtotal += qty * unit
    discount_pct = Decimal(str(_num(quote_data.get("discount_pct"))))
    discount_amt = subtotal * discount_pct / Decimal("100")
    taxable = subtotal - discount_amt
    gst_pct = Decimal(str(_num(quote_data.get("gst_pct"), 18)))
    gst_amt = taxable * gst_pct / Decimal("100") if currency == "INR" else Decimal("0")
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
    c.setStrokeColorRGB(*BLACK)
    currency = quote_data.get("currency", "INR")

    # ── Layout constants (match reference PDF coordinates exactly) ─────────────
    PL, PR   = 20, 575.2        # page left / right
    HDR_BTM  = 148              # header box bottom

    # ── Other Terms & Conditions ─────────────────────────────────────────────
    _draw(c, 33, 162.8, "Other Terms & Conditions:", size=10, bold=True)

    terms = [
        ("Price Basis", quote_data.get("price_basis", "As per Quotation")),
        ("Packing Charges", quote_data.get("packing", "As per Quotation")),
        ("Freight", quote_data.get("freight", "As per Quotation")),
        ("Validity", f"{quote_data.get('validity_days', '7')} days"),
        ("Payment Terms", quote_data.get("payment_terms", "As per Quotation")),
        ("Delivery Terms", quote_data.get("delivery", "As per Quotation")),
        ("Insurance", quote_data.get("insurance", "As per Quotation")),
        ("Road Permit", quote_data.get("road_permit", "As per Quotation")),
        ("TPI Inspections charges", quote_data.get("inspection", "As per Quotation")),
        ("LD Clause", quote_data.get("ld_clause", "As per Quotation / Not applicable")),
        ("HSN Code", quote_data.get("hsn_code", "84841010")),
        ("PBG", quote_data.get("pbg", "As per Quotation")),
        ("Taxes & Duties", f"Paid at actuals as applicable at the time of shipment -present GST is {_num(quote_data.get('gst_pct'), 18):g}%" if currency == "INR" else "Paid at actuals as applicable at the time of shipment"),
        ("Bank Charges", quote_data.get("bank_charges", "At customer end, shall be at customer account, unless agreed prior by Goodrich")),
        ("Minimum Order Value", quote_data.get("min_order_value", "INR 25,000. No order can be processed below the same and if processed, INR 5,000 shall be paid extra towards document charges.")),
    ]

    top = 176.9
    for index, (label, value) in enumerate(terms, start=1):
        top = _draw_other_term_row(c, top, index, label, value)

    # ── Quote remarks and Technical Notes ─────────────────────────────────────
    top += 12
    top = _draw_paragraph_block(
        c,
        "Technical Deviation / Remarks:",
        quote_data.get("technical_deviation_remarks", ""),
        top,
    )
    top = _draw_paragraph_block(
        c,
        "Commercial T&C:",
        quote_data.get("commercial_tnc", ""),
        top,
    )
    top = _draw_paragraph_block(
        c,
        "Technical Notes :",
        quote_data.get("technical_notes") or DEFAULT_TECHNICAL_NOTES,
        top,
    )

    # ── Signature and acceptance block, kept together as one unit ────────────
    signature_top = max(top + 18, 472)
    if signature_top + 182 > 785:
        return True, 472
    _draw_signature_block(c, signature_top)
    return False, None


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
    page_no = 1
    if not items:
        items = []

    while True:
        _draw_header(c, quote_data, logo_path)
        idx = _draw_items_page(c, items, quote_data, idx)
        _draw_page_outer_border(c)
        _draw_page_number(c, page_no)
        c.showPage()
        page_no += 1
        if idx >= len(items):
            break

    _draw_header(c, quote_data, logo_path, show_pan=False)
    _draw_general_terms_page(c)
    _draw_page_outer_border(c)
    _draw_page_number(c, page_no)
    c.showPage()
    page_no += 1

    _draw_header(c, quote_data, logo_path, show_pan=False)
    needs_signature_page, signature_top = _draw_terms_page(c, items, quote_data)
    _draw_page_outer_border(c)
    _draw_page_number(c, page_no)
    if needs_signature_page:
        c.showPage()
        page_no += 1
        _draw_header(c, quote_data, logo_path, show_pan=False)
        _draw_signature_block(c, signature_top or 472)
        _draw_page_outer_border(c)
        _draw_page_number(c, page_no)
    c.save()
    return buf.getvalue()
