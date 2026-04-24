"""
Generates a professional GGPL Sales Quotation PDF using ReportLab.
Layout mirrors the official GGPL quotation template (ref: QT00102 R1).
"""
from __future__ import annotations
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer,
    HRFlowable, Image, KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfbase import pdfmetrics

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
NAVY       = colors.HexColor('#1F3864')
LIGHT_BLUE = colors.HexColor('#D9E1F2')
DARK_GREY  = colors.HexColor('#404040')
MID_GREY   = colors.HexColor('#808080')
LIGHT_GREY = colors.HexColor('#F5F5F5')
WHITE      = colors.white
GOLD       = colors.HexColor('#C09000')
GREEN_BG   = colors.HexColor('#E2EFDA')
YELLOW_BG  = colors.HexColor('#FFF2CC')
RED_BG     = colors.HexColor('#FFE0E0')
GREY_BG    = colors.HexColor('#E0E0E0')
BORDER_CLR = colors.HexColor('#8EA9C1')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
COMPANY_NAME = "GOODRICH GASKET PRIVATE LIMITED"
COMPANY_ADDRESS = (
    "Regd.Office & Works : 40, Velichai Village, Next to: Pasupathi Eswaran Temple,\n"
    "Opp.Road to: Pudupakkam Anjaneyar Hill Temple, Vandalur-Kelambakkam Road,\n"
    "Chennai - 600127, Tamil Nadu, India.\n"
    "Tel: +91-44-67400004 - 99 / +91-7824017150 / 7824017151     "
    "Fax: +91-44-67400003\n"
    "Email: goodrichgasket@gmail.com / info@flosil.com     "
    "Web: www.goodrichgasket.com / www.flosil.com\n"
    "IT PAN No.: AABCG2902K     CIN: U27209TN1987PTC014031     GSTIN NO: 33AABCG2902K1ZY"
)

GENERAL_TERMS = (
    "<b>GENERAL TERMS OF QUOTATION:</b><br/>"
    "1) The \"purchase\" fully acknowledges that he/she has read the \"General Terms of Quote\" and agrees "
    "to mention the above clauses in the Purchase Order.<br/>"
    "2) Products will be shipped only to the \"Shipping Address\" mentioned in the Purchase Order.<br/>"
    "3) For any dispute jurisdiction will be Chennai city civil court or Chennai High Court Only.<br/>"
    "4) The delivery quoted is subject to standard Force Majeure conditions which will be beyond our "
    "control like Lockdowns, Natural disasters, Epidemics, Pandemics, Act of God, Ordinance of all "
    "relevant Government Authorities and if there is a delay on account of the above, Goodrich shall "
    "not be considered in default in the performance of its obligations.<br/>"
    "5) The above offer pricing is ONLY applicable for the offered part numbers and quantities despatched "
    "in one lot. GGPL reserves the right to change the prices if the order is partial or dispatched in "
    "several shipments.<br/>"
    "6) Ex-stock items are subject to prior sales."
)

PAGE_W, PAGE_H = A4          # 210mm × 297mm
L_MAR = R_MAR = 12 * mm
T_MAR = B_MAR = 12 * mm
USABLE_W = PAGE_W - L_MAR - R_MAR   # ~186mm

# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------
def _ps(name, **kw) -> ParagraphStyle:
    defaults = dict(fontName='Helvetica', fontSize=8, leading=10,
                    textColor=DARK_GREY, alignment=TA_LEFT)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


S_COMPANY   = _ps('company',   fontName='Helvetica-Bold', fontSize=13,
                  textColor=NAVY, alignment=TA_CENTER, leading=16)
S_ADDR      = _ps('addr',      fontSize=7.5, textColor=DARK_GREY,
                  alignment=TA_CENTER, leading=10)
S_TITLE     = _ps('title',     fontName='Helvetica-Bold', fontSize=12,
                  textColor=WHITE, alignment=TA_CENTER, leading=15)
S_LABEL     = _ps('label',     fontName='Helvetica-Bold', fontSize=7.5,
                  textColor=NAVY, alignment=TA_RIGHT)
S_VALUE     = _ps('value',     fontSize=8, textColor=DARK_GREY)
S_VALUE_C   = _ps('value_c',   fontSize=8, textColor=DARK_GREY, alignment=TA_CENTER)
S_SECT_HDR  = _ps('sect_hdr',  fontName='Helvetica-Bold', fontSize=8,
                  textColor=WHITE, alignment=TA_LEFT)
S_TBL_HDR   = _ps('tbl_hdr',   fontName='Helvetica-Bold', fontSize=8,
                  textColor=WHITE, alignment=TA_CENTER, leading=10)
S_TBL_CELL  = _ps('tbl_cell',  fontSize=7.5, textColor=DARK_GREY, leading=10)
S_TBL_CELL_C= _ps('tbl_cell_c',fontSize=7.5, textColor=DARK_GREY,
                  alignment=TA_CENTER, leading=10)
S_TBL_CELL_R= _ps('tbl_cell_r',fontSize=7.5, textColor=DARK_GREY,
                  alignment=TA_RIGHT, leading=10)
S_TOTAL_LBL = _ps('total_lbl', fontName='Helvetica-Bold', fontSize=8,
                  textColor=NAVY, alignment=TA_RIGHT)
S_TOTAL_VAL = _ps('total_val', fontName='Helvetica-Bold', fontSize=9,
                  textColor=NAVY, alignment=TA_RIGHT)
S_TERMS_LBL = _ps('terms_lbl', fontName='Helvetica-Bold', fontSize=7.5,
                  textColor=NAVY)
S_TERMS_VAL = _ps('terms_val', fontSize=7.5, textColor=DARK_GREY, leading=10)
S_NOTES     = _ps('notes',     fontSize=7.5, textColor=DARK_GREY, leading=10)
S_FOOTER    = _ps('footer',    fontSize=7, textColor=MID_GREY, alignment=TA_CENTER)
S_SIGN      = _ps('sign',      fontName='Helvetica-Bold', fontSize=8,
                  textColor=NAVY, alignment=TA_CENTER)


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(str(text) if text is not None else '', style)


def _fmt_money(val) -> str:
    try:
        return f'{float(val):,.2f}'
    except (TypeError, ValueError):
        return '0.00'


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
def build_quotation_pdf(
    items: list[dict],
    quote_data: dict,
    logo_path: str | None = None,
) -> bytes:
    """
    Returns PDF bytes for a professional GGPL Sales Quotation.

    quote_data keys:
        quote_no, quote_date, rev_no, rev_date,
        buyer_name_address, customer_enq_no, attention, designation,
        contact_no, email,
        rep_name, rep_designation, rep_contact, rep_email,
        price_basis, validity_days, packing, freight,
        gst_type, gst_pct, discount_pct,
        payment_terms, bank_charges, delivery, inspection, insurance,
        ld_clause, cancellation, min_order_value, hsn_code,
        technical_notes,
        unit_prices (list of floats, parallel to items)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=L_MAR, rightMargin=R_MAR,
        topMargin=T_MAR,  bottomMargin=B_MAR,
        title=f"Quotation {quote_data.get('quote_no', '')}",
        author='Goodrich Gasket Pvt. Ltd.',
    )

    story = []
    W = USABLE_W

    # ── 1. Company header ────────────────────────────────────────────────────
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image(logo_path)
            aspect = logo.imageWidth / logo.imageHeight
            logo_h = 16 * mm
            logo_w = logo_h * aspect
            logo.drawWidth  = logo_w
            logo.drawHeight = logo_h

            hdr_table = Table(
                [[logo, _p(COMPANY_NAME, S_COMPANY)]],
                colWidths=[logo_w + 4 * mm, W - logo_w - 4 * mm],
                rowHeights=[logo_h],
            )
            hdr_table.setStyle(TableStyle([
                ('VALIGN',  (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING',  (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ]))
            story.append(hdr_table)
        except Exception:
            story.append(_p(COMPANY_NAME, S_COMPANY))
    else:
        story.append(_p(COMPANY_NAME, S_COMPANY))

    story.append(Spacer(1, 1 * mm))

    # Address block
    for line in COMPANY_ADDRESS.split('\n'):
        story.append(_p(line, S_ADDR))

    story.append(Spacer(1, 1 * mm))
    story.append(HRFlowable(width=W, thickness=2, color=NAVY, spaceAfter=1 * mm))

    # ── 2. SALES QUOTATION title bar ─────────────────────────────────────────
    title_tbl = Table(
        [[_p('SALES QUOTATION', S_TITLE)]],
        colWidths=[W],
        rowHeights=[8 * mm],
    )
    title_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 1 * mm))

    # ── 3. Quote reference row ───────────────────────────────────────────────
    def _lbl_val(label, value):
        return [_p(label, S_LABEL), _p(str(value or ''), S_VALUE)]

    col_q = W * 0.28
    col_v = W * 0.22
    ref_data = [[
        _p('QUOTE NO :', S_LABEL),
        _p(str(quote_data.get('quote_no', '')), S_VALUE),
        _p('DATE :', S_LABEL),
        _p(str(quote_data.get('quote_date', '')), S_VALUE),
        _p('REV NO :', S_LABEL),
        _p(str(quote_data.get('rev_no', '0')), S_VALUE),
        _p('REV DATE :', S_LABEL),
        _p(str(quote_data.get('rev_date', '')), S_VALUE),
    ]]
    cw_ref = [W * 0.13, W * 0.17, W * 0.08, W * 0.16, W * 0.09, W * 0.10, W * 0.11, W * 0.16]
    ref_tbl = Table(ref_data, colWidths=cw_ref, rowHeights=[6 * mm])
    ref_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), LIGHT_BLUE),
        ('BACKGROUND', (2, 0), (2, 0), LIGHT_BLUE),
        ('BACKGROUND', (4, 0), (4, 0), LIGHT_BLUE),
        ('BACKGROUND', (6, 0), (6, 0), LIGHT_BLUE),
        ('BOX',        (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ('INNERGRID',  (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(ref_tbl)
    story.append(Spacer(1, 1 * mm))

    # ── 4. Buyer + GGPL rep side by side ────────────────────────────────────
    left_w  = W * 0.57
    right_w = W * 0.43

    # Buyer left column
    buyer_rows = [
        [_p('Name &amp; Address of the Buyer :', S_SECT_HDR)],
        [_p((quote_data.get('buyer_name_address') or '').replace('\n', '<br/>'), S_VALUE)],
        [_p(f"<b>Customer Enq No :</b>  {quote_data.get('customer_enq_no', '')}", S_VALUE)],
        [_p(f"<b>Kind Attention :</b>  {quote_data.get('attention', '')}", S_VALUE)],
        [_p(f"<b>Designation :</b>  {quote_data.get('designation', '')}", S_VALUE)],
        [_p(f"<b>Contact No :</b>  {quote_data.get('contact_no', '')}", S_VALUE)],
        [_p(f"<b>Email ID :</b>  {quote_data.get('email', '')}", S_VALUE)],
    ]
    buyer_tbl = Table(buyer_rows, colWidths=[left_w - 1 * mm])
    buyer_tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), NAVY),
        ('BOX',          (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ('INNERGRID',    (0, 0), (-1, -1), 0.3, BORDER_CLR),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',   (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
    ]))

    # GGPL rep right column
    rep_rows = [
        [_p('Followed By :', S_SECT_HDR)],
        [_p(f"<b>Name :</b>  {quote_data.get('rep_name', '')}", S_VALUE)],
        [_p(f"<b>Designation :</b>  {quote_data.get('rep_designation', '')}", S_VALUE)],
        [_p(f"<b>Contact No :</b>  {quote_data.get('rep_contact', '')}", S_VALUE)],
        [_p(f"<b>Email ID :</b>  {quote_data.get('rep_email', '')}", S_VALUE)],
    ]
    rep_tbl = Table(rep_rows, colWidths=[right_w])
    rep_tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), NAVY),
        ('BOX',          (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ('INNERGRID',    (0, 0), (-1, -1), 0.3, BORDER_CLR),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',   (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
    ]))

    two_col = Table(
        [[buyer_tbl, rep_tbl]],
        colWidths=[left_w, right_w],
    )
    two_col.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 2 * mm))

    # ── 5. Items table ───────────────────────────────────────────────────────
    unit_prices = quote_data.get('unit_prices', [])
    currency = (quote_data.get('currency') or 'INR').upper()

    # Column widths (total = W)
    cw_items = [
        W * 0.05,   # Sl.No
        W * 0.05,   # Cust Sl.No
        W * 0.10,   # Cust Item Code
        W * 0.46,   # Description
        W * 0.07,   # Qty
        W * 0.07,   # UOM
        W * 0.10,   # Unit Price
        W * 0.10,   # Total Price
    ]

    hdr_row = [
        _p('Sl.\nNo.', S_TBL_HDR),
        _p('Cust\nSl.No', S_TBL_HDR),
        _p('Cust\nItem Code', S_TBL_HDR),
        _p('Material Description', S_TBL_HDR),
        _p('Qty', S_TBL_HDR),
        _p('UOM', S_TBL_HDR),
        _p(f'Unit Price\n({currency})', S_TBL_HDR),
        _p(f'Total Price\n({currency})', S_TBL_HDR),
    ]

    tbl_data = [hdr_row]
    tbl_styles = [
        # Header
        ('BACKGROUND',   (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR',    (0, 0), (-1, 0), WHITE),
        ('ALIGN',        (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',         (0, 0), (-1, -1), 0.4, BORDER_CLR),
        ('LEFTPADDING',  (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING',   (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
    ]

    total_qty  = 0.0
    subtotal   = 0.0

    for idx, item in enumerate(items):
        status = item.get('status', 'missing')
        row_idx = idx + 1   # offset for header row

        if status == 'regret':
            row_bg = GREY_BG
        elif status == 'missing':
            row_bg = RED_BG
        elif status == 'check':
            row_bg = YELLOW_BG
        else:
            row_bg = WHITE

        qty = item.get('quantity') or 0
        uom = item.get('uom') or 'NOS'
        unit_price  = float(unit_prices[idx]) if idx < len(unit_prices) and unit_prices[idx] else 0.0
        total_price = float(qty) * unit_price
        total_qty  += float(qty)
        subtotal   += total_price

        ggpl_desc = ('REGRET — CANNOT PRODUCE' if status == 'regret'
                     else item.get('ggpl_description', ''))

        tbl_data.append([
            _p(str(idx + 1),       S_TBL_CELL_C),
            _p(str(idx + 1),       S_TBL_CELL_C),
            _p('',                 S_TBL_CELL_C),
            _p(ggpl_desc,          S_TBL_CELL),
            _p(str(qty),           S_TBL_CELL_C),
            _p(uom,                S_TBL_CELL_C),
            _p(_fmt_money(unit_price),  S_TBL_CELL_R),
            _p(_fmt_money(total_price), S_TBL_CELL_R),
        ])
        tbl_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), row_bg))

    items_tbl = Table(tbl_data, colWidths=cw_items, repeatRows=1)
    items_tbl.setStyle(TableStyle(tbl_styles))
    story.append(items_tbl)
    story.append(Spacer(1, 1 * mm))

    # ── 6. Totals ────────────────────────────────────────────────────────────
    discount_pct = float(quote_data.get('discount_pct') or 0)
    discount_amt = subtotal * discount_pct / 100
    net_before_tax = subtotal - discount_amt

    gst_type = quote_data.get('gst_type', 'IGST')
    gst_pct  = float(quote_data.get('gst_pct') or 18)
    gst_amt  = round(net_before_tax * gst_pct / 100, 2)
    grand_total = net_before_tax + gst_amt

    totals_cw = [W * 0.60, W * 0.20, W * 0.20]

    totals_data = []
    totals_styles = [
        ('GRID',         (0, 0), (-1, -1), 0.4, BORDER_CLR),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',   (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
    ]

    def _tot_row(label, qty_val, amt_val, bg=LIGHT_GREY, bold=False):
        s_l = S_TOTAL_LBL if bold else S_TERMS_LBL
        s_v = S_TOTAL_VAL if bold else S_TERMS_VAL
        return [
            _p(label, s_l),
            _p(str(qty_val) if qty_val != '' else '', _ps('tv_c', fontName='Helvetica-Bold' if bold else 'Helvetica',
                fontSize=8 if bold else 7.5, textColor=NAVY if bold else DARK_GREY, alignment=TA_CENTER)),
            _p(amt_val, s_v),
        ]

    totals_data.append(_tot_row('Total Qty & Amount :', f'{total_qty:g}', _fmt_money(subtotal)))
    totals_styles.append(('BACKGROUND', (0, 0), (-1, 0), LIGHT_BLUE))

    if discount_pct > 0:
        totals_data.append(_tot_row(f'Discount @ {discount_pct:.2f}% :', '', f'- {_fmt_money(discount_amt)}'))
        totals_data.append(_tot_row('Amount After Discount :', '', _fmt_money(net_before_tax)))
        totals_styles.append(('BACKGROUND', (0, 1), (-1, 1), LIGHT_GREY))
        totals_styles.append(('BACKGROUND', (0, 2), (-1, 2), LIGHT_BLUE))

    if gst_type == 'IGST':
        gst_rows = [(f'IGST @ {gst_pct:.2f}%', gst_amt),
                    ('CGST @ 0.00%', 0.0), ('SGST @ 0.00%', 0.0), ('UGST @ 0.00%', 0.0)]
    elif gst_type == 'CGST+SGST':
        half = round(gst_amt / 2, 2)
        gst_rows = [('IGST @ 0.00%', 0.0),
                    (f'CGST @ {gst_pct / 2:.2f}%', half),
                    (f'SGST @ {gst_pct / 2:.2f}%', half),
                    ('UGST @ 0.00%', 0.0)]
    else:
        gst_rows = [('IGST @ 0.00%', 0.0), ('CGST @ 0.00%', 0.0),
                    ('SGST @ 0.00%', 0.0), (f'UGST @ {gst_pct:.2f}%', gst_amt)]

    base_row = len(totals_data)
    for lbl, amt in gst_rows:
        totals_data.append(_tot_row(f'{lbl} :', '', _fmt_money(amt)))
    for i in range(4):
        totals_styles.append(('BACKGROUND', (0, base_row + i), (-1, base_row + i), LIGHT_GREY))

    grand_row = len(totals_data)
    totals_data.append(_tot_row(f'GRAND TOTAL ({currency}) :', '', _fmt_money(grand_total), bold=True))
    totals_styles.append(('BACKGROUND',  (0, grand_row), (-1, grand_row), LIGHT_BLUE))
    totals_styles.append(('FONTSIZE',    (0, grand_row), (-1, grand_row), 9))
    totals_styles.append(('FONTNAME',    (0, grand_row), (-1, grand_row), 'Helvetica-Bold'))
    totals_styles.append(('TEXTCOLOR',   (0, grand_row), (-1, grand_row), NAVY))

    totals_tbl = Table(totals_data, colWidths=totals_cw)
    totals_tbl.setStyle(TableStyle(totals_styles))
    story.append(totals_tbl)
    story.append(Spacer(1, 2 * mm))

    # ── 7. Terms & Conditions ────────────────────────────────────────────────
    terms_hdr = Table(
        [[_p('Terms &amp; Conditions :', S_SECT_HDR)]],
        colWidths=[W], rowHeights=[6 * mm],
    )
    terms_hdr.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',(0, 0), (-1, -1), 4),
    ]))
    story.append(terms_hdr)

    terms = [
        ('1. Price Basis',          str(quote_data.get('price_basis', 'FOR BASIS'))),
        ('2. Validity',             f"{quote_data.get('validity_days', '7')} DAYS"),
        ('3. Packing &amp; Forwarding', str(quote_data.get('packing', 'INCLUSIVE'))),
        ('4. Freight',              str(quote_data.get('freight', 'INCLUSIVE'))),
        ('5. Taxes and Duties',
         f"GST ({gst_type}) @ {gst_pct:.2f}% = {currency} {_fmt_money(gst_amt)}. "
         "Taxes and duties shall be paid at actuals as applicable at the time of shipment."),
        ('6. Payment Terms',        str(quote_data.get('payment_terms',
                                        '30% ADVANCE & 70% BALANCE BEFORE DISPATCH OF MATERIAL'))),
        ('7. Bank Charges',         str(quote_data.get('bank_charges', 'TO YOUR ACCOUNT'))),
        ('8. Delivery',             str(quote_data.get('delivery', ''))),
        ('9. Inspection',           str(quote_data.get('inspection', 'Not Applicable'))),
        ('10. Insurance',           str(quote_data.get('insurance', 'TO YOUR ACCOUNT'))),
        ('11. HSN Code',            str(quote_data.get('hsn_code', '84841010'))),
        ('12. LD Clause',           str(quote_data.get('ld_clause', 'Not Applicable'))),
        ('13. Cancellation',        str(quote_data.get('cancellation',
                                        'Products are manufactured on order and hence Goodrich will '
                                        'not be able to accept cancellation of order or reduction in quantity.'))),
        ('14. Minimum Order Value', str(quote_data.get('min_order_value',
                                        'INR 10,000. No order can be processed below the same.'))),
    ]

    terms_cw = [W * 0.22, W * 0.78]
    terms_data = []
    terms_styles = [
        ('GRID',         (0, 0), (-1, -1), 0.4, BORDER_CLR),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',   (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
    ]
    for i, (lbl, val) in enumerate(terms):
        terms_data.append([_p(lbl, S_TERMS_LBL), _p(val, S_TERMS_VAL)])
        if i % 2 == 0:
            terms_styles.append(('BACKGROUND', (0, i), (0, i), LIGHT_BLUE))
        else:
            terms_styles.append(('BACKGROUND', (0, i), (0, i), LIGHT_GREY))

    terms_tbl = Table(terms_data, colWidths=terms_cw)
    terms_tbl.setStyle(TableStyle(terms_styles))
    story.append(terms_tbl)
    story.append(Spacer(1, 2 * mm))

    # ── 8. Technical Notes ───────────────────────────────────────────────────
    tech_notes = quote_data.get('technical_notes', '')
    if tech_notes:
        tech_hdr = Table(
            [[_p('Technical Notes :', S_SECT_HDR)]],
            colWidths=[W], rowHeights=[6 * mm],
        )
        tech_hdr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',(0, 0), (-1, -1), 4),
        ]))
        story.append(tech_hdr)

        notes_tbl = Table(
            [[_p(tech_notes.replace('\n', '<br/>'), S_NOTES)]],
            colWidths=[W],
        )
        notes_tbl.setStyle(TableStyle([
            ('BOX',          (0, 0), (-1, -1), 0.4, BORDER_CLR),
            ('LEFTPADDING',  (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING',   (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ]))
        story.append(notes_tbl)
        story.append(Spacer(1, 2 * mm))

    # ── 9. General Terms ─────────────────────────────────────────────────────
    gen_tbl = Table(
        [[_p(GENERAL_TERMS, _ps('gen', fontSize=7, leading=10, textColor=DARK_GREY))]],
        colWidths=[W],
    )
    gen_tbl.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.4, BORDER_CLR),
        ('LEFTPADDING',  (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('BACKGROUND',   (0, 0), (-1, -1), LIGHT_GREY),
    ]))
    story.append(gen_tbl)
    story.append(Spacer(1, 3 * mm))

    # ── 10. Authorised Signatory ─────────────────────────────────────────────
    sign_tbl = Table(
        [[_p('', S_SIGN), _p('For Goodrich Gasket Pvt. Ltd.', S_SIGN)],
         [_p('', S_SIGN), _p('Authorised Signatory', S_SIGN)]],
        colWidths=[W * 0.55, W * 0.45],
        rowHeights=[6 * mm, 10 * mm],
    )
    sign_tbl.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.5, BORDER_CLR),
        ('INNERGRID',    (0, 0), (-1, -1), 0.3, BORDER_CLR),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND',   (1, 0), (1, 0), LIGHT_BLUE),
        ('BACKGROUND',   (1, 1), (1, 1), LIGHT_GREY),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
    ]))
    story.append(sign_tbl)
    story.append(Spacer(1, 2 * mm))

    # ── 11. Footer ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=MID_GREY))
    story.append(Spacer(1, 1 * mm))
    story.append(_p(
        'This is a Computer Generated Document — Signature Not Required',
        S_FOOTER,
    ))

    doc.build(story)
    return buf.getvalue()
