import base64
import datetime as _dt
import json as _json
from pathlib import Path

import streamlit as st

from core.rules import STATUS_READY, STATUS_CHECK, STATUS_MISSING, STATUS_REGRET

_HISTORY_PATH = Path(__file__).resolve().parents[1] / 'data' / 'quote_history.json'
_HISTORY_LIMIT = 100


def load_history():
    """Load quote history once per Streamlit session."""
    if st.session_state._history_loaded:
        return

    from services import storage as _storage

    loaded_history = None
    if _storage.is_connected():
        try:
            loaded_history = _storage.load_quotes(limit=_HISTORY_LIMIT)
        except Exception:
            loaded_history = None

    if not loaded_history and _HISTORY_PATH.exists():
        try:
            loaded_history = _json.loads(_HISTORY_PATH.read_text(encoding='utf-8'))
        except Exception:
            loaded_history = None

    if isinstance(loaded_history, list):
        st.session_state.run_history = loaded_history
    st.session_state._history_loaded = True


def _save_history_local(entry: dict | None = None):
    """Write full history list to local JSON (local dev fallback)."""
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_PATH.write_text(
            _json.dumps(st.session_state.run_history[-_HISTORY_LIMIT:]),
            encoding='utf-8',
        )
    except Exception:
        pass


def _make_history_entry(items, quote_data=None, quote_pdf=None):
    quote_data = dict(quote_data or {})
    n_ready   = sum(1 for i in items if i.get('status') == STATUS_READY)
    n_check   = sum(1 for i in items if i.get('status') == STATUS_CHECK)
    n_missing = sum(1 for i in items if i.get('status') == STATUS_MISSING)
    n_regret  = sum(1 for i in items if i.get('status') == STATUS_REGRET)
    customer_val = quote_data.get('buyer_name_address', '').split('\n')[0] or ''
    project_val = quote_data.get('customer_enq_no', '')
    quote_no = quote_data.get('quote_no', '')
    entry = {
        'timestamp': _dt.datetime.now().strftime('%d %b %Y %H:%M'),
        'customer': customer_val,
        'project_ref': project_val,
        'quote_no': quote_no,
        'quote_data': quote_data,
        'n_items': len(items),
        'n_ready': n_ready,
        'n_check': n_check,
        'n_missing': n_missing,
        'n_regret': n_regret,
        'items': [dict(i) for i in items],
    }
    if quote_pdf:
        entry['quote_pdf_b64'] = base64.b64encode(quote_pdf).decode('ascii')
        entry['quote_pdf_name'] = f"{(quote_no or 'quotation').replace('/', '-')}.pdf"
    return entry


def _append_history(entry):
    from services import storage as _storage
    # If there's a pending extraction entry for this session, update it instead of inserting.
    active = st.session_state.get('_active_hist_entry')
    if active is not None and active in st.session_state.run_history:
        active.update(entry)
        active['pdf_ready'] = True
        uid = _storage.save_quote(active)
        if uid:
            active['supabase_id'] = uid
        else:
            _save_history_local()
        st.session_state.pop('_active_hist_entry', None)
        return
    # No pending entry - fresh insert.
    uid = _storage.save_quote(entry)
    if uid:
        entry['supabase_id'] = uid
    else:
        _save_history_local()
    st.session_state.run_history.insert(0, entry)
    st.session_state.run_history = st.session_state.run_history[:_HISTORY_LIMIT]


def _save_extraction_history():
    """Save a history entry immediately after LLM extraction (no PDF yet)."""
    items = st.session_state.working_items
    if not items:
        return
    entry = _make_history_entry(items, st.session_state.get('_quote_data') or {}, quote_pdf=None)
    entry['pdf_ready'] = False
    from services import storage as _storage
    uid = _storage.save_quote(entry)
    if uid:
        entry['supabase_id'] = uid
    else:
        _save_history_local()
    st.session_state.run_history.insert(0, entry)
    st.session_state.run_history = st.session_state.run_history[:_HISTORY_LIMIT]
    # Keep a reference so _append_history can update this entry when PDF is ready.
    st.session_state._active_hist_entry = entry


def _restore_history_entry(run):
    st.session_state.working_items = [dict(i) for i in run.get('items', [])]
    st.session_state._quote_data = dict(run.get('quote_data') or {})
    st.session_state._quote_excel = None
    st.session_state._selected_rows = set()
    st.session_state.pop('_bulk_df', None)
    st.session_state.pop('_last_excel', None)
    st.session_state.filter_mode = 'All'
    st.session_state._show_confirm = False
    st.session_state._show_quote_page = False


def _history_pdf_bytes(run):
    pdf_b64 = run.get('quote_pdf_b64')
    if not pdf_b64:
        return None
    try:
        return base64.b64decode(pdf_b64)
    except Exception:
        return None
