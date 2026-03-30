"""
Gasket Quote Processor — Streamlit MVP
Soft cut gaskets only.
"""
import streamlit as st
import pandas as pd

from core.parser import parse_email_text, parse_excel_file
from core.rules import apply_rules, STATUS_READY, STATUS_CHECK, STATUS_MISSING
from core.formatter import format_description
from core.exporter import build_excel

st.set_page_config(page_title='Gasket Quote Processor', layout='wide')

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if 'results' not in st.session_state:
    st.session_state.results = []
if '_selected_rows' not in st.session_state:
    st.session_state._selected_rows = set()

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

groq_key = st.sidebar.text_input('Groq API Key (optional — enables AI extraction)', type='password')
if groq_key:
    import os
    import core.extractor as _ext
    if os.environ.get('GROQ_API_KEY') != groq_key:
        os.environ['GROQ_API_KEY'] = groq_key
        _ext._groq_client = None  # reset cached client when key changes
    st.sidebar.success('Groq API key set')
else:
    st.sidebar.info('No Groq key — using rule-based extraction')

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

        status_text.text(f'Extracting {unique_count} unique descriptions...')
        progress_bar.progress(5)

        def _on_progress(done, total):
            status_text.text(f'Extracting... {done}/{total} descriptions')
            progress_bar.progress(5 + int(done / total * 70))

        extracted_items = extract_batch(raw_items, progress_cb=_on_progress)
        progress_bar.progress(75)

        status_text.text('Applying rules and formatting...')
        processed = []
        for i, extracted in enumerate(extracted_items, 1):
            item = apply_rules(extracted)
            item['ggpl_description'] = format_description(item)
            processed.append(item)
            progress_bar.progress(75 + int(i / len(extracted_items) * 25))

        progress_bar.empty()
        status_text.empty()
        st.session_state.results = processed

# ---------------------------------------------------------------------------
# Step 2 — Review & Edit
# ---------------------------------------------------------------------------
if st.session_state.results:
    items = st.session_state.results
    st.divider()
    st.subheader('Step 2 — Review & Edit')

    n_ready   = sum(1 for i in items if i['status'] == STATUS_READY)
    n_check   = sum(1 for i in items if i['status'] == STATUS_CHECK)
    n_missing = sum(1 for i in items if i['status'] == STATUS_MISSING)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Total items', len(items))
    c2.metric('Ready ✅', n_ready)
    c3.metric('Check defaults 🟡', n_check)
    c4.metric('Action needed 🔴', n_missing)

    st.caption('Use **Bulk Edit** to fill a field across many rows at once, then fine-tune individual cells in the table.')

    # Build editable dataframe — editable fields only
    FACE_OPTIONS   = ['RF', 'FF', '']
    UOM_OPTIONS    = ['NOS', 'M']
    TYPE_OPTIONS   = ['SOFT_CUT', 'SPIRAL_WOUND', 'RTJ', 'KAMM', 'DJI', 'ISK', 'ISK_RTJ']
    GROOVE_OPTIONS = ['OCT', 'OVAL', '']

    rows = []
    for idx, item in enumerate(items):
        status_icon = {'ready': '✅', 'check': '🟡', 'missing': '🔴'}.get(item['status'], '')
        flags = item.get('flags', [])
        defaults = item.get('applied_defaults', [])
        parts = list(flags) + [f'[default] {d}' for d in defaults]
        notes = '; '.join(parts)
        rows.append({
            'Select':               idx in st.session_state._selected_rows,
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
            'Notes / Flags':        notes,
        })

    df = pd.DataFrame(rows)

    # ---- Select All / Deselect All buttons ------------------------------------
    sa_col1, sa_col2, _ = st.columns([1, 1, 8])
    if sa_col1.button('Select All', key='sel_all_btn'):
        st.session_state._selected_rows = set(range(len(items)))
        st.rerun()
    if sa_col2.button('Deselect All', key='desel_all_btn'):
        st.session_state._selected_rows = set()
        st.rerun()

    # ---- Bulk Edit panel -------------------------------------------------------
    with st.expander('Bulk Edit — apply a value to multiple rows at once', expanded=False):
        st.caption('Tick **Select** on the rows you want to change (leave all un-ticked to apply to every row), fill the fields below, then click **Apply Bulk Edit**.')
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
        bulk_winding = bc9.text_input('SW Winding',  placeholder='e.g. SS316',         key='bulk_winding')
        bulk_filler  = bc10.text_input('SW Filler',  placeholder='e.g. GRAPHITE',      key='bulk_filler')
        bulk_outer   = bc11.text_input('SW Outer Ring', placeholder='e.g. CS',         key='bulk_outer')
        bulk_inner   = bc12.text_input('SW Inner Ring', placeholder='e.g. SS316',      key='bulk_inner')

        if st.button('Apply Bulk Edit', type='secondary', key='apply_bulk'):
            selected = st.session_state._selected_rows
            target_indices = list(selected) if selected else list(range(len(df)))
            target_mask = pd.Series([i in set(target_indices) for i in df.index])
            for idx in df.index[target_mask]:
                if bulk_type    != '(no change)':  df.at[idx, 'Type']         = bulk_type
                if bulk_moc.strip():               df.at[idx, 'MOC']          = bulk_moc.strip().upper()
                if bulk_rating.strip():            df.at[idx, 'Rating']       = bulk_rating.strip()
                if bulk_face    != '(no change)':  df.at[idx, 'Face']         = bulk_face
                if bulk_groove  != '(no change)':  df.at[idx, 'Groove']       = bulk_groove
                if bulk_thk     > 0:               df.at[idx, 'Thk (mm)']     = bulk_thk
                if bulk_bhn     > 0:               df.at[idx, 'BHN']          = bulk_bhn
                if bulk_uom     != '(no change)':  df.at[idx, 'UoM']          = bulk_uom
                if bulk_winding.strip():           df.at[idx, 'SW Winding']   = bulk_winding.strip().upper()
                if bulk_filler.strip():            df.at[idx, 'SW Filler']    = bulk_filler.strip().upper()
                if bulk_outer.strip():             df.at[idx, 'SW Outer Ring']= bulk_outer.strip().upper()
                if bulk_inner.strip():             df.at[idx, 'SW Inner Ring']= bulk_inner.strip().upper()
            st.session_state['_bulk_df'] = df.copy()
            st.success(f'Applied to {int(target_mask.sum())} row(s). Click **Update** below to regenerate descriptions.')

    # Use bulk-edited df if available, else the default one
    if '_bulk_df' in st.session_state:
        df = st.session_state['_bulk_df']

    # Keep Select column in sync with session state selection
    for i in range(len(df)):
        df.at[i, 'Select'] = i in st.session_state._selected_rows

    edited_df = st.data_editor(
        df,
        width="stretch",
        height=min(80 + 35 * len(items), 620),
        hide_index=True,
        column_config={
            'Select':               st.column_config.CheckboxColumn('Select', width='small'),
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
            'Notes / Flags':        st.column_config.TextColumn('Notes / Flags', width='large', disabled=True),
        },
    )

    # Sync selection state back from data editor
    new_selected = {i for i, row in edited_df.iterrows() if row['Select']}
    if new_selected != st.session_state._selected_rows:
        st.session_state._selected_rows = new_selected

    if st.button('Update', type='secondary'):
        updated = []
        for i, row in edited_df.iterrows():
            base = items[i].copy()
            # Apply reviewer edits back into the item
            base['gasket_type']        = row['Type'] or base.get('gasket_type', 'SOFT_CUT')
            base['size']               = row['Size'] or base.get('size')
            base['rating']             = row['Rating'] or base.get('rating')
            base['moc']                = row['MOC'] or None
            base['face_type']          = row['Face'] or None
            base['thickness_mm']       = row['Thk (mm)'] or None
            base['ring_no']            = row['Ring No'] or None
            base['rtj_groove_type']    = row['Groove'] or None
            # BHN column may now contain "90 BHN HARDNESS" or "22 HRC MAX" strings
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
            # When SW fields are edited, clear the assembled MOC so it rebuilds
            if base.get('gasket_type') == 'SPIRAL_WOUND' and any([
                row['SW Winding'], row['SW Filler'], row['SW Outer Ring'], row['SW Inner Ring']
            ]):
                base['moc'] = None
            base['quantity']           = row['Qty'] or base.get('quantity')
            base['uom']                = row['UoM'] or 'NOS'
            base['special']            = row['Special'] or None
            # Clear derived fields so rules engine recalculates cleanly
            for f in ('size_norm', 'rating_norm', 'status', 'flags', 'applied_defaults', 'dimensions'):
                base.pop(f, None)
            item = apply_rules(base)
            item['ggpl_description'] = format_description(item)
            updated.append(item)
        st.session_state.results = updated
        st.session_state.pop('_bulk_df', None)
        st.session_state._selected_rows = set()
        st.rerun()

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
            st.text_area('RFI draft', value=rfi_text, height=200, label_visibility='collapsed')

    # ---------------------------------------------------------------------------
    # Step 3 — Export
    # ---------------------------------------------------------------------------
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
