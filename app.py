"""
Gasket Quote Processor — Streamlit MVP
Soft cut & spiral wound gaskets.
"""
import streamlit as st
import pandas as pd

from core.parser import parse_email_text, parse_excel_file
from core.rules import apply_rules, STATUS_READY, STATUS_CHECK, STATUS_MISSING, STATUS_REGRET
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
.gq-regret  { background: #eeeeee; color: #666666; }
.gq-regret .lbl { color: #888888; }

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
.gq-pill-regret  { background: #888888; color: #fff; }

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

/* ── Floating chat widget ───────────────────────────────────── */
#gq-fab {
    position: fixed !important;
    bottom: 28px !important;
    right: 28px !important;
    width: 58px !important;
    height: 58px !important;
    border-radius: 50% !important;
    background: linear-gradient(135deg, #2e4470, #1a2740) !important;
    color: #fff !important;
    font-size: 1.5rem !important;
    border: none !important;
    cursor: pointer !important;
    box-shadow: 0 4px 20px rgba(46,68,112,0.55) !important;
    z-index: 10001 !important;
    transition: transform 0.18s, box-shadow 0.18s !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
#gq-fab:hover {
    transform: scale(1.1) !important;
    box-shadow: 0 6px 26px rgba(46,68,112,0.7) !important;
}

/* Full panel — input placeholder is built into the bottom of the panel */
#gq-chat-panel {
    position: fixed !important;
    bottom: 88px !important;
    right: 28px !important;
    width: 460px !important;
    height: 520px !important;
    background: #fff !important;
    border-radius: 16px !important;
    border: 1px solid #dde3f0 !important;
    z-index: 10000 !important;
    display: none !important;
    flex-direction: column !important;
    overflow: hidden !important;
    box-shadow: 0 8px 40px rgba(0,0,0,0.18) !important;
}
#gq-chat-panel.gqcp-open { display: flex !important; }

#gq-chat-hdr {
    background: linear-gradient(135deg, #2e4470, #1a2740);
    color: #fff;
    padding: 0.85rem 1.1rem;
    font-weight: 600;
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-shrink: 0;
}
#gq-chat-hdr .gq-online-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #4ade80;
    box-shadow: 0 0 5px #4ade80;
    flex-shrink: 0;
}
.gq-chat-hdr-close {
    margin-left: auto;
    background: rgba(255,255,255,0.15) !important;
    border: none !important;
    color: #fff !important;
    cursor: pointer !important;
    width: 28px !important;
    height: 28px !important;
    border-radius: 50% !important;
    font-size: 1rem !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    line-height: 1 !important;
    transition: background 0.15s !important;
}
.gq-chat-hdr-close:hover { background: rgba(255,255,255,0.28) !important; }

#gq-chat-body {
    flex: 1;
    overflow-y: scroll;
    overscroll-behavior: contain;
    padding: 1rem 1rem 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    background: #f4f7fd;
    scroll-behavior: smooth;
    min-height: 0;
}
#gq-chat-body::-webkit-scrollbar { width: 5px; }
#gq-chat-body::-webkit-scrollbar-track { background: transparent; }
#gq-chat-body::-webkit-scrollbar-thumb { background: #c8d3e8; border-radius: 4px; }

#gq-chat-nokey {
    padding: 0.55rem 1rem;
    background: #fffbe6;
    border-top: 1px solid #fde68a;
    font-size: 0.83rem;
    color: #92620a;
    flex-shrink: 0;
}

/* Typing / loading indicator */
@keyframes gq-bounce {
    0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
    40%            { transform: translateY(-5px); opacity: 1; }
}
.gq-typing { display: flex; gap: 5px; align-items: center; padding: 10px 14px; }
.gq-typing span {
    width: 8px; height: 8px; border-radius: 50%;
    background: #8fa3c8;
    animation: gq-bounce 1.1s infinite;
}
.gq-typing span:nth-child(2) { animation-delay: 0.18s; }
.gq-typing span:nth-child(3) { animation-delay: 0.36s; }

/* Input footer — visual placeholder at the bottom of the panel */
#gq-chat-footer {
    flex-shrink: 0;
    height: 64px;
    background: #fff;
    border-top: 1px solid #e4eaf5;
}

/* stBottom — transparent floating layer over the panel footer */
[data-testid="stBottom"] {
    position: fixed !important;
    bottom: 88px !important;
    right: 28px !important;
    width: 460px !important;
    height: 64px !important;
    left: auto !important;
    padding: 0 !important;
    margin: 0 !important;
    z-index: 10002 !important;
    display: none !important;
    overflow: visible !important;
}
/* Kill every white/shadowed box inside stBottom */
[data-testid="stBottom"],
[data-testid="stBottom"]::before,
[data-testid="stBottom"]::after,
[data-testid="stBottom"] * {
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
}
body:has(#gq-chat-panel.gqcp-open) [data-testid="stBottom"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
/* Flatten every wrapper layer so they don't break vertical centering */
body:has(#gq-chat-panel.gqcp-open) [data-testid="stBottom"] > *,
body:has(#gq-chat-panel.gqcp-open) [data-testid="stBottom"] > * > * {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    height: auto !important;
    padding: 0 !important;
    margin: 0 !important;
    flex: 1 !important;
}
/* The actual input element — 90% width */
body:has(#gq-chat-panel.gqcp-open) [data-testid="stChatInput"],
body:has(#gq-chat-panel.gqcp-open) .stChatInput {
    width: 90% !important;
    flex: none !important;
}
body:has(#gq-chat-panel.gqcp-open) [data-testid="stChatInputContainer"] {
    background: #f0f4fa !important;
    border-radius: 24px !important;
    border: 1.5px solid #cdd6ea !important;
    padding: 2px 8px !important;
    width: 100% !important;
    flex: 1 !important;
}
body:has(#gq-chat-panel.gqcp-open) [data-testid="stChatInput"] textarea {
    color: #111 !important;
    background: transparent !important;
    caret-color: #2e4470 !important;
    font-size: 0.93rem !important;
    line-height: 1.5 !important;
    padding: 8px 4px !important;
}
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
if 'working_items' not in st.session_state:
    st.session_state.working_items = []
if '_selected_rows' not in st.session_state:
    st.session_state._selected_rows = set()
if 'filter_mode' not in st.session_state:
    st.session_state.filter_mode = 'All'
if 'run_history' not in st.session_state:
    st.session_state.run_history = []
if '_history_loaded' not in st.session_state:
    st.session_state._history_loaded = False
if '_show_confirm' not in st.session_state:
    st.session_state._show_confirm = False
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'chat_open' not in st.session_state:
    st.session_state.chat_open = False  # unused for panel CSS; panel state managed by JS sessionStorage
if 'chat_loading' not in st.session_state:
    st.session_state.chat_loading = False

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
    st.markdown('<div class="gq-sidebar-title">Enquiry History</div>', unsafe_allow_html=True)

    history = st.session_state.run_history
    if not history:
        st.markdown('<p style="font-size:0.8rem;opacity:0.5;margin:0.4rem 0">No enquiries committed yet.</p>',
                    unsafe_allow_html=True)
    else:
        for idx, run in enumerate(reversed(history)):
            run_idx = len(history) - 1 - idx
            label = run['customer'] or run['project_ref'] or f'Enquiry {run_idx + 1}'
            with st.expander(f'**{label}**', expanded=False):
                n_regret_h = run.get('n_regret', 0)
                st.markdown(
                    f'<div class="gq-hist-meta">{run["timestamp"]}</div>'
                    f'<div class="gq-hist-pills">'
                    f'<span class="gq-pill gq-pill-ready">✅ {run["n_ready"]}</span>'
                    f'<span class="gq-pill gq-pill-check">🟡 {run["n_check"]}</span>'
                    f'<span class="gq-pill gq-pill-missing">🔴 {run["n_missing"]}</span>'
                    + (f'<span class="gq-pill gq-pill-regret">⛔ {n_regret_h}</span>' if n_regret_h else '')
                    + '</div>',
                    unsafe_allow_html=True,
                )
                btn_col, del_col = st.columns(2)
                if btn_col.button('Restore', key=f'restore_{run_idx}'):
                    st.session_state.working_items = [dict(i) for i in run['items']]
                    st.session_state._selected_rows = set()
                    st.session_state.pop('_bulk_df', None)
                    st.session_state.pop('_last_excel', None)
                    st.session_state.filter_mode = 'All'
                    st.session_state._show_confirm = False
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
# Customer / Project ref — captured once, used throughout
# ---------------------------------------------------------------------------
ref_c1, ref_c2 = st.columns(2)
with ref_c1:
    customer = st.text_input('Customer name', key='inp_customer', placeholder='e.g. VA Tech Wabag')
with ref_c2:
    project_ref = st.text_input('Project / PO reference', key='inp_project_ref', placeholder='e.g. HPCL Vizag Refinery')

st.markdown('<div style="height:0.3rem"></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper — build display rows
# ---------------------------------------------------------------------------
def _build_preview_df(items):
    STATUS_ICON = {'ready': '✅', 'check': '🟡', 'missing': '🔴'}
    return pd.DataFrame([{
        '#':                    item.get('line_no', ''),
        'S':                    STATUS_ICON.get(item.get('status', ''), ''),
        'Customer Description': (item.get('raw_description') or '')[:80],
        'GGPL Description':     item.get('ggpl_description', ''),
        'Notes':                '; '.join((item.get('flags') or [])[:2]),
    } for item in items])


def _build_rows(items):
    rows = []
    for item in items:
        status_icon = {'ready': '✅', 'check': '🟡', 'missing': '🔴', 'regret': '⛔'}.get(item['status'], '')
        flags    = item.get('flags', [])
        defaults = item.get('applied_defaults', [])
        parts    = list(flags) + [f'[default] {d}' for d in defaults]
        rows.append({
            '#':                    item.get('line_no', ''),
            'Regret':               item.get('regret', False),
            'Customer Description': item.get('raw_description', ''),
            'Type':                 item.get('gasket_type', 'SOFT_CUT'),
            'Size':                 item.get('size') or '',
            'Rating':               item.get('rating') or '',
            'Standard':             item.get('standard') or '',
            'MOC':                  item.get('moc') or '',
            'Face':                 item.get('face_type') or '',
            'Series':               item.get('series') or '',
            'Thk (mm)':             item.get('thickness_mm') if item.get('thickness_mm') is not None else None,
            'Ring No':              item.get('ring_no') or '',
            'Groove':               item.get('rtj_groove_type') or '',
            'BHN':                  item.get('rtj_hardness_bhn') or None,
            'SW Winding':           item.get('sw_winding_material') or '',
            'SW Filler':            item.get('sw_filler') or '',
            'SW Outer Ring':        item.get('sw_outer_ring') or '',
            'SW Inner Ring':        item.get('sw_inner_ring') or '',
            'ISK Gasket Mat':       item.get('isk_gasket_material') or '',
            'ISK Core':             item.get('isk_core_material') or '',
            'ISK Sleeves':          item.get('isk_sleeve_material') or '',
            'ISK Washers':          item.get('isk_washer_material') or '',
            'KAMM Core':            item.get('kamm_core_material') or '',
            'KAMM Surface':         item.get('kamm_surface_material') or '',
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

    df = df.drop(columns=[c for c in ('Select',) if c in df.columns])
    df.insert(0, 'Select', [i in st.session_state._selected_rows for i in range(len(df))])

    edited_df = st.data_editor(
        df,
        width="stretch",
        height=min(80 + 35 * len(display_items), 620),
        hide_index=True,
        column_config={
            'Select':               st.column_config.CheckboxColumn('☑', width='small',
                                        help='Select rows for bulk actions below'),
            'Regret':               st.column_config.CheckboxColumn('⛔ Regret', width='small',
                                        help='Tick = GGPL cannot produce this item'),
            '#':                    st.column_config.NumberColumn('#', width='small', disabled=True),
            'Customer Description': st.column_config.TextColumn('Customer Description', width='large', disabled=True),
            'Type':                 st.column_config.SelectboxColumn('Type', options=TYPE_OPTIONS, width='small'),
            'Size':                 st.column_config.TextColumn('Size', width='small'),
            'Rating':               st.column_config.TextColumn('Rating', width='small'),
            'Standard':             st.column_config.TextColumn('Standard', width='medium',
                                        help='e.g. ASME B16.20, ASME B16.21, ASME B16.47 (SERIES-A), API 6A'),
            'MOC':                  st.column_config.TextColumn('MOC', width='large'),
            'Face':                 st.column_config.SelectboxColumn('Face', options=FACE_OPTIONS, width='small'),
            'Series':               st.column_config.SelectboxColumn('Series', options=['', 'A', 'B'], width='small',
                                        help='B16.47 only — Series A (ex-API 605) or Series B (ex-MSS SP-44)'),
            'Thk (mm)':             st.column_config.NumberColumn('Thk (mm)', width='small', min_value=0),
            'Ring No':              st.column_config.TextColumn('Ring No', width='small', help='RTJ ring e.g. R-23'),
            'Groove':               st.column_config.SelectboxColumn('Groove', options=GROOVE_OPTIONS, width='small'),
            'BHN':                  st.column_config.NumberColumn('BHN', width='small', min_value=1, step=10, help='Enter number only — BHN HARDNESS appended automatically'),
            'SW Winding':           st.column_config.TextColumn('SW Winding', width='small'),
            'SW Filler':            st.column_config.TextColumn('SW Filler', width='small'),
            'SW Outer Ring':        st.column_config.TextColumn('SW Outer Ring', width='small'),
            'SW Inner Ring':        st.column_config.TextColumn('SW Inner Ring', width='small'),
            'ISK Gasket Mat':       st.column_config.TextColumn('ISK Gasket Mat', width='small',
                                        help='ISK gasket ring material e.g. GRE G10, PTFE, PEEK'),
            'ISK Core':             st.column_config.TextColumn('ISK Core', width='small',
                                        help='ISK metal core e.g. SS316, CS, DUPLEX'),
            'ISK Sleeves':          st.column_config.TextColumn('ISK Sleeves', width='small',
                                        help='ISK sleeve insulation material'),
            'ISK Washers':          st.column_config.TextColumn('ISK Washers', width='small',
                                        help='ISK washer/bolt material e.g. CS, SS316'),
            'KAMM Core':            st.column_config.TextColumn('KAMM Core', width='small',
                                        help='Kammprofile metal core e.g. SS316, ALLOY 625'),
            'KAMM Surface':         st.column_config.TextColumn('KAMM Surface', width='small',
                                        help='Kammprofile surface material e.g. GRAPHITE, PTFE'),
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
    n_sel = len(st.session_state._selected_rows)
    sel_label = f'{n_sel} selected' if n_sel else 'none selected'

    act_c1, act_c2, act_c3, act_c4 = st.columns([2.2, 2, 2, 4])

    # ── Update Descriptions ──────────────────────────────────────────────────
    if act_c1.button('↻  Update Descriptions', type='secondary', key='update_btn'):
        updated_full = list(items)

        for i, row in edited_df.iterrows():
            orig_idx = display_indices[i]
            base = items[orig_idx].copy()
            base['gasket_type']        = row['Type'] or base.get('gasket_type', 'SOFT_CUT')
            base['size']               = row['Size'] or base.get('size')
            base['rating']             = row['Rating'] or base.get('rating')
            base['standard']           = row['Standard'] or None
            base['moc']                = row['MOC'] or None
            base['face_type']          = row['Face'] or None
            base['series']             = row['Series'] or None
            base['thickness_mm']       = row['Thk (mm)'] or None
            base['ring_no']            = row['Ring No'] or None
            base['rtj_groove_type']    = row['Groove'] or None
            bhn_val = row['BHN'] or None
            if bhn_val:
                bhn_int = int(float(bhn_val))
                base['rtj_hardness_bhn']  = bhn_int
                base['rtj_hardness_spec'] = f'{bhn_int} BHN HARDNESS'
            else:
                base['rtj_hardness_bhn']  = None
                base['rtj_hardness_spec'] = None
            base['sw_winding_material']  = row['SW Winding'] or None
            base['sw_filler']            = row['SW Filler'] or None
            base['sw_outer_ring']        = row['SW Outer Ring'] or None
            base['sw_inner_ring']        = row['SW Inner Ring'] or None
            base['isk_gasket_material']  = row['ISK Gasket Mat'] or None
            base['isk_core_material']    = row['ISK Core'] or None
            base['isk_sleeve_material']  = row['ISK Sleeves'] or None
            base['isk_washer_material']  = row['ISK Washers'] or None
            base['kamm_core_material']   = row['KAMM Core'] or None
            base['kamm_surface_material']= row['KAMM Surface'] or None
            # For SPW/KAMM, always clear MOC so apply_rules rebuilds it from
            # the current component fields (winding, filler, inner/outer ring).
            if base.get('gasket_type') in ('SPIRAL_WOUND', 'KAMM'):
                base['moc'] = None
            base['quantity']           = row['Qty'] or base.get('quantity')
            base['uom']                = row['UoM'] or 'NOS'
            base['special']            = row['Special'] or None
            # Preserve regret from checkbox
            base['regret'] = bool(row.get('Regret'))
            for f in ('size_norm', 'rating_norm', 'status', 'flags', 'applied_defaults', 'dimensions'):
                base.pop(f, None)
            updated = apply_rules(base)
            updated['ggpl_description'] = format_description(updated)
            # Regret overrides calculated status
            if base['regret']:
                updated['status'] = STATUS_REGRET
                updated['regret'] = True
            updated_full[orig_idx] = updated

        for j, it in enumerate(updated_full, 1):
            it['line_no'] = j
        st.session_state.working_items = updated_full
        st.session_state.pop('_bulk_df', None)
        st.session_state._selected_rows = set()
        st.rerun(scope='app')

    # ── Delete Selected ──────────────────────────────────────────────────────
    if act_c2.button(f'🗑  Delete ({sel_label})', type='secondary', key='delete_sel_btn',
                     disabled=(n_sel == 0)):
        to_delete = {display_indices[i] for i in st.session_state._selected_rows}
        final = [it for idx, it in enumerate(items) if idx not in to_delete]
        for j, it in enumerate(final, 1):
            it['line_no'] = j
        st.session_state.working_items = final
        st.session_state._selected_rows = set()
        st.session_state.pop('_bulk_df', None)
        st.rerun(scope='app')

    # ── Mark as Regret ───────────────────────────────────────────────────────
    if act_c3.button(f'⛔  Regret ({sel_label})', type='secondary', key='regret_sel_btn',
                     disabled=(n_sel == 0),
                     help='Mark selected items as REGRET — GGPL cannot produce'):
        updated_full = list(items)
        for i in st.session_state._selected_rows:
            orig_idx = display_indices[i]
            it = dict(updated_full[orig_idx])
            # Toggle: if already regret, clear it; otherwise set it
            if it.get('regret'):
                it['regret'] = False
                it.pop('status', None)
                it = apply_rules(it)
                it['ggpl_description'] = format_description(it)
            else:
                it['regret'] = True
                it['status'] = STATUS_REGRET
            updated_full[orig_idx] = it
        st.session_state.working_items = updated_full
        st.session_state._selected_rows = set()
        st.session_state.pop('_bulk_df', None)
        st.rerun(scope='app')


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

tab_email, tab_excel, tab_manual = st.tabs(['📧 Email / Text', '📊 Excel File', '✏️ Add Manually'])


def _process_and_append(raw_items):
    """Extract, apply rules, and append processed items to working_items."""
    if not raw_items:
        st.warning('No gasket line items found. Check your input and try again.')
        return False

    from core.extractor import extract_batch
    unique_count = len({item['description'] for item in raw_items})

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

    # Offset line numbers from existing items
    existing = st.session_state.working_items
    line_offset = (max(i.get('line_no', 0) for i in existing) if existing else 0)

    for i, extracted in enumerate(extracted_items, 1):
        item = apply_rules(extracted)
        item['ggpl_description'] = format_description(item)
        item['line_no'] = line_offset + i
        processed.append(item)
        progress_bar.progress(75 + int(i / n * 24))
        if i % step == 0 or i == n:
            status_text.text(f'Processing {i}/{n} items...')
            preview_ph.dataframe(
                _build_preview_df(processed),
                width="stretch",
                hide_index=True,
            )

    progress_bar.empty()
    status_text.empty()
    preview_ph.empty()

    st.session_state.working_items = existing + processed
    st.session_state._selected_rows = set()
    st.session_state.pop('_bulk_df', None)
    st.session_state.filter_mode = 'All'
    st.session_state._show_confirm = False
    return True


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
    )
    st.caption(_wl_hint)
    if st.button('⚡  Process & Add to List', type='primary', key='process_email_btn'):
        if email_text.strip():
            raw_items = parse_email_text(email_text)
            if _process_and_append(raw_items):
                st.rerun()
        else:
            st.warning('Please paste some email text first.')

with tab_excel:
    uploaded_file = st.file_uploader(
        'Upload Excel file',
        type=['xlsx', 'xls'],
        help='Supports multi-sheet enquiry files',
    )
    st.caption(_wl_hint)
    if st.button('⚡  Process & Add to List', type='primary', key='process_excel_btn'):
        if uploaded_file:
            raw_items = parse_excel_file(uploaded_file.read())
            if _process_and_append(raw_items):
                st.rerun()
        else:
            st.warning('Please upload an Excel file first.')

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


# ---------------------------------------------------------------------------
# Step 2 — Working List
# ---------------------------------------------------------------------------
if st.session_state.working_items:
    items = st.session_state.working_items

    n_ready   = sum(1 for i in items if i['status'] == STATUS_READY)
    n_check   = sum(1 for i in items if i['status'] == STATUS_CHECK)
    n_missing = sum(1 for i in items if i['status'] == STATUS_MISSING)
    n_regret  = sum(1 for i in items if i['status'] == STATUS_REGRET)

    # Step header + Clear List
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
            st.rerun()

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
      <div class="gq-metric gq-regret">
        <div class="val">{n_regret}</div>
        <div class="lbl">⛔ Regret</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Filter
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
            st.session_state.working_items.append(new_item)
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
    # Step 3 — Generate Enquiry
    # -------------------------------------------------------------------------
    st.markdown("""
    <div class="gq-step" style="border-left-color:#1a7a3c">
      <div class="gq-step-label">
        <span class="gq-step-badge" style="background:#1a7a3c">3</span>
        <p class="gq-step-title">Generate Enquiry</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state._show_confirm:
        st.caption('When you are happy with the working list, click below to do a final review before committing to history.')
        gen_col, _ = st.columns([3, 7])
        with gen_col:
            if st.button('📋  Generate Enquiry', type='primary', key='gen_enquiry_btn'):
                st.session_state._show_confirm = True
                st.rerun()
    else:
        st.markdown(f'**Final Verification** — {len(items)} items · review before saving to history.')
        st.dataframe(_build_preview_df(items), hide_index=True)

        conf_c1, conf_c2, _ = st.columns([2, 1.5, 6])
        with conf_c1:
            if st.button('✅  Confirm & Save to History', type='primary', key='confirm_save_btn'):
                # Build and store Excel
                excel_bytes = build_excel(items, customer=customer, project_ref=project_ref)
                filename = f"quote_{project_ref or customer or 'output'}.xlsx".replace(' ', '_')
                st.session_state['_last_excel'] = excel_bytes
                st.session_state['_last_filename'] = filename

                # Commit to history
                st.session_state.run_history.append({
                    'timestamp':   _dt.datetime.now().strftime('%d %b %H:%M'),
                    'customer':    customer or '',
                    'project_ref': project_ref or '',
                    'n_items':     len(items),
                    'n_ready':     n_ready,
                    'n_check':     n_check,
                    'n_missing':   n_missing,
                    'n_regret':    n_regret,
                    'items':       items,
                })
                if len(st.session_state.run_history) > 15:
                    st.session_state.run_history = st.session_state.run_history[-15:]
                _save_history_to_redis()

                # Clear working list
                st.session_state.working_items = []
                st.session_state._selected_rows = set()
                st.session_state.pop('_bulk_df', None)
                st.session_state._show_confirm = False
                st.rerun()
        with conf_c2:
            if st.button('Cancel', key='cancel_confirm_btn', type='secondary'):
                st.session_state._show_confirm = False
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


# ---------------------------------------------------------------------------
# Floating chat widget — bottom-right popup
# ---------------------------------------------------------------------------
def _build_chat_html():
    msgs = st.session_state.chat_messages[-20:]
    loading = st.session_state.get('chat_loading', False)
    if not msgs and not loading:
        return (
            '<div style="color:#9aabca;font-size:0.88rem;text-align:center;'
            'padding:3rem 1.5rem;line-height:1.6">'
            '<div style="font-size:1.8rem;margin-bottom:0.6rem">⚙️</div>'
            'Ask me anything about gaskets — materials, ratings, standards, dimensions.'
            '</div>'
        )
    out = []
    for m in msgs:
        txt = (m['content']
               .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
               .replace('\n', '<br>'))
        if m['role'] == 'user':
            out.append(
                '<div style="background:#2e4470;color:#fff;'
                'border-radius:16px 16px 4px 16px;'
                'padding:0.65rem 0.95rem;font-size:0.91rem;line-height:1.5;'
                'max-width:82%;margin-left:auto;word-break:break-word;'
                f'box-shadow:0 2px 8px rgba(46,68,112,0.25)">{txt}</div>'
            )
        else:
            if m.get('error'):
                style = ('background:#fdecea;color:#b91c1c;'
                         'border:1px solid #fca5a5;')
            else:
                style = ('background:#fff;color:#1a2740;'
                         'border:1px solid #e4eaf5;')
            out.append(
                f'<div style="{style}border-radius:16px 16px 16px 4px;'
                f'padding:0.65rem 0.95rem;font-size:0.91rem;line-height:1.5;'
                f'max-width:88%;word-break:break-word;'
                f'box-shadow:0 1px 4px rgba(0,0,0,0.06)">{txt}</div>'
            )
    if loading:
        out.append(
            '<div style="background:#fff;border:1px solid #e4eaf5;'
            'border-radius:16px 16px 16px 4px;max-width:88%;'
            'box-shadow:0 1px 4px rgba(0,0,0,0.06)">'
            '<div class="gq-typing">'
            '<span></span><span></span><span></span>'
            '</div></div>'
        )
    return ''.join(out)


_api_ok = bool(_os.environ.get('OPENAI_API_KEY'))

st.markdown(f"""
<button id="gq-fab" title="Gasket Assistant">&#128172;</button>

<div id="gq-chat-panel">
  <div id="gq-chat-hdr">
    <span class="gq-online-dot"></span>
    <span>Gasket Assistant</span>
    <button id="gq-chat-close" class="gq-chat-hdr-close">&#10005;</button>
  </div>
  <div id="gq-chat-body">{_build_chat_html()}</div>
  <div id="gq-chat-footer">
    {'<div id="gq-chat-nokey">&#128274; Enter your OpenAI API key in the sidebar.</div>' if not _api_ok else ''}
  </div>
</div>
""", unsafe_allow_html=True)

# Attach click handlers via iframe (Streamlit CSP blocks inline onclick attrs)
# Panel open/close state is stored in sessionStorage so it survives Streamlit reruns.
st.html("""
<script>
(function attach() {
  var fab = document.getElementById('gq-fab');
  var panel = document.getElementById('gq-chat-panel');
  var closeBtn = document.getElementById('gq-chat-close');
  var body = document.getElementById('gq-chat-body');
  if (!fab || !panel) { setTimeout(attach, 100); return; }

  // Restore open state from sessionStorage (survives Streamlit reruns)
  if (sessionStorage.getItem('gq_chat_open') === '1') {
    panel.classList.add('gqcp-open');
    fab.innerHTML = '&#10005;';
    if (body) body.scrollTop = body.scrollHeight;
  }

  fab.onclick = function() {
    var open = panel.classList.toggle('gqcp-open');
    fab.innerHTML = open ? '&#10005;' : '&#128172;';
    sessionStorage.setItem('gq_chat_open', open ? '1' : '0');
    if (open && body) body.scrollTop = body.scrollHeight;
  };
  if (closeBtn) {
    closeBtn.onclick = function() {
      panel.classList.remove('gqcp-open');
      fab.innerHTML = '&#128172;';
      sessionStorage.setItem('gq_chat_open', '0');
    };
  }
  if (body) body.scrollTop = body.scrollHeight;
})();
</script>
""", unsafe_allow_javascript=True)

if _api_ok:
    _q = st.chat_input('Ask about gaskets…', key='float_chat')
    if _q:
        st.session_state.chat_messages.append({'role': 'user', 'content': _q})
        st.session_state.chat_loading = True
        st.rerun()

if st.session_state.get('chat_loading'):
    try:
        from openai import OpenAI as _OAI
        _cl = _OAI(api_key=_os.environ['OPENAI_API_KEY'])
        _sys = (
            'You are a concise technical expert on industrial gaskets for Goodrich Gasket Pvt. Ltd. '
            'Specialise in: soft cut (CNAF, PTFE, Neoprene, Graphite, Klingersil), spiral wound, RTJ, '
            'Kammprofile, DJI, ISK. Topics: material selection, pressure ratings (ASME 150#-2500#, PN6-PN400), '
            'standards (ASME B16.21/B16.20/B16.47, EN 1514-1), dimensions, application suitability. '
            'Keep replies short and technical. Politely decline non-gasket topics.'
        )
        _hx = [{'role': 'system', 'content': _sys}]
        _hx += [{'role': m['role'], 'content': m['content']} for m in st.session_state.chat_messages]
        _r = _cl.chat.completions.create(
            model='gpt-4o-mini', messages=_hx, temperature=0.2, max_tokens=350,
        )
        st.session_state.chat_messages.append(
            {'role': 'assistant', 'content': _r.choices[0].message.content.strip()}
        )
    except Exception as _e:
        st.session_state.chat_messages.append(
            {'role': 'assistant', 'content': f'Error: {_e}', 'error': True}
        )
    finally:
        st.session_state.chat_loading = False
    st.rerun()
