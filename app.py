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

st.set_page_config(
    page_title='Gasket Quote Processor',
    page_icon='⚙️',
    layout='wide',
    initial_sidebar_state='expanded',
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ── Global resets ─────────────────────────────────────────── */
[data-testid="stAppViewContainer"] { background: #f4f6f9; }
[data-testid="stSidebar"] { background: #1a2740 !important; }
[data-testid="stSidebar"] * { color: #e8ecf1 !important; }
[data-testid="stSidebar"] .stButton > button {
    background: #2e4470 !important;
    color: #e8ecf1 !important;
    border: 1px solid #3d5a8a !important;
    border-radius: 6px !important;
    width: 100%;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #3d5a8a !important;
}
[data-testid="stSidebar"] hr { border-color: #2e4470 !important; }

/* ── App header ─────────────────────────────────────────────── */
.gq-header {
    background: linear-gradient(135deg, #1a2740 0%, #2e4470 100%);
    color: #fff;
    padding: 1.4rem 2rem 1.2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1.2rem;
    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
.gq-header-icon { font-size: 2.6rem; line-height: 1; }
.gq-header-title { font-size: 1.7rem; font-weight: 700; letter-spacing: -0.5px; margin: 0; }
.gq-header-sub   { font-size: 0.85rem; opacity: 0.75; margin: 3px 0 0; }

/* ── Step cards ─────────────────────────────────────────────── */
.gq-step {
    background: #fff;
    border-radius: 10px;
    padding: 1.4rem 1.6rem 1.2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    margin-bottom: 1.2rem;
    border-left: 4px solid #2e4470;
}
.gq-step-label {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    margin-bottom: 1rem;
}
.gq-step-badge {
    background: #2e4470;
    color: #fff;
    border-radius: 50%;
    width: 28px; height: 28px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.85rem;
    flex-shrink: 0;
}
.gq-step-title { font-size: 1.05rem; font-weight: 600; color: #1a2740; margin: 0; }

/* ── Status metric cards ────────────────────────────────────── */
.gq-metrics { display: flex; gap: 0.8rem; margin: 0.8rem 0 1rem; }
.gq-metric {
    flex: 1;
    border-radius: 10px;
    padding: 0.9rem 1rem;
    text-align: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}
.gq-metric .val { font-size: 1.9rem; font-weight: 700; line-height: 1.1; }
.gq-metric .lbl { font-size: 0.73rem; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
.gq-total   { background: #eef2fa; color: #2e4470; }
.gq-total .lbl { color: #5a7aab; }
.gq-ready   { background: #e6f4ec; color: #1a7a3c; }
.gq-ready .lbl { color: #3a9a5c; }
.gq-check   { background: #fff8e6; color: #9a6800; }
.gq-check .lbl { color: #c08000; }
.gq-missing { background: #fdecea; color: #b91c1c; }
.gq-missing .lbl { color: #d94040; }

/* ── Sidebar history entries ────────────────────────────────── */
.gq-hist-meta { font-size: 0.78rem; opacity: 0.7; margin: 2px 0 6px; }
.gq-hist-pills { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.gq-pill {
    font-size: 0.7rem;
    padding: 1px 7px;
    border-radius: 20px;
    font-weight: 600;
}
.gq-pill-ready   { background: #1a7a3c; color: #fff; }
.gq-pill-check   { background: #9a6800; color: #fff; }
.gq-pill-missing { background: #b91c1c; color: #fff; }

/* ── Sidebar section title ──────────────────────────────────── */
.gq-sidebar-title {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.55;
    margin: 0.5rem 0 0.4rem;
}

/* ── Status indicator in sidebar ───────────────────────────── */
.gq-ai-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.55rem 0.8rem;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 500;
    margin-bottom: 0.5rem;
}
.gq-ai-on  { background: #1a4a2e; }
.gq-ai-off { background: #2e3a52; }
.gq-ai-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.gq-ai-dot-on  { background: #4caf50; box-shadow: 0 0 6px #4caf50; }
.gq-ai-dot-off { background: #7a8eaa; }

/* ── Process button ─────────────────────────────────────────── */
[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #2e4470, #1a2740) !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    padding: 0.6rem 2rem !important;
    box-shadow: 0 3px 10px rgba(46,68,112,0.35) !important;
    transition: transform 0.1s, box-shadow 0.1s !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 5px 14px rgba(46,68,112,0.45) !important;
}

/* ── Download button ────────────────────────────────────────── */
[data-testid="stDownloadButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #1a7a3c, #155c2e) !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    box-shadow: 0 3px 10px rgba(26,122,60,0.35) !important;
}

/* ── Data editor container ──────────────────────────────────── */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* ── Warning / info callouts ────────────────────────────────── */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* ── Expander ────────────────────────────────────────────────── */
details { border-radius: 8px !important; }

/* ── Filter radio ───────────────────────────────────────────── */
[data-testid="stRadio"] > div { gap: 0.5rem !important; }

/* ── Progress bar ───────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div { background: #2e4470 !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

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
if 'run_history' not in st.session_state:
    st.session_state.run_history = []
if '_history_loaded' not in st.session_state:
    st.session_state._history_loaded = False

# Load history from Redis once per session
if not st.session_state._history_loaded:
    import json as _json
    from core.extractor import _get_redis as _get_redis_client
    _r = _get_redis_client()
    if _r:
        try:
            _raw = _r.get('gq:run_history')
            if _raw:
                st.session_state.run_history = _json.loads(_raw)
        except Exception:
            pass
    st.session_state._history_loaded = True

import os as _os
import datetime as _dt
import json as _json


def _save_history_to_redis():
    from core.extractor import _get_redis as _get_redis_client
    _r = _get_redis_client()
    if _r:
        try:
            _r.set('gq:run_history', _json.dumps(st.session_state.run_history))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="gq-sidebar-title">System Status</div>', unsafe_allow_html=True)
    if _os.environ.get('OPENAI_API_KEY'):
        st.markdown(
            '<div class="gq-ai-status gq-ai-on">'
            '<div class="gq-ai-dot gq-ai-dot-on"></div>'
            'AI extraction active'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="gq-ai-status gq-ai-off">'
            '<div class="gq-ai-dot gq-ai-dot-off"></div>'
            'Rule-based mode only'
            '</div>',
            unsafe_allow_html=True,
        )
        api_key_input = st.text_input(
            'OpenAI API Key', type='password', placeholder='sk-...', label_visibility='collapsed',
            help='Paste your key to enable AI extraction',
        )
        if api_key_input:
            _os.environ['OPENAI_API_KEY'] = api_key_input
            st.rerun()

    st.markdown('<hr style="margin:0.8rem 0;border-color:#2e4470">', unsafe_allow_html=True)
    st.markdown('<div class="gq-sidebar-title">Run History</div>', unsafe_allow_html=True)

    history = st.session_state.run_history
    if not history:
        st.markdown('<p style="font-size:0.8rem;opacity:0.5;margin:0.4rem 0">No runs yet this session.</p>',
                    unsafe_allow_html=True)
    else:
        for idx, run in enumerate(reversed(history)):
            run_idx = len(history) - 1 - idx
            label = run['customer'] or run['project_ref'] or f'Run {run_idx + 1}'
            with st.expander(f'**{label}**', expanded=False):
                st.markdown(
                    f'<div class="gq-hist-meta">{run["timestamp"]}</div>'
                    f'<div class="gq-hist-pills">'
                    f'<span class="gq-pill gq-pill-ready">✅ {run["n_ready"]}</span>'
                    f'<span class="gq-pill gq-pill-check">🟡 {run["n_check"]}</span>'
                    f'<span class="gq-pill gq-pill-missing">🔴 {run["n_missing"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                btn_col, del_col = st.columns(2)
                if btn_col.button('Restore', key=f'restore_{run_idx}'):
                    st.session_state.results = run['items']
                    st.session_state._selected_rows = set()
                    st.session_state.pop('_bulk_df', None)
                    st.session_state.filter_mode = 'All'
                    st.rerun()
                if del_col.button('Delete', key=f'delete_{run_idx}', type='secondary'):
                    from core.extractor import _get_redis, _cache_key
                    r = _get_redis()
                    if r:
                        descs = {
                            item.get('raw_description', '')
                            for item in run['items']
                            if item.get('raw_description')
                        }
                        for desc in descs:
                            try:
                                r.delete(_cache_key(desc))
                            except Exception:
                                pass
                    st.session_state.run_history.pop(run_idx)
                    _save_history_to_redis()
                    st.rerun()


# ---------------------------------------------------------------------------
# App header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="gq-header">
  <div class="gq-header-icon">⚙️</div>
  <div>
    <p class="gq-header-title">Gasket Quote Processor</p>
    <p class="gq-header-sub">Goodrich Gasket Pvt. Ltd — Soft cut &amp; spiral wound · ASME &amp; EN/PN standards</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Step 1 — Input
# ---------------------------------------------------------------------------
st.markdown("""
<div class="gq-step">
  <div class="gq-step-label">
    <span class="gq-step-badge">1</span>
    <p class="gq-step-title">Paste email or upload Excel</p>
  </div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 1], gap='large')

with col1:
    email_text = st.text_area(
        'Paste email body',
        height=200,
        placeholder='Paste the customer email text containing gasket requirements...',
        label_visibility='visible',
    )

with col2:
    uploaded_file = st.file_uploader(
        'Upload Excel file',
        type=['xlsx', 'xls'],
        help='Supports multi-sheet enquiry files',
    )
    st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
    customer = st.text_input('Customer name', placeholder='e.g. VA Tech Wabag')
    project_ref = st.text_input('Project / PO reference', placeholder='e.g. HPCL Vizag Refinery')

st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)


def _build_preview_df(items):
    STATUS_ICON = {'ready': '✅', 'check': '🟡', 'missing': '🔴'}
    return pd.DataFrame([{
        '#':                    item.get('line_no', ''),
        'S':                    STATUS_ICON.get(item.get('status', ''), ''),
        'Customer Description': (item.get('raw_description') or '')[:80],
        'GGPL Description':     item.get('ggpl_description', ''),
        'Notes':                '; '.join((item.get('flags') or [])[:2]),
    } for item in items])


if st.button('⚡  Process Enquiry', type='primary', use_container_width=True):
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

        proc_container = st.container()
        with proc_container:
            status_text = st.empty()
            progress_bar = st.progress(0)
            preview_ph   = st.empty()

        status_text.text(f'Extracting {unique_count} unique descriptions...')
        progress_bar.progress(5)

        def _on_progress(done, total):
            pct = int(done / total * 100)
            status_text.text(f'Extracting... {done}/{total} descriptions ({pct}%)')
            progress_bar.progress(5 + int(done / total * 70))

        extracted_items = extract_batch(raw_items, progress_cb=_on_progress)
        progress_bar.progress(75)

        n = len(extracted_items)
        step = max(1, n // 20)
        processed = []

        for i, extracted in enumerate(extracted_items, 1):
            item = apply_rules(extracted)
            item['ggpl_description'] = format_description(item)
            processed.append(item)
            progress_bar.progress(75 + int(i / n * 24))
            if i % step == 0 or i == n:
                status_text.text(f'Processing {i}/{n} items...')
                preview_ph.dataframe(
                    _build_preview_df(processed),
                    use_container_width=True,
                    hide_index=True,
                )

        progress_bar.empty()
        status_text.empty()
        preview_ph.empty()
        st.session_state.results = processed
        st.session_state._selected_rows = set()
        st.session_state.pop('_bulk_df', None)
        st.session_state.filter_mode = 'All'

        st.session_state.run_history.append({
            'timestamp':   _dt.datetime.now().strftime('%d %b %H:%M'),
            'customer':    customer or '',
            'project_ref': project_ref or '',
            'n_items':     len(processed),
            'n_ready':     sum(1 for i in processed if i['status'] == STATUS_READY),
            'n_check':     sum(1 for i in processed if i['status'] == STATUS_CHECK),
            'n_missing':   sum(1 for i in processed if i['status'] == STATUS_MISSING),
            'items':       processed,
        })
        if len(st.session_state.run_history) > 15:
            st.session_state.run_history = st.session_state.run_history[-15:]
        _save_history_to_redis()


# ---------------------------------------------------------------------------
# Helper — build display rows
# ---------------------------------------------------------------------------
def _build_rows(items):
    rows = []
    for item in items:
        status_icon = {'ready': '✅', 'check': '🟡', 'missing': '🔴'}.get(item['status'], '')
        flags    = item.get('flags', [])
        defaults = item.get('applied_defaults', [])
        parts    = list(flags) + [f'[default] {d}' for d in defaults]
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
# ---------------------------------------------------------------------------
@st.fragment
def _editor_fragment(items, display_indices):
    display_items = [items[i] for i in display_indices]

    if '_bulk_df' in st.session_state:
        df = st.session_state['_bulk_df'].copy()
    else:
        df = pd.DataFrame(_build_rows(display_items))

    df = df.drop(columns=[c for c in ('Select', 'Delete') if c in df.columns])
    df.insert(0, 'Delete', False)
    df.insert(0, 'Select', [i in st.session_state._selected_rows for i in range(len(df))])

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        height=min(80 + 35 * len(display_items), 620),
        hide_index=True,
        column_config={
            'Select':               st.column_config.CheckboxColumn('Select', width='small'),
            'Delete':               st.column_config.CheckboxColumn('🗑', width='small', help='Tick to delete on Update'),
            '#':                    st.column_config.NumberColumn('#', width='small', disabled=True),
            'Customer Description': st.column_config.TextColumn('Customer Description', width='large', disabled=True),
            'Type':                 st.column_config.SelectboxColumn('Type', options=TYPE_OPTIONS, width='small'),
            'Size':                 st.column_config.TextColumn('Size', width='small'),
            'Rating':               st.column_config.TextColumn('Rating', width='small'),
            'MOC':                  st.column_config.TextColumn('MOC', width='large'),
            'Face':                 st.column_config.SelectboxColumn('Face', options=FACE_OPTIONS, width='small'),
            'Thk (mm)':             st.column_config.NumberColumn('Thk (mm)', width='small', min_value=0),
            'Ring No':              st.column_config.TextColumn('Ring No', width='small', help='RTJ ring e.g. R-23'),
            'Groove':               st.column_config.SelectboxColumn('Groove', options=GROOVE_OPTIONS, width='small'),
            'BHN':                  st.column_config.TextColumn('BHN', width='small', help='e.g. 90 BHN HARDNESS'),
            'SW Winding':           st.column_config.TextColumn('SW Winding', width='small'),
            'SW Filler':            st.column_config.TextColumn('SW Filler', width='small'),
            'SW Outer Ring':        st.column_config.TextColumn('SW Outer Ring', width='small'),
            'SW Inner Ring':        st.column_config.TextColumn('SW Inner Ring', width='small'),
            'Qty':                  st.column_config.NumberColumn('Qty', width='small', min_value=0),
            'UoM':                  st.column_config.SelectboxColumn('UoM', options=UOM_OPTIONS, width='small'),
            'Special':              st.column_config.TextColumn('Special', width='medium'),
            'GGPL Description':     st.column_config.TextColumn('GGPL Description', width='large', disabled=True),
            'Status':               st.column_config.TextColumn('Status', width='small', disabled=True),
            'AI':                   st.column_config.TextColumn('AI', width='small', disabled=True,
                                        help='Confidence: HIGH / MEDIUM / LOW'),
            'Notes / Flags':        st.column_config.TextColumn('Notes / Flags', width='large', disabled=True),
        },
    )

    st.session_state._selected_rows = {i for i, row in edited_df.iterrows() if row['Select']}

    if st.button('↻  Update Descriptions', type='secondary', key='update_btn'):
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

    n_ready   = sum(1 for i in items if i['status'] == STATUS_READY)
    n_check   = sum(1 for i in items if i['status'] == STATUS_CHECK)
    n_missing = sum(1 for i in items if i['status'] == STATUS_MISSING)

    st.markdown("""
    <div class="gq-step">
      <div class="gq-step-label">
        <span class="gq-step-badge">2</span>
        <p class="gq-step-title">Review &amp; Edit</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Colored metric cards
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
    </div>
    """, unsafe_allow_html=True)

    # Filter
    filter_col, spacer = st.columns([4, 6])
    with filter_col:
        filter_mode = st.radio(
            'Show',
            ['All', 'Issues (🟡 + 🔴)', 'Missing only (🔴)'],
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
    else:
        display_indices = list(range(len(items)))

    if not display_indices:
        st.success('No items match this filter.')
    else:
        sa1, sa2, sa3, _ = st.columns([1, 1.3, 1.2, 7])
        if sa1.button('Select All', key='sel_all_btn'):
            st.session_state._selected_rows = set(range(len(display_indices)))
        if sa2.button('Deselect All', key='desel_all_btn'):
            st.session_state._selected_rows = set()
        if sa3.button('＋ Add Row', key='add_row_btn'):
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
                st.success(f'Applied to {len(target)} row(s). Click **↻ Update Descriptions** to regenerate.')

        _editor_fragment(items, display_indices)

    # Missing items summary + RFI
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
    # Step 3 — Export
    # -------------------------------------------------------------------------
    st.markdown("""
    <div class="gq-step" style="border-left-color:#1a7a3c">
      <div class="gq-step-label">
        <span class="gq-step-badge" style="background:#1a7a3c">3</span>
        <p class="gq-step-title">Export Quote</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    excel_bytes = build_excel(items, customer=customer, project_ref=project_ref)
    filename = f"quote_{project_ref or customer or 'output'}.xlsx".replace(' ', '_')

    dl_col, info_col = st.columns([2, 3])
    with dl_col:
        st.download_button(
            label='⬇  Download Quote Excel',
            data=excel_bytes,
            file_name=filename,
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            type='primary',
            use_container_width=True,
        )
    with info_col:
        st.markdown(
            f'<p style="color:#555;font-size:0.85rem;margin:0.6rem 0 0">'
            f'<strong>{filename}</strong><br>'
            f'{len(items)} items · '
            f'<span style="color:#1a7a3c">{n_ready} ready</span> · '
            f'<span style="color:#9a6800">{n_check} defaults</span> · '
            f'<span style="color:#b91c1c">{n_missing} missing</span>'
            f'</p>',
            unsafe_allow_html=True,
        )
