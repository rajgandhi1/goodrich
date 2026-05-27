"""
Generates a professional GGPL Sales Quotation Excel file.
Layout mirrors the official GGPL quotation template (ref: QT00102 R1).
"""
from __future__ import annotations
import io
import os
import datetime
import xlsxwriter

# ---------------------------------------------------------------------------
# Company constants
# ---------------------------------------------------------------------------
COMPANY_NAME = "GOODRICH GASKET PRIVATE LIMITED"
COMPANY_ADDRESS_LINES = [
    "Regd. Office & Works: 40, Velichai Village, Next to: Pasupathi Eswaran Temple,",
    "Opp.Road to: Pudupakkam Anjaneyar Hill Temple, Vandalur-Kelambakkam Road,",
    "Chennai - 600127, Tamil Nadu, India.",
    "Email: info@flosil.com",
    "IT PAN No.: AABCG2902K   CIN: U27209TN1987PTC014031   GSTIN NO: 33AABCG2902K1ZY",
]

GENERAL_TERMS = (
    "GENERAL TERMS OF QUOTATION:\n"
    "1. Delivery Terms: Delivery is subject to final acceptance of the purchase order by Goodrich, including acceptance of commercial terms and conditions, technical deviations, and replies to technical queries. Production release note and contractual delivery date will start only after pending issues are resolved.\n"
    "2. Express Deliveries: Any shorter delivery requirement must be requested in writing before purchase order placement. Goodrich may accept or reject the request. Approved express delivery charges shall be borne by the customer, and LD shall not apply for express deliveries.\n"
    "3. Payment Terms: Payment terms shall be as negotiated and agreed. Delayed payments beyond agreed terms shall attract interest at 18% per annum on a pro-rata basis.\n"
    "4. Liquidated Damages LD Clause: Not applicable.\n"
    "5. Storage Charge: If dispatch approval or dispatch arrangement is delayed by the customer, storage charges at 1% per month plus GST shall apply on a pro-rata basis. Delays beyond 60 days will not be accepted, and the consignment may be dispatched without further notice.\n"
    "6. Order Cancellation or Amendment: After purchase order placement, cancellation or amendment will not be accepted. If cancelled or amended, full payment shall be made as per the original purchase order.\n"
    "7. Delivery Dates: If production is completed early, the customer shall settle payment and authorize dispatch.\n"
    "8. Acknowledgement of Terms: The purchaser acknowledges that they have read and agreed to the General Terms of Quotation and shall include these clauses in the purchase order.\n"
    "9. Shipping Address: Products will be shipped only to the \"Shipping Address\" mentioned in the purchase order.\n"
    "10. Jurisdiction for Disputes: For any dispute, jurisdiction will be Chennai City Civil Court or Chennai High Court only.\n"
    "11. Force Majeure: Delivery is subject to Force Majeure conditions beyond Goodrich control, including lockdowns, natural disasters, epidemics, pandemics, acts of God, and government ordinances. Delays due to such events shall not be considered default by Goodrich.\n"
    "12. Pricing Validity: Pricing is applicable only for the offered part numbers and quantities dispatched in one lot. Goodrich reserves the right to revise prices for partial or multiple shipments.\n"
    "13. Ex-Stock Items: Ex-stock items are subject to prior sales.\n"
    "We trust that our rates are competitive and our terms and conditions are acceptable. We look forward to receiving your valued order."
)

DEFAULT_TECHNICAL_NOTES = (
    "1. Certifications: MTC to EN10204-3.1 for metallic parts and EN10204-2.1 for non-metallic.\n"
    "2. Testing Charges for gasket will be extra at actuals for tests other than compression & sealability test and chemical analysis."
)

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
_NAVY       = '#1F3864'
_LIGHT_BLUE = '#D9E1F2'
_DARK_GREY  = '#404040'
_MID_GREY   = '#808080'
_LIGHT_GREY = '#F2F2F2'
_WHITE      = '#FFFFFF'
_GOLD       = '#C09000'
_GREEN_BG   = '#E2EFDA'
_YELLOW_BG  = '#FFEB9C'
_RED_BG     = '#FFC7CE'
_GREY_BG    = '#D9D9D9'
_BORDER     = '#8EA9C1'

# Column layout (10 columns: A-J)
# A=SlNo(4), B=CustSlNo(7), C=CustCode(12), D=Description(55), E=Qty(8), F=UOM(7), G=UnitPrice(14), H=TotalPrice(14)
# Extra cols I, J for right-side use
COL_WIDTHS = [4, 7, 12, 55, 8, 7, 14, 14, 18, 18]
NCOLS = len(COL_WIDTHS)  # 10


def _col(n: int) -> str:
    """0-based int → Excel column letter."""
    result = ''
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


def _cr(row: int, col: int) -> str:
    """0-based row,col → 'A1' reference."""
    return f'{_col(col)}{row + 1}'


def _range(r1: int, c1: int, r2: int, c2: int) -> str:
    return f'{_cr(r1, c1)}:{_cr(r2, c2)}'


def build_quotation_excel(
    items: list[dict],
    quote_data: dict,
    logo_path: str | None = None,
) -> bytes:
    """
    Build a professional GGPL sales quotation Excel.

    quote_data keys:
        quote_no, quote_date, rev_no, rev_date,
        buyer_name_address, customer_enq_no, attention, designation, contact_no,
        mobile_no, telephone_no, email,
        rep_name, rep_designation, rep_contact, rep_email,
        price_basis, validity_days, packing, freight,
        gst_type, gst_pct, discount_pct,
        payment_terms, bank_charges, delivery, inspection, insurance,
        ld_clause, cancellation, min_order_value, hsn_code,
        technical_deviation_remarks, commercial_tnc,
        technical_notes,
        unit_prices (list of floats, parallel to items)
    """
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Quotation')

    # ── Set column widths ────────────────────────────────────────────────────
    for i, w in enumerate(COL_WIDTHS):
        ws.set_column(i, i, w)

    # ── Format palette ───────────────────────────────────────────────────────
    def _fmt(**kw):
        defaults = {'font_name': 'Calibri', 'font_size': 9,
                    'valign': 'vcenter', 'border': 0}
        defaults.update(kw)
        return wb.add_format(defaults)

    f_company   = _fmt(bold=True, font_size=14, font_color=_NAVY, align='center')
    f_addr      = _fmt(font_size=8, font_color=_DARK_GREY, align='center')
    f_title     = _fmt(bold=True, font_size=13, font_color=_WHITE,
                       bg_color=_NAVY, align='center', valign='vcenter')
    f_ref_label = _fmt(bold=True, font_size=8, font_color=_NAVY,
                       bg_color=_LIGHT_BLUE, align='right', border=1, border_color=_BORDER)
    f_ref_val   = _fmt(font_size=9, align='left', border=1, border_color=_BORDER)
    f_sect_hdr  = _fmt(bold=True, font_size=9, font_color=_WHITE,
                       bg_color=_NAVY, align='left', border=1, border_color=_BORDER)
    f_lbl       = _fmt(bold=True, font_size=8, font_color=_NAVY,
                       bg_color=_LIGHT_BLUE, align='right', border=1, border_color=_BORDER)
    f_val       = _fmt(font_size=9, align='left', border=1, border_color=_BORDER,
                       text_wrap=True)
    f_tbl_hdr   = _fmt(bold=True, font_size=9, font_color=_WHITE,
                       bg_color=_NAVY, align='center', border=1, border_color=_BORDER,
                       text_wrap=True, valign='vcenter')
    f_tbl_num   = _fmt(font_size=9, align='center', border=1, border_color=_BORDER)
    f_tbl_desc  = _fmt(font_size=9, align='left', border=1, border_color=_BORDER,
                       text_wrap=True)
    f_tbl_money = _fmt(font_size=9, align='right', border=1, border_color=_BORDER,
                       num_format='#,##0.00')
    f_total_lbl = _fmt(bold=True, font_size=9, font_color=_NAVY,
                       bg_color=_LIGHT_BLUE, align='right', border=1, border_color=_BORDER)
    f_total_val = _fmt(bold=True, font_size=10, align='right', border=1,
                       border_color=_BORDER, num_format='#,##0.00')
    f_terms_hdr = _fmt(bold=True, font_size=9, font_color=_WHITE,
                       bg_color=_NAVY, align='left', border=1, border_color=_BORDER)
    f_terms_lbl = _fmt(bold=True, font_size=8, font_color=_NAVY,
                       bg_color=_LIGHT_GREY, align='left', border=1, border_color=_BORDER)
    f_terms_val = _fmt(font_size=8, align='left', border=1, border_color=_BORDER,
                       text_wrap=True)
    f_notes     = _fmt(font_size=8, align='left', text_wrap=True, border=1,
                       border_color=_BORDER)
    f_sign      = _fmt(bold=True, font_size=9, font_color=_NAVY, align='center',
                       border=1, border_color=_BORDER)
    f_footer    = _fmt(font_size=7, font_color=_MID_GREY, align='center',
                       italic=True)

    row = 0  # current write row (0-based)

    # ── Logo + Company header ────────────────────────────────────────────────
    ws.set_row(row, 50)
    if logo_path and os.path.exists(logo_path):
        # Logo in col A (merged A:B)
        ws.merge_range(_range(row, 0, row, 1), '', _fmt())
        ws.insert_image(row, 0, logo_path, {
            'x_scale': 0.35, 'y_scale': 0.35,
            'x_offset': 5, 'y_offset': 5,
            'object_position': 1,
        })
        # Company name spans cols C-H
        ws.merge_range(_range(row, 2, row, NCOLS - 1), COMPANY_NAME, f_company)
    else:
        ws.merge_range(_range(row, 0, row, NCOLS - 1), COMPANY_NAME, f_company)
    row += 1

    # Address lines
    for line in COMPANY_ADDRESS_LINES:
        ws.set_row(row, 13)
        ws.merge_range(_range(row, 0, row, NCOLS - 1), line, f_addr)
        row += 1

    # Divider row
    ws.set_row(row, 4)
    ws.merge_range(_range(row, 0, row, NCOLS - 1), '',
                   _fmt(bg_color=_NAVY, border=0))
    row += 1

    # ── SALES QUOTATION title ────────────────────────────────────────────────
    ws.set_row(row, 22)
    ws.merge_range(_range(row, 0, row, NCOLS - 1), 'SALES QUOTATION', f_title)
    row += 1

    # ── Quote reference block ────────────────────────────────────────────────
    ws.set_row(row, 16)
    # [QUOTE NO label][val][DATE label][val][REV NO label][val][REV DATE label][val]  (squeeze into 10 cols)
    ws.merge_range(_range(row, 0, row, 1), 'QUOTATION NO.:', f_ref_label)
    ws.merge_range(_range(row, 2, row, 4), quote_data.get('quote_no', ''), f_ref_val)
    ws.write(row, 5, 'Date:', f_ref_label)
    ws.write(row, 6, quote_data.get('quote_date', ''), f_ref_val)
    ws.write(row, 7, 'Rev. No.:', f_ref_label)
    ws.write(row, 8, str(quote_data.get('rev_no', '0')), f_ref_val)
    ws.write(row, 9, 'Rev. Date:', f_ref_label) if NCOLS > 9 else None
    row += 1
    ws.set_row(row, 16)
    ws.merge_range(_range(row, 0, row, 1), '', f_ref_label)
    ws.merge_range(_range(row, 2, row, 4), '', f_ref_val)
    ws.write(row, 5, '', f_ref_val)
    ws.write(row, 6, quote_data.get('rev_date', ''), f_ref_val)
    ws.write(row, 7, '', f_ref_val)
    ws.write(row, 8, '', f_ref_val)
    ws.write(row, 9, quote_data.get('rev_date', ''), f_ref_val) if NCOLS > 9 else None
    row += 1

    # ── Buyer info (left 6 cols) + GGPL rep info (right 4 cols) ─────────────
    # Section headers
    ws.set_row(row, 14)
    ws.merge_range(_range(row, 0, row, 5), 'Name & Address of the Buyer :', f_sect_hdr)
    ws.merge_range(_range(row, 6, row, NCOLS - 1), 'Followed By :', f_sect_hdr)
    row += 1

    # Buyer address block (3 rows tall for address)
    buyer_addr = quote_data.get('buyer_name_address', '')
    addr_rows = 4
    for r in range(addr_rows):
        ws.set_row(row + r, 14)
    ws.merge_range(_range(row, 0, row + addr_rows - 1, 5), buyer_addr,
                   _fmt(font_size=9, align='left', border=1, border_color=_BORDER,
                        text_wrap=True, valign='top'))
    # Rep info (right side)
    rep_fields = [
        ('Name', quote_data.get('rep_name', '')),
        ('Designation', quote_data.get('rep_designation', '')),
        ('Contact No', quote_data.get('rep_contact', '')),
        ('Email ID', quote_data.get('rep_email', '')),
    ]
    for i, (lbl, val) in enumerate(rep_fields):
        if i < addr_rows:
            ws.write(row + i, 6, f'{lbl} :', f_lbl)
            ws.merge_range(_range(row + i, 7, row + i, NCOLS - 1), val, f_val)
    row += addr_rows

    mobile_no = quote_data.get('mobile_no') or quote_data.get('contact_no', '')

    # Customer enquiry / sender details
    buyer_detail_fields = [
        ('Customer Enq No', quote_data.get('customer_enq_no', '')),
        ("Sender's Name", quote_data.get('attention', '')),
        ('Designation', quote_data.get('designation', '')),
        ('Mobile Number', mobile_no),
        ('Telephone No', quote_data.get('telephone_no', '')),
        ('Email ID', quote_data.get('email', '')),
    ]
    for lbl, val in buyer_detail_fields:
        ws.set_row(row, 14)
        ws.merge_range(_range(row, 0, row, 1), f'{lbl} :', f_lbl)
        ws.merge_range(_range(row, 2, row, 5), val, f_val)
        # Right side blank (continuation)
        ws.merge_range(_range(row, 6, row, NCOLS - 1), '', f_val)
        row += 1

    # ── Items table ──────────────────────────────────────────────────────────
    currency = quote_data.get('currency', 'INR')

    ws.set_row(row, 30)
    tbl_headers = ['Sl.\nNo.', 'Cust\nSl.No', 'Customer\nItem Code',
                   'Material Description', 'Qty', 'UOM',
                   f'Unit Price\n({currency})', f'Total Price\n({currency})']
    tbl_col_map = [0, 1, 2, 3, 4, 5, 6, 7]  # column indices

    for i, (col_idx, hdr) in enumerate(zip(tbl_col_map, tbl_headers)):
        if i == 3:  # description — span 1 col (col 3)
            ws.write(row, col_idx, hdr, f_tbl_hdr)
        elif i == 7:  # total price — span cols 7-9
            ws.merge_range(_range(row, 7, row, NCOLS - 1), hdr, f_tbl_hdr)
        else:
            ws.write(row, col_idx, hdr, f_tbl_hdr)
    row += 1

    unit_prices = quote_data.get('unit_prices', [])
    total_qty = 0.0
    subtotal  = 0.0

    for idx, item in enumerate(items):
        status = item.get('status', 'missing')
        if status == 'regret':
            row_bg = _GREY_BG
        elif status == 'missing':
            row_bg = _RED_BG
        elif status == 'check':
            row_bg = _YELLOW_BG
        else:
            row_bg = _WHITE

        rfmt_num  = _fmt(font_size=9, align='center', border=1,
                         border_color=_BORDER, bg_color=row_bg)
        rfmt_desc = _fmt(font_size=9, align='left', border=1,
                         border_color=_BORDER, text_wrap=True, bg_color=row_bg)
        rfmt_money = _fmt(font_size=9, align='right', border=1,
                          border_color=_BORDER, num_format='#,##0.00', bg_color=row_bg)

        qty = item.get('quantity') or 0
        uom = item.get('uom') or 'NOS'
        unit_price = unit_prices[idx] if idx < len(unit_prices) else 0.0
        quoted_qty = 0 if status == 'regret' else qty
        total_price = quoted_qty * unit_price if unit_price else 0.0
        total_qty  += float(quoted_qty) if quoted_qty else 0
        subtotal   += total_price

        ggpl_desc = ('REGRET — CANNOT PRODUCE' if status == 'regret'
                     else item.get('ggpl_description', ''))

        # Row height: taller for long descriptions
        ws.set_row(row, max(20, min(60, 15 + len(ggpl_desc) // 8)))

        ws.write(row, 0, idx + 1,              rfmt_num)
        ws.write(row, 1, item.get('customer_sl_no') or '', rfmt_num)
        ws.write(row, 2, item.get('customer_item_code') or '', rfmt_num)
        ws.write(row, 3, ggpl_desc,            rfmt_desc)
        ws.write(row, 4, qty,                  rfmt_num)
        ws.write(row, 5, uom,                  rfmt_num)
        ws.write(row, 6, unit_price,           rfmt_money)
        ws.merge_range(_range(row, 7, row, NCOLS - 1), total_price, rfmt_money)
        row += 1

    # ── Totals section ───────────────────────────────────────────────────────
    ws.set_row(row, 16)
    ws.merge_range(_range(row, 0, row, 5), 'Total Qty :', f_total_lbl)
    ws.write(row, 6, total_qty, f_total_val)
    ws.merge_range(_range(row, 7, row, NCOLS - 1), subtotal, f_total_val)
    row += 1

    # Discount
    discount_pct = float(quote_data.get('discount_pct') or 0)
    discount_amt = subtotal * discount_pct / 100
    net_before_tax = subtotal - discount_amt
    if discount_pct > 0:
        ws.set_row(row, 16)
        ws.merge_range(_range(row, 0, row, 5),
                       f'Discount @ {discount_pct:.2f}% :', f_total_lbl)
        ws.write(row, 6, '', f_total_val)
        ws.merge_range(_range(row, 7, row, NCOLS - 1), discount_amt, f_total_val)
        row += 1
        ws.set_row(row, 16)
        ws.merge_range(_range(row, 0, row, 5), 'Amount After Discount :', f_total_lbl)
        ws.write(row, 6, '', f_total_val)
        ws.merge_range(_range(row, 7, row, NCOLS - 1), net_before_tax, f_total_val)
        row += 1

    # GST calculation
    gst_type = quote_data.get('gst_type', 'IGST')
    gst_pct  = float(quote_data.get('gst_pct') or 18)
    gst_amt  = round(net_before_tax * gst_pct / 100, 2) if currency == 'INR' else 0.0
    grand_total = net_before_tax + gst_amt

    if currency != 'INR':
        gst_rows = [(f'Tax / Duty ({currency})', gst_amt)]
    elif gst_type == 'IGST':
        gst_rows = [(f'IGST @ {gst_pct:.2f}%', gst_amt),
                    ('CGST @ 0.00%', 0.0), ('SGST @ 0.00%', 0.0), ('UGST @ 0.00%', 0.0)]
    elif gst_type == 'CGST+SGST':
        half = round(gst_amt / 2, 2)
        gst_rows = [('IGST @ 0.00%', 0.0),
                    (f'CGST @ {gst_pct / 2:.2f}%', half),
                    (f'SGST @ {gst_pct / 2:.2f}%', half),
                    ('UGST @ 0.00%', 0.0)]
    else:  # UGST
        gst_rows = [('IGST @ 0.00%', 0.0), ('CGST @ 0.00%', 0.0),
                    ('SGST @ 0.00%', 0.0), (f'UGST @ {gst_pct:.2f}%', gst_amt)]

    for lbl, amt in gst_rows:
        ws.set_row(row, 14)
        ws.merge_range(_range(row, 0, row, 5), lbl + ' :', f_total_lbl)
        ws.write(row, 6, '', f_total_val)
        ws.merge_range(_range(row, 7, row, NCOLS - 1), amt, f_total_val)
        row += 1

    ws.set_row(row, 18)
    ws.merge_range(_range(row, 0, row, 5), f'GRAND TOTAL ({currency}) :', f_total_lbl)
    ws.write(row, 6, '', _fmt(bold=True, font_size=11, font_color=_NAVY,
                               bg_color=_LIGHT_BLUE, align='right', border=1,
                               border_color=_BORDER, num_format='#,##0.00'))
    ws.merge_range(_range(row, 7, row, NCOLS - 1), grand_total,
                   _fmt(bold=True, font_size=11, font_color=_NAVY,
                        bg_color=_LIGHT_BLUE, align='right', border=1,
                        border_color=_BORDER, num_format='#,##0.00'))
    row += 1

    # ── General Terms ────────────────────────────────────────────────────────
    ws.set_row(row, 14)
    ws.merge_range(_range(row, 0, row, NCOLS - 1), 'GENERAL TERMS OF QUOTATION:', f_terms_hdr)
    row += 1
    gt_h = max(110, 11 * (GENERAL_TERMS.count('\n') + 4))
    ws.set_row(row, min(gt_h, 260))
    ws.merge_range(_range(row, 0, row, NCOLS - 1), GENERAL_TERMS,
                   _fmt(font_size=7.5, align='left', text_wrap=True, border=1,
                        border_color=_BORDER, valign='top'))
    row += 1

    # ── Other Terms & Conditions ─────────────────────────────────────────────
    ws.set_row(row, 14)
    ws.merge_range(_range(row, 0, row, NCOLS - 1),
                   'Other Terms & Conditions :', f_terms_hdr)
    row += 1

    terms = [
        ('1. Price Basis',          quote_data.get('price_basis', 'FOR BASIS')),
        ('2. Validity',             f"{quote_data.get('validity_days', '7')} DAYS"),
        ('3. Packing & Forwarding', quote_data.get('packing', 'INCLUSIVE')),
        ('4. Freight',              quote_data.get('freight', 'INCLUSIVE')),
        ('5. Taxes and Duties',
         (f"GST ({gst_type}) @ {gst_pct:.2f}% = INR {gst_amt:,.2f}. "
          "Taxes and duties shall be paid at actuals as applicable at the time of shipment.")
         if currency == 'INR'
         else "Taxes and duties shall be paid at actuals as applicable at the time of shipment."),
        ('6. Payment Terms',        quote_data.get('payment_terms',
                                                    '30% ADVANCE & 70% BALANCE BEFORE DISPATCH OF MATERIAL')),
        ('7. Bank Charges',         quote_data.get('bank_charges', 'TO YOUR ACCOUNT')),
        ('8. Delivery',             quote_data.get('delivery', '')),
        ('9. Inspection',           quote_data.get('inspection', 'Not Applicable')),
        ('10. Insurance',           quote_data.get('insurance', 'TO YOUR ACCOUNT')),
        ('11. HSN Code',            quote_data.get('hsn_code', '84841010')),
        ('12. LD Clause',           quote_data.get('ld_clause', 'Not Applicable')),
        ('13. Cancellation',        quote_data.get('cancellation',
                                                    'Products are manufactured on order and hence Goodrich will '
                                                    'not be able to accept cancellation of order or reduction in '
                                                    'quantity.')),
        ('14. Minimum Order Value', quote_data.get('min_order_value',
                                                    'INR 10,000. No order can be processed below the same.')),
    ]

    for lbl, val in terms:
        val_lines = (val.count('\n') + 1) if val else 1
        h = max(14, min(40, 13 * val_lines))
        ws.set_row(row, h)
        ws.merge_range(_range(row, 0, row, 1), lbl, f_terms_lbl)
        ws.merge_range(_range(row, 2, row, NCOLS - 1), val, f_terms_val)
        row += 1

    for title, value in [
        ('Technical Deviation / Remarks:', quote_data.get('technical_deviation_remarks', '')),
        ('Commercial T&C:', quote_data.get('commercial_tnc', '')),
    ]:
        if value:
            ws.set_row(row, 14)
            ws.merge_range(_range(row, 0, row, NCOLS - 1), title, f_terms_hdr)
            row += 1
            note_h = max(30, min(120, 12 * (value.count('\n') + 2)))
            ws.set_row(row, note_h)
            ws.merge_range(_range(row, 0, row, NCOLS - 1), value, f_notes)
            row += 1

    # ── Technical Notes ──────────────────────────────────────────────────────
    tech_notes = quote_data.get('technical_notes') or DEFAULT_TECHNICAL_NOTES
    if tech_notes:
        ws.set_row(row, 14)
        ws.merge_range(_range(row, 0, row, NCOLS - 1), 'Technical Notes :', f_terms_hdr)
        row += 1
        note_h = max(30, min(100, 12 * (tech_notes.count('\n') + 2)))
        ws.set_row(row, note_h)
        ws.merge_range(_range(row, 0, row, NCOLS - 1), tech_notes, f_notes)
        row += 1

    # ── Authorized Signatory ─────────────────────────────────────────────────
    ws.set_row(row, 14)
    ws.merge_range(_range(row, 0, row, 5), '', _fmt(border=1, border_color=_BORDER))
    ws.merge_range(_range(row, 6, row, NCOLS - 1),
                   'For Goodrich Gasket Pvt. Ltd.', f_sign)
    row += 1
    ws.set_row(row, 30)
    ws.merge_range(_range(row, 0, row, 5), '', _fmt(border=1, border_color=_BORDER))
    ws.merge_range(_range(row, 6, row, NCOLS - 1), 'Authorised Signatory', f_sign)
    row += 1

    # ── Footer ───────────────────────────────────────────────────────────────
    ws.set_row(row, 12)
    ws.merge_range(_range(row, 0, row, NCOLS - 1),
                   'This is a Computer Generated Document — Signature Not Required',
                   f_footer)

    # ── Print settings ───────────────────────────────────────────────────────
    ws.set_paper(9)            # A4
    ws.set_landscape()
    ws.set_margins(left=0.4, right=0.4, top=0.4, bottom=0.4)
    ws.fit_to_pages(1, 0)
    ws.set_zoom(80)

    wb.close()
    return output.getvalue()
