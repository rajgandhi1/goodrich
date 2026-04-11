"""
Gasket Quote Processor — Streamlit MVP
Soft cut & spiral wound gaskets.
"""
import streamlit as st
import pandas as pd

from core.parser import parse_email_text, parse_excel_file
from core.rules import apply_rules, STATUS_READY, STATUS_CHECK, STATUS_MISSING
from core.formatter import format_description
from core.exporter import build_excel

st.set_page_config(page_title='Gasket Quote Processor', layout='wide')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FACE_OPTIONS   = ['RF', 'FF', '']
UOM_OPTIONS    = ['NOS', 'M']
TYPE_OPTIONS   = ['SOFT_CUT', 'SPIRAL_WOUND', 'RTJ', 'KAMM', 'DJI', 'ISK', 'ISK_RTJ']
GROOVE_OPTIONS = ['OCT', 'OVAL', '']

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if 'results' not in st.session_state:
    st.session_state.results = []
if '_selected_rows' not in st.session_state:
    st.session_state._selected_rows = set()
if 'filter_mode' not in st.session_state:
    st.session_state.filter_mode = 'All'

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title('Gasket Quote Processor')
st.caption('Soft cut & spiral wound gaskets — ASME & EN/PN standards')
st.divider()

# ---------------------------------------------------------------------------
# Step 1 — Input
# ---------------------------------------------------------------------------
st.subheader('Step 1 — Paste email or upload Excel')

col1, col2 = st.columns([1, 1], gap='large')

with col1:
    email_text = st.text_area(
        'Paste email body here',
        height=220,
        placeholder='Paste the customer email text containing gasket requirements...',
    )

with col2:
    uploaded_file = st.file_uploader('Or upload Excel file', type=['xlsx', 'xls'])
    customer = st.text_input('Customer name', placeholder='e.g. VA Tech Wabag')
    project_ref = st.text_input('Project / PO reference', placeholder='e.g. HPCL Vizag Refinery')

openai_key = st.sidebar.text_input('OpenAI API Key (optional — enables AI extraction)', type='password')
if openai_key:
    import os
    import core.extractor as _ext
    if os.environ.get('OPENAI_API_KEY') != openai_key:
        os.environ['OPENAI_API_KEY'] = openai_key
        _ext._openai_client = None
        # Validate the new key immediately
        try:
            from openai import OpenAI
            _test_client = OpenAI(api_key=openai_key, timeout=10.0)
            _test_client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{'role': 'user', 'content': 'hi'}],
                max_tokens=1,
            )
            st.sidebar.success('OpenAI API key valid')
        except Exception as _e:
            err_msg = str(_e)
            if 'auth' in err_msg.lower() or '401' in err_msg or 'invalid' in err_msg.lower():
                st.sidebar.error('Invalid API key — check and re-enter')
            else:
                st.sidebar.warning(f'Key set but could not verify: {err_msg}')
            os.environ['OPENAI_API_KEY'] = ''
            _ext._openai_client = None
    else:
        st.sidebar.success('OpenAI API key valid')
else:
    st.sidebar.info('No OpenAI key — using rule-based extraction')

def _build_preview_df(items):
    """Lightweight preview DataFrame shown while processing."""
    STATUS_ICON = {'ready': '✅', 'check': '🟡', 'missing': '🔴'}
    return pd.DataFrame([{
        '#':                    item.get('line_no', ''),
        'S':                    STATUS_ICON.get(item.get('status', ''), ''),
        'Customer Description': (item.get('raw_description') or '')[:80],
        'GGPL Description':     item.get('ggpl_description', ''),
        'Notes':                '; '.join((item.get('flags') or [])[:2]),
    } for item in items])


if st.button('Process Enquiry', type='primary', width="stretch"):
    raw_items = []

    if uploaded_file:
        raw_items = parse_excel_file(uploaded_file.read())
    elif email_text.strip():
        raw_items = parse_email_text(email_text)

    if not raw_items:
        st.warning('No gasket line items found. Check your input and try again.')
    else:
        from core.extractor import extract_batch
        unique_count = len({item['description'] for item in raw_items})

        status_text = st.empty()
        progress_bar = st.progress(0)
        preview_ph   = st.empty()   # progressive results table

        status_text.text(f'Extracting {unique_count} unique descriptions in parallel...')
        progress_bar.progress(5)

        def _on_progress(done, total):
            pct = int(done / total * 100)
            status_text.text(f'Extracting... {done}/{total} descriptions ({pct}%)')
            progress_bar.progress(5 + int(done / total * 70))

        extracted_items = extract_batch(raw_items, progress_cb=_on_progress)
        progress_bar.progress(75)

        # Rules + format — show preview table growing in real time
        n = len(extracted_items)
        step = max(1, n // 20)   # ~20 preview refreshes regardless of list size
        processed = []

        for i, extracted in enumerate(extracted_items, 1):
            item = apply_rules(extracted)
            item['ggpl_description'] = format_description(item)
            processed.append(item)
            progress_bar.progress(75 + int(i / n * 24))
            if i % step == 0 or i == n:
                status_text.text(f'Processed {i}/{n} items...')
                preview_ph.dataframe(
                    _build_preview_df(processed),
                    width='stretch',
                    hide_index=True,
                )

        progress_bar.empty()
        status_text.empty()
        preview_ph.empty()        # clear preview — full editor replaces it below
        st.session_state.results = processed
        st.session_state._selected_rows = set()
        st.session_state.pop('_bulk_df', None)
        st.session_state.filter_mode = 'All'


# ---------------------------------------------------------------------------
# Helper — build display rows from item list
# ---------------------------------------------------------------------------
def _build_rows(items):
    rows = []
    for item in items:
        status_icon = {'ready': '✅', 'check': '🟡', 'missing': '🔴'}.get(item['status'], '')
        flags = item.get('flags', [])
        defaults = item.get('applied_defaults', [])
        parts = list(flags) + [f'[default] {d}' for d in defaults]
        rows.append({
            '#':                    item.get('line_no', ''),
            'Customer Description': item.get('raw_description', ''),
            'Type':                 item.get('gasket_type', 'SOFT_CUT'),
            'Size':                 item.get('size') or '',
            'Rating':               item.get('rating') or '',
            'MOC':                  item.get('moc') or '',
            'Face':                 item.get('face_type') or '',
            'Thk (mm)':             item.get('thickness_mm') if item.get('thickness_mm') is not None else None,
            'Ring No':              item.get('ring_no') or '',
            'Groove':               item.get('rtj_groove_type') or '',
            'BHN':                  item.get('rtj_hardness_spec') or item.get('rtj_hardness_bhn') or '',
            'SW Winding':           item.get('sw_winding_material') or '',
            'SW Filler':            item.get('sw_filler') or '',
            'SW Outer Ring':        item.get('sw_outer_ring') or '',
            'SW Inner Ring':        item.get('sw_inner_ring') or '',
            'Qty':                  item.get('quantity') if item.get('quantity') is not None else None,
            'UoM':                  item.get('uom') or 'NOS',
            'Special':              item.get('special') or '',
            'GGPL Description':     item.get('ggpl_description', ''),
            'Status':               status_icon,
            'AI':                   item.get('confidence', ''),
            'Notes / Flags':        '; '.join(parts),
        })
    return rows


# ---------------------------------------------------------------------------
# Fragment — data editor + Update/Delete
# Reruns only itself on checkbox changes, keeping the rest of the page stable.
# display_indices: list of indices into the full `items` list to show.
# ---------------------------------------------------------------------------
@st.fragment
def _editor_fragment(items, display_indices):
    display_items = [items[i] for i in display_indices]

    if '_bulk_df' in st.session_state:
        df = st.session_state['_bulk_df'].copy()
    else:
        df = pd.DataFrame(_build_rows(display_items))

    # Inject Select and Delete columns at the front (_bulk_df never stores these)
    df = df.drop(columns=[c for c in ('Select', 'Delete') if c in df.columns])
    df.insert(0, 'Delete', False)
    df.insert(0, 'Select', [i in st.session_state._selected_rows for i in range(len(df))])

    edited_df = st.data_editor(
        df,
        width='stretch',
        height=min(80 + 35 * len(display_items), 620),
        hide_index=True,
        column_config={
            'Select':               st.column_config.CheckboxColumn('Select', width='small'),
            'Delete':               st.column_config.CheckboxColumn('🗑', width='small', help='Tick to delete this row on Update'),
            '#':                    st.column_config.NumberColumn('#', width='small', disabled=True),
            'Customer Description': st.column_config.TextColumn('Customer Description', width='large', disabled=True),
            'Type':                 st.column_config.SelectboxColumn('Type', options=TYPE_OPTIONS, width='small'),
            'Size':                 st.column_config.TextColumn('Size', width='small'),
            'Rating':               st.column_config.TextColumn('Rating', width='small'),
            'MOC':                  st.column_config.TextColumn('MOC', width='large'),
            'Face':                 st.column_config.SelectboxColumn('Face', options=FACE_OPTIONS, width='small'),
            'Thk (mm)':             st.column_config.NumberColumn('Thk (mm)', width='small', min_value=0),
            'Ring No':              st.column_config.TextColumn('Ring No', width='small', help='RTJ ring designation e.g. R-23'),
            'Groove':               st.column_config.SelectboxColumn('Groove', options=GROOVE_OPTIONS, width='small'),
            'BHN':                  st.column_config.TextColumn('BHN', width='small', help='RTJ hardness (e.g. 90 BHN HARDNESS or 22 HRC MAX)'),
            'SW Winding':           st.column_config.TextColumn('SW Winding', width='small', help='SPW/KAMM winding material e.g. SS304, SS316L'),
            'SW Filler':            st.column_config.TextColumn('SW Filler', width='small', help='SPW filler e.g. GRAPHITE, PTFE'),
            'SW Outer Ring':        st.column_config.TextColumn('SW Outer Ring', width='small', help='Outer centering ring e.g. CS, SS304'),
            'SW Inner Ring':        st.column_config.TextColumn('SW Inner Ring', width='small', help='Inner ring material e.g. SS304'),
            'Qty':                  st.column_config.NumberColumn('Qty', width='small', min_value=0),
            'UoM':                  st.column_config.SelectboxColumn('UoM', options=UOM_OPTIONS, width='small'),
            'Special':              st.column_config.TextColumn('Special', width='medium'),
            'GGPL Description':     st.column_config.TextColumn('GGPL Description', width='large', disabled=True),
            'Status':               st.column_config.TextColumn('Status', width='small', disabled=True),
            'AI':                   st.column_config.TextColumn('AI', width='small', disabled=True,
                                        help='Extraction confidence: HIGH / MEDIUM / LOW (blank = regex fallback)'),
            'Notes / Flags':        st.column_config.TextColumn('Notes / Flags', width='large', disabled=True),
        },
    )

    # Sync checkbox state back for Bulk Edit to read
    st.session_state._selected_rows = {i for i, row in edited_df.iterrows() if row['Select']}

    if st.button('Update', type='secondary', key='update_btn'):
        # Work on a copy of the full results list so non-visible rows are preserved
        updated_full = list(items)
        to_delete = set()

        for i, row in edited_df.iterrows():
            orig_idx = display_indices[i]
            if row.get('Delete'):
                to_delete.add(orig_idx)
                continue
            base = items[orig_idx].copy()
            base['gasket_type']        = row['Type'] or base.get('gasket_type', 'SOFT_CUT')
            base['size']               = row['Size'] or base.get('size')
            base['rating']             = row['Rating'] or base.get('rating')
            base['moc']                = row['MOC'] or None
            base['face_type']          = row['Face'] or None
            base['thickness_mm']       = row['Thk (mm)'] or None
            base['ring_no']            = row['Ring No'] or None
            base['rtj_groove_type']    = row['Groove'] or None
            bhn_val = row['BHN'] or None
            if bhn_val:
                base['rtj_hardness_spec'] = str(bhn_val)
                try:
                    base['rtj_hardness_bhn'] = int(float(str(bhn_val).split()[0]))
                except (ValueError, IndexError):
                    base['rtj_hardness_bhn'] = None
            else:
                base['rtj_hardness_spec'] = None
                base['rtj_hardness_bhn'] = None
            base['sw_winding_material']= row['SW Winding'] or None
            base['sw_filler']          = row['SW Filler'] or None
            base['sw_outer_ring']      = row['SW Outer Ring'] or None
            base['sw_inner_ring']      = row['SW Inner Ring'] or None
            if base.get('gasket_type') == 'SPIRAL_WOUND' and any([
                row['SW Winding'], row['SW Filler'], row['SW Outer Ring'], row['SW Inner Ring']
            ]):
                base['moc'] = None
            base['quantity']           = row['Qty'] or base.get('quantity')
            base['uom']                = row['UoM'] or 'NOS'
            base['special']            = row['Special'] or None
            for f in ('size_norm', 'rating_norm', 'status', 'flags', 'applied_defaults', 'dimensions'):
                base.pop(f, None)
            item = apply_rules(base)
            item['ggpl_description'] = format_description(item)
            updated_full[orig_idx] = item

        # Remove deleted rows and renumber
        final = [item for idx, item in enumerate(updated_full) if idx not in to_delete]
        for j, item in enumerate(final, 1):
            item['line_no'] = j

        st.session_state.results = final
        st.session_state.pop('_bulk_df', None)
        st.session_state._selected_rows = set()
        st.rerun(scope='app')


# ---------------------------------------------------------------------------
# Step 2 — Review & Edit
# ---------------------------------------------------------------------------
if st.session_state.results:
    items = st.session_state.results
    st.divider()
    st.subheader('Step 2 — Review & Edit')

    # Metrics
    n_ready   = sum(1 for i in items if i['status'] == STATUS_READY)
    n_check   = sum(1 for i in items if i['status'] == STATUS_CHECK)
    n_missing = sum(1 for i in items if i['status'] == STATUS_MISSING)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Total items', len(items))
    c2.metric('Ready ✅', n_ready)
    c3.metric('Check defaults 🟡', n_check)
    c4.metric('Action needed 🔴', n_missing)

    # Filter
    filter_col, spacer = st.columns([3, 7])
    with filter_col:
        filter_mode = st.radio(
            'Show',
            ['All', 'Issues (🟡 + 🔴)', 'Missing only (🔴)'],
            horizontal=True,
            key='filter_mode',
            label_visibility='collapsed',
        )

    # Invalidate bulk-df cache and selections when filter changes
    if st.session_state.get('_last_filter_mode') != filter_mode:
        st.session_state.pop('_bulk_df', None)
        st.session_state._selected_rows = set()
        st.session_state['_last_filter_mode'] = filter_mode

    # Compute which rows to display
    if filter_mode == 'Issues (🟡 + 🔴)':
        display_indices = [i for i, item in enumerate(items)
                           if item['status'] in (STATUS_CHECK, STATUS_MISSING)]
    elif filter_mode == 'Missing only (🔴)':
        display_indices = [i for i, item in enumerate(items)
                           if item['status'] == STATUS_MISSING]
    else:
        display_indices = list(range(len(items)))

    if not display_indices:
        st.success('No items match this filter.')
    else:
        # Select All / Deselect All (scoped to visible rows)
        sa1, sa2, sa3, _ = st.columns([1, 1.3, 1.3, 7])
        if sa1.button('Select All', key='sel_all_btn'):
            st.session_state._selected_rows = set(range(len(display_indices)))
        if sa2.button('Deselect All', key='desel_all_btn'):
            st.session_state._selected_rows = set()
        if sa3.button('+ Add Row', key='add_row_btn'):
            new_item = apply_rules({
                'line_no': len(items) + 1,
                'raw_description': '',
                'gasket_type': 'SOFT_CUT',
            })
            new_item['ggpl_description'] = format_description(new_item)
            st.session_state.results.append(new_item)
            st.session_state.pop('_bulk_df', None)
            st.session_state._selected_rows = set()
            st.rerun(scope='app')

        # Bulk Edit
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
            bc9, bc10, bc11, bc12 = st.columns(4)
            bulk_winding = bc9.text_input('SW Winding',     placeholder='e.g. SS316',    key='bulk_winding')
            bulk_filler  = bc10.text_input('SW Filler',     placeholder='e.g. GRAPHITE', key='bulk_filler')
            bulk_outer   = bc11.text_input('SW Outer Ring', placeholder='e.g. CS',       key='bulk_outer')
            bulk_inner   = bc12.text_input('SW Inner Ring', placeholder='e.g. SS316',    key='bulk_inner')

            if st.button('Apply Bulk Edit', type='secondary', key='apply_bulk'):
                df_bulk = st.session_state['_bulk_df'].copy() if '_bulk_df' in st.session_state \
                          else pd.DataFrame(_build_rows([items[i] for i in display_indices]))
                # _bulk_df never stores Select/Delete — fragment always injects them fresh
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
                st.session_state['_bulk_df'] = df_bulk
                st.success(f'Applied to {len(target)} row(s). Click **Update** below to regenerate descriptions.')

        # ---- The only thing that reruns on checkbox clicks ----
        _editor_fragment(items, display_indices)

    # Missing info summary + RFI draft
    missing_items = [i for i in items if i['status'] == STATUS_MISSING]
    if missing_items:
        st.warning('**Items needing clarification** (edit the table above to fill these in):')
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
    # Step 3 — Export
    # -------------------------------------------------------------------------
    st.divider()
    st.subheader('Step 3 — Export')

    excel_bytes = build_excel(items, customer=customer, project_ref=project_ref)
    filename = f"quote_{project_ref or customer or 'output'}.xlsx".replace(' ', '_')

    st.download_button(
        label='Download Quote Excel',
        data=excel_bytes,
        file_name=filename,
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        type='primary',
        width="stretch",
    )
