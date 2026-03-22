from __future__ import annotations
"""
Builds the output Excel file from processed items.
Green = ready, Yellow = defaults applied, Red = missing critical info.
"""
import io
import xlsxwriter


_GREEN  = '#C6EFCE'
_YELLOW = '#FFEB9C'
_RED    = '#FFC7CE'
_HEADER = '#1F6FB2'


def build_excel(items: list[dict], customer: str = '', project_ref: str = '') -> bytes:
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Quote')

    # --- Formats ---
    hdr_fmt = wb.add_format({'bold': True, 'bg_color': _HEADER, 'font_color': 'white',
                              'border': 1, 'text_wrap': True, 'valign': 'vcenter'})
    cell_base = {'border': 1, 'text_wrap': True, 'valign': 'vcenter'}
    fmt = {
        'ready':   wb.add_format({**cell_base, 'bg_color': _GREEN}),
        'check':   wb.add_format({**cell_base, 'bg_color': _YELLOW}),
        'missing': wb.add_format({**cell_base, 'bg_color': _RED}),
        'plain':   wb.add_format({**cell_base}),
    }

    # --- Header rows ---
    ws.merge_range('A1:U1', f'GOODRICH GASKET PVT. LTD', wb.add_format(
        {'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'}))
    if customer or project_ref:
        ws.merge_range('A2:U2', f'Customer: {customer}   |   Ref: {project_ref}',
                       wb.add_format({'italic': True, 'align': 'center'}))
    ws.set_row(0, 25)
    ws.set_row(1, 18)

    headers = ['SR.NO', 'CUSTOMER DESCRIPTION', 'GGPL DESCRIPTION',
               'SIZE', 'RATING', 'MOC', 'FACE', 'THK (MM)',
               'QTY', 'UOM', 'OD (MM)', 'ID (MM)',
               'RING NO', 'GROOVE', 'BHN',
               'SW WINDING', 'SW FILLER', 'SW OUTER RING', 'SW INNER RING',
               'STATUS', 'FLAGS / DEFAULTS']
    col_widths = [6, 40, 50, 8, 8, 25, 5, 8, 6, 5, 8, 8,
                  8, 6, 6,
                  12, 12, 14, 14,
                  10, 40]

    start_row = 3
    for col, (h, w) in enumerate(zip(headers, col_widths)):
        ws.write(start_row, col, h, hdr_fmt)
        ws.set_column(col, col, w)
    ws.set_row(start_row, 30)

    # --- Data rows ---
    for i, item in enumerate(items, 1):
        row = start_row + i
        status = item.get('status', 'missing')
        row_fmt = fmt.get(status, fmt['plain'])
        dims = item.get('dimensions') or {}
        flags = item.get('flags', [])
        defaults = item.get('applied_defaults', [])
        notes = '; '.join(flags + [f'[default] {d}' for d in defaults])

        ws.write(row, 0,  i,                                           row_fmt)
        ws.write(row, 1,  item.get('raw_description', ''),             row_fmt)
        ws.write(row, 2,  item.get('ggpl_description', ''),            row_fmt)
        ws.write(row, 3,  item.get('size', ''),                        row_fmt)
        ws.write(row, 4,  item.get('rating', ''),                      row_fmt)
        ws.write(row, 5,  item.get('moc', ''),                         row_fmt)
        ws.write(row, 6,  item.get('face_type', ''),                   row_fmt)
        ws.write(row, 7,  item.get('thickness_mm', ''),                row_fmt)
        ws.write(row, 8,  item.get('quantity', ''),                    row_fmt)
        ws.write(row, 9,  item.get('uom', ''),                         row_fmt)
        ws.write(row, 10, dims.get('od', '') if dims else '',          row_fmt)
        ws.write(row, 11, dims.get('id', '') if dims else '',          row_fmt)
        ws.write(row, 12, item.get('ring_no', ''),                     row_fmt)
        ws.write(row, 13, item.get('rtj_groove_type', ''),             row_fmt)
        hardness_display = item.get('rtj_hardness_spec') or item.get('rtj_hardness_bhn', '')
        ws.write(row, 14, hardness_display,                             row_fmt)
        ws.write(row, 15, item.get('sw_winding_material', ''),         row_fmt)
        ws.write(row, 16, item.get('sw_filler', ''),                   row_fmt)
        ws.write(row, 17, item.get('sw_outer_ring', ''),               row_fmt)
        ws.write(row, 18, item.get('sw_inner_ring', ''),               row_fmt)
        ws.write(row, 19, status.upper(),                              row_fmt)
        ws.write(row, 20, notes,                                       row_fmt)
        ws.set_row(row, 30)

    wb.close()
    return output.getvalue()
