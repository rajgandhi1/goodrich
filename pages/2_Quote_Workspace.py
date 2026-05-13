"""
Gasket Quote Workspace — process enquiries and build quotations.

This is the original single-page app, now reachable as the "Quote Workspace"
page; the dashboard at app.py is the landing page.
"""
import os as _os

import pandas as pd
import streamlit as st

from ui.bootstrap import init_session_state  # noqa: F401 — also runs env loading

st.set_page_config(
    page_title='Quote Workspace — GGPL',
    page_icon='⚙️',
    layout='wide',
    initial_sidebar_state='expanded',
)

from core.formatter import format_description
from core.rules import apply_rules, STATUS_CHECK, STATUS_MISSING, STATUS_READY, STATUS_REGRET
from ui.chat import render_chat_widget
from ui.constants import FACE_OPTIONS, GROOVE_OPTIONS, TYPE_OPTIONS, UOM_OPTIONS
from ui.converter import render_converter_tab
from ui.editor import (
    _build_extraction_summary,
    _build_rows,
    _delete_selected_items,
    _editor_fragment,
    _reset_enquiry_inputs,
)
from ui.history import _save_extraction_history, load_history, mark_active_quote_prep
from ui.processing import process_and_append
from ui.quote_page import render_quote_page
from ui.sidebar import render_sidebar
from ui.styles import apply_global_styles

apply_global_styles()
init_session_state()
load_history()
render_sidebar()


# ---------------------------------------------------------------------------
# Quote page — intercept main content if quote page is active
# ---------------------------------------------------------------------------
_has_unsaved_progress = bool(
    st.session_state.get('working_items')
    or st.session_state.get('_quote_data')
    or st.session_state.get('_quote_excel')
)
st.html(f"""
<script>
(function() {{
  window.gqHasUnsavedProgress = {str(_has_unsaved_progress).lower()};
  window.onbeforeunload = function(event) {{
    if (!window.gqHasUnsavedProgress) return undefined;
    event.preventDefault();
    event.returnValue = '';
    return '';
  }};
}})();
</script>
""", unsafe_allow_javascript=True)

if st.session_state._show_quote_page:
    render_quote_page()
    st.stop()

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="gq-header">
  <div class="gq-header-icon">⚙️</div>
  <div>
    <p class="gq-header-title">Gasket Quote Workspace</p>
    <p class="gq-header-sub">Goodrich Gasket Pvt. Ltd — Soft cut &amp; spiral wound · ASME &amp; EN/PN standards</p>
  </div>
</div>
""", unsafe_allow_html=True)

ref_c1, ref_c2 = st.columns(2)
with ref_c1:
    customer = st.text_input('Customer name', key='inp_customer', placeholder='e.g. VA Tech Wabag')
with ref_c2:
    project_ref = st.text_input('Project / PO reference', key='inp_project_ref', placeholder='e.g. HPCL Vizag Refinery')

st.markdown('<div style="height:0.3rem"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Step 1 — Input
# ---------------------------------------------------------------------------
st.markdown("""
<div class="gq-step">
  <div class="gq-step-label">
    <span class="gq-step-badge">1</span>
    <p class="gq-step-title">Add items to working list</p>
  </div>
</div>
""", unsafe_allow_html=True)

tab_email, tab_excel, tab_pdf, tab_manual, tab_conv = st.tabs(
    ['📧 Email', '📊 Excel', '📄 PDF', '✏️ Manual', '📐 Converter']
)


_wl_count = len(st.session_state.working_items)
_wl_hint = (
    f'Working list currently has **{_wl_count} item{"s" if _wl_count != 1 else ""}** — '
    'new items will be appended. Use 🗑 Clear in the working list to start fresh.'
    if _wl_count > 0 else
    'Working list is empty — processed items will appear in Step 2 below.'
)

with tab_email:
    email_text = st.text_area(
        'Paste email body',
        height=200,
        placeholder='Paste the customer email text containing gasket requirements...',
        label_visibility='visible',
        key=f'email_text_{st.session_state._input_reset_seq}',
    )
    st.caption(f'**Smart Parse active** — LLM reads the full email in one pass. {_wl_hint}')
    if st.button('⚡  Process & Add to List', type='primary', key='process_email_btn'):
        if not email_text.strip():
            st.warning('Please paste some email text first.')
        elif not _os.environ.get('OPENAI_API_KEY'):
            st.error('OpenAI API key required. Enter it in the sidebar to process enquiries.')
        elif process_and_append(source=email_text, source_type='email'):
            _save_extraction_history()
            st.rerun()

with tab_excel:
    uploaded_file = st.file_uploader(
        'Upload Excel file',
        type=['xlsx', 'xls'],
        help='Supports multi-sheet enquiry files',
        key=f'excel_upload_{st.session_state._input_reset_seq}',
    )
    st.caption(f'**Smart Parse active** — LLM reads all sheets at once. {_wl_hint}')
    if st.button('⚡  Process & Add to List', type='primary', key='process_excel_btn'):
        if uploaded_file:
            file_bytes = uploaded_file.read()
            if not _os.environ.get('OPENAI_API_KEY'):
                st.error('OpenAI API key required. Enter it in the sidebar to process enquiries.')
            elif process_and_append(source=file_bytes, source_type='excel'):
                _save_extraction_history()
                st.rerun()
        else:
            st.warning('Please upload an Excel file first.')

with tab_pdf:
    st.caption(
        'Upload a PDF gasket enquiry. The text will be extracted and processed with Smart Parse. '
        'Scanned/image-only PDFs are not supported — copy-paste from those into the Email tab instead.'
    )
    pdf_file = st.file_uploader(
        'Upload PDF',
        type=['pdf'],
        help='Text-based PDFs only (not scanned images)',
        key='pdf_uploader',
    )
    st.caption(_wl_hint)
    if st.button('⚡  Process & Add to List', type='primary', key='process_pdf_btn'):
        if pdf_file:
            if not _os.environ.get('OPENAI_API_KEY'):
                st.warning(
                    'PDF processing requires an OpenAI API key (Smart Parse mode). '
                    'Enter your key in the sidebar.'
                )
            else:
                pdf_bytes = pdf_file.read()
                if process_and_append(source=pdf_bytes, source_type='pdf'):
                    _save_extraction_history()
                    st.rerun()
        else:
            st.warning('Please upload a PDF file first.')

with tab_manual:
    st.caption('Fill in fields to add a single line item directly to the working list.')
    with st.form('manual_add_form', clear_on_submit=True):
        m_desc = st.text_input('Customer Description (optional)', placeholder='e.g. 4" 150# CNAF RF')
        m_c1, m_c2, m_c3, m_c4 = st.columns(4)
        m_type   = m_c1.selectbox('Type', TYPE_OPTIONS, key='m_type')
        m_size   = m_c1.text_input('Size', placeholder='e.g. 4" or 100 NB', key='m_size')
        m_rating = m_c2.text_input('Rating', placeholder='e.g. 150# or PN16', key='m_rating')
        m_moc    = m_c2.text_input('MOC', placeholder='e.g. CNAF', key='m_moc')
        m_face   = m_c3.selectbox('Face', FACE_OPTIONS, key='m_face')
        m_thk    = m_c3.number_input('Thickness (mm)', value=3.0, min_value=0.0, step=0.5, key='m_thk')
        m_qty    = m_c4.number_input('Qty', value=1, min_value=0, step=1, key='m_qty')
        m_uom    = m_c4.selectbox('UoM', UOM_OPTIONS, key='m_uom')
        m_special = st.text_input('Special / Notes (optional)', placeholder='e.g. NACE MR0175', key='m_special')
        submitted = st.form_submit_button('+ Add Item to List', type='secondary')

    if submitted:
        if not (m_size or m_moc):
            st.warning('At least Size or MOC is required to add an item.')
        else:
            existing = st.session_state.working_items
            next_ln = (max(i.get('line_no', 0) for i in existing) + 1) if existing else 1
            raw = {
                'line_no':         next_ln,
                'raw_description': m_desc or '',
                'description':     m_desc or f'{m_size} {m_rating} {m_moc}'.strip(),
                'gasket_type':     m_type,
                'size':            m_size or None,
                'rating':          m_rating or None,
                'moc':             m_moc.upper() if m_moc else None,
                'face_type':       m_face or None,
                'thickness_mm':    m_thk if m_thk else None,
                'quantity':        m_qty if m_qty else None,
                'uom':             m_uom,
                'special':         m_special.upper() if m_special else None,
                'confidence':      'MANUAL',
            }
            item = apply_rules(raw)
            item['ggpl_description'] = format_description(item)
            st.session_state.working_items = existing + [item]
            st.session_state._show_confirm = False
            st.rerun()


render_converter_tab(tab_conv)


# ---------------------------------------------------------------------------
# Step 2 — Working List
# ---------------------------------------------------------------------------
if st.session_state.working_items:
    items = st.session_state.working_items

    n_ready   = sum(1 for i in items if i['status'] == STATUS_READY)
    n_check   = sum(1 for i in items if i['status'] == STATUS_CHECK)
    n_missing = sum(1 for i in items if i['status'] == STATUS_MISSING)
    n_regret  = sum(1 for i in items if i['status'] == STATUS_REGRET)

    wl_hdr, wl_clear = st.columns([9, 1])
    with wl_hdr:
        st.markdown(f"""
        <div class="gq-step">
          <div class="gq-step-label">
            <span class="gq-step-badge">2</span>
            <p class="gq-step-title">Working List &nbsp;<span style="font-weight:400;font-size:0.9rem;color:#5a7aab">({len(items)} items — keep adding or edit below)</span></p>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with wl_clear:
        st.markdown('<div style="height:0.9rem"></div>', unsafe_allow_html=True)
        if st.button('🗑 Clear', key='clear_list_btn', type='secondary', help='Remove all items from working list'):
            st.session_state.working_items = []
            st.session_state._selected_rows = set()
            st.session_state.pop('_bulk_df', None)
            st.session_state.pop('_last_excel', None)
            st.session_state.filter_mode = 'All'
            st.session_state._show_confirm = False
            _reset_enquiry_inputs()
            st.rerun()

    st.markdown(f"""
    <div class="gq-metrics">
      <div class="gq-metric gq-total">
        <div class="val">{len(items)}</div>
        <div class="lbl">Total Items</div>
      </div>
      <div class="gq-metric gq-ready">
        <div class="val">{n_ready}</div>
        <div class="lbl">✅ Ready</div>
      </div>
      <div class="gq-metric gq-check">
        <div class="val">{n_check}</div>
        <div class="lbl">🟡 Check Defaults</div>
      </div>
      <div class="gq-metric gq-missing">
        <div class="val">{n_missing}</div>
        <div class="lbl">🔴 Action Needed</div>
      </div>
      <div class="gq-metric gq-regret">
        <div class="val">{n_regret}</div>
        <div class="lbl">⛔ Regret</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _summary_lines = _build_extraction_summary(items)
    if _summary_lines:
        with st.expander(f'📋 Enquiry Summary — {len(_summary_lines)} unique gasket type{"s" if len(_summary_lines) != 1 else ""}', expanded=False):
            for i, line in enumerate(_summary_lines, 1):
                st.markdown(f'**{i}.** `{line}`')

    filter_col, spacer = st.columns([4, 6])
    with filter_col:
        filter_mode = st.radio(
            'Show',
            ['All', 'Issues (🟡 + 🔴)', 'Missing only (🔴)', 'Regret only (⛔)'],
            horizontal=True,
            key='filter_mode',
            label_visibility='collapsed',
        )

    if st.session_state.get('_last_filter_mode') != filter_mode:
        st.session_state.pop('_bulk_df', None)
        st.session_state._selected_rows = set()
        st.session_state['_last_filter_mode'] = filter_mode

    if filter_mode == 'Issues (🟡 + 🔴)':
        display_indices = [i for i, item in enumerate(items)
                           if item['status'] in (STATUS_CHECK, STATUS_MISSING)]
    elif filter_mode == 'Missing only (🔴)':
        display_indices = [i for i, item in enumerate(items)
                           if item['status'] == STATUS_MISSING]
    elif filter_mode == 'Regret only (⛔)':
        display_indices = [i for i, item in enumerate(items)
                           if item['status'] == STATUS_REGRET]
    else:
        display_indices = list(range(len(items)))

    if not display_indices:
        st.success('No items match this filter.')
    else:
        sa1, sa2, sa3, sa4, _ = st.columns([1, 1.3, 1.2, 1.4, 5.6])
        if sa1.button('Select All', key='sel_all_btn'):
            st.session_state._selected_rows = set(range(len(display_indices)))
        if sa2.button('Deselect All', key='desel_all_btn'):
            st.session_state._selected_rows = set()
        sel_rows = st.session_state._selected_rows
        insert_hint = 'after selected row' if len(sel_rows) == 1 else 'at end of list'
        if sa3.button('＋ Add Row', key='add_row_btn', help=f'Insert a blank row {insert_hint}'):
            new_item = apply_rules({
                'line_no': 0,
                'raw_description': '',
                'gasket_type': 'SOFT_CUT',
            })
            new_item['ggpl_description'] = format_description(new_item)
            wl = st.session_state.working_items
            if len(sel_rows) == 1:
                sel_display_idx = next(iter(sel_rows))
                insert_after = display_indices[sel_display_idx]
                wl.insert(insert_after + 1, new_item)
            else:
                wl.append(new_item)
            for i, it in enumerate(wl, 1):
                it['line_no'] = i
            st.session_state.pop('_bulk_df', None)
            st.session_state._selected_rows = set()
            st.rerun(scope='app')
        if sa4.button('Delete Row', key='delete_row_top_btn',
                      disabled=(len(st.session_state._selected_rows) == 0),
                      help='Delete selected row(s) from the working list'):
            _delete_selected_items(items, display_indices)
            st.rerun(scope='app')

        n_sel = len(st.session_state._selected_rows)
        n_visible = len(display_indices)
        target_label = f'all {n_visible} visible rows' if n_sel == 0 else f'{n_sel} selected row(s)'
        with st.expander(f'Bulk Edit — targeting {target_label}', expanded=False):
            st.caption('Tick **Select** on the rows you want to change, fill fields below, then click **Apply Bulk Edit**.')
            bc1, bc2, bc3, bc4, bc5, bc6, bc7, bc8 = st.columns(8)
            bulk_type    = bc1.selectbox('Type',        ['(no change)'] + TYPE_OPTIONS,   key='bulk_type')
            bulk_moc     = bc2.text_input('MOC',         placeholder='e.g. CNAF',          key='bulk_moc')
            bulk_rating  = bc3.text_input('Rating',      placeholder='e.g. 150#',          key='bulk_rating')
            bulk_face    = bc4.selectbox('Face',         ['(no change)'] + FACE_OPTIONS,   key='bulk_face')
            bulk_groove  = bc5.selectbox('Groove',       ['(no change)'] + GROOVE_OPTIONS, key='bulk_groove')
            bulk_thk     = bc6.number_input('Thk (mm)',  value=0.0, min_value=0.0, step=0.5, key='bulk_thk',
                                            help='0 = no change')
            bulk_bhn     = bc7.number_input('BHN',       value=0,   min_value=0, step=10,   key='bulk_bhn',
                                            help='0 = no change')
            bulk_uom     = bc8.selectbox('UoM',          ['(no change)'] + UOM_OPTIONS,    key='bulk_uom')
            bc9, bc10, bc11, bc12, bc13 = st.columns(5)
            bulk_winding  = bc9.text_input('SW Winding',     placeholder='e.g. SS316',              key='bulk_winding')
            bulk_filler   = bc10.text_input('SW Filler',     placeholder='e.g. GRAPHITE',           key='bulk_filler')
            bulk_outer    = bc11.text_input('SW Outer Ring', placeholder='e.g. CS',                 key='bulk_outer')
            bulk_inner    = bc12.text_input('SW Inner Ring', placeholder='e.g. SS316',              key='bulk_inner')
            bulk_standard = bc13.text_input('Standard',      placeholder='e.g. ASME B16.20',        key='bulk_standard')

            if st.button('Apply Bulk Edit', type='secondary', key='apply_bulk'):
                df_bulk = st.session_state['_bulk_df'].copy() if '_bulk_df' in st.session_state \
                          else pd.DataFrame(_build_rows([items[i] for i in display_indices]))
                df_bulk = df_bulk.drop(columns=[c for c in ('Select', 'Delete') if c in df_bulk.columns])
                selected = st.session_state._selected_rows
                target = list(selected) if selected else list(range(len(df_bulk)))
                for idx in target:
                    if bulk_type    != '(no change)':  df_bulk.at[idx, 'Type']          = bulk_type
                    if bulk_moc.strip():               df_bulk.at[idx, 'MOC']           = bulk_moc.strip().upper()
                    if bulk_rating.strip():            df_bulk.at[idx, 'Rating']        = bulk_rating.strip()
                    if bulk_face    != '(no change)':  df_bulk.at[idx, 'Face']          = bulk_face
                    if bulk_groove  != '(no change)':  df_bulk.at[idx, 'Groove']        = bulk_groove
                    if bulk_thk     > 0:               df_bulk.at[idx, 'Thk (mm)']      = bulk_thk
                    if bulk_bhn     > 0:               df_bulk.at[idx, 'BHN']           = bulk_bhn
                    if bulk_uom     != '(no change)':  df_bulk.at[idx, 'UoM']           = bulk_uom
                    if bulk_winding.strip():           df_bulk.at[idx, 'SW Winding']    = bulk_winding.strip().upper()
                    if bulk_filler.strip():            df_bulk.at[idx, 'SW Filler']     = bulk_filler.strip().upper()
                    if bulk_outer.strip():             df_bulk.at[idx, 'SW Outer Ring'] = bulk_outer.strip().upper()
                    if bulk_inner.strip():             df_bulk.at[idx, 'SW Inner Ring'] = bulk_inner.strip().upper()
                    if bulk_standard.strip():          df_bulk.at[idx, 'Standard']      = bulk_standard.strip()
                st.session_state['_bulk_df'] = df_bulk
                st.success(f'Applied to {len(target)} row(s). Click **↻ Update Descriptions** to regenerate.')

        _editor_fragment(items, display_indices)

    missing_items = [i for i in items if i['status'] == STATUS_MISSING]
    if missing_items:
        st.warning('**Items needing clarification** — edit the table above to fill these in:')
        seen_flags = {}
        for item in missing_items:
            for flag in item.get('flags', []):
                seen_flags.setdefault(flag, []).append(str(item.get('line_no') or '?'))
        for flag, line_nos in seen_flags.items():
            st.write(f'• Items {", ".join(line_nos)}: {flag}')

        rfi_lines = [f'- Items {", ".join(lns)}: {flag}' for flag, lns in seen_flags.items()]
        rfi_text = ('Dear Sir,\n\nThank you for your enquiry. '
                    'To proceed with the quote, kindly clarify:\n\n'
                    + '\n'.join(rfi_lines)
                    + '\n\nWith regards,\nGoodrich Gasket')
        with st.expander('Draft RFI email'):
            st.code(rfi_text, language=None)
            st.download_button(
                label='Download RFI as .txt',
                data=rfi_text.encode(),
                file_name=f"RFI_{project_ref or customer or 'enquiry'}.txt".replace(' ', '_'),
                mime='text/plain',
                key='rfi_download',
            )

    # -------------------------------------------------------------------------
    # Step 3 — Generate Quotation
    # -------------------------------------------------------------------------
    st.markdown("""
    <div class="gq-step" style="border-left-color:#1a7a3c">
      <div class="gq-step-label">
        <span class="gq-step-badge" style="background:#1a7a3c">3</span>
        <p class="gq-step-title">Generate Sales Quotation</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        'When you are happy with the working list, click below to fill in pricing, '
        'buyer details and terms — then generate the official GGPL quotation Excel.'
    )
    gen_col, _ = st.columns([3, 7])
    with gen_col:
        if st.button('📋  Generate Quotation', type='primary', key='gen_enquiry_btn'):
            if not st.session_state._quote_data.get('buyer_name_address') and customer:
                st.session_state._quote_data['buyer_name_address'] = customer
            if not st.session_state._quote_data.get('customer_enq_no') and project_ref:
                st.session_state._quote_data['customer_enq_no'] = project_ref
            st.session_state._show_quote_page = True
            st.session_state._quote_excel = None
            mark_active_quote_prep()
            st.rerun()


# ---------------------------------------------------------------------------
# Download section — shown after enquiry is committed
# ---------------------------------------------------------------------------
if st.session_state.get('_last_excel'):
    excel_bytes = st.session_state['_last_excel']
    filename    = st.session_state.get('_last_filename', 'quote.xlsx')

    st.markdown("""
    <div class="gq-step" style="border-left-color:#1a7a3c">
      <div class="gq-step-label">
        <span class="gq-step-badge" style="background:#1a7a3c">✓</span>
        <p class="gq-step-title">Enquiry Committed — Download Ready</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.success(f'Enquiry saved to history: **{filename}**')
    dl_col, new_col, _ = st.columns([2, 2, 6])
    with dl_col:
        st.download_button(
            label='⬇  Download Quote Excel',
            data=excel_bytes,
            file_name=filename,
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            type='primary',
            width="stretch",
        )
    with new_col:
        if st.button('＋  Start New Enquiry', type='secondary', key='new_enquiry_btn'):
            st.session_state.pop('_last_excel', None)
            st.session_state.pop('_last_filename', None)
            st.rerun()


render_chat_widget()
