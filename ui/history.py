from __future__ import annotations

import base64
import datetime as _dt
import json as _json
from pathlib import Path

import streamlit as st

from core.rules import STATUS_READY, STATUS_CHECK, STATUS_MISSING, STATUS_REGRET

_HISTORY_PATH = Path(__file__).resolve().parents[1] / 'data' / 'quote_history.json'
_HISTORY_LIMIT = 100

# Pipeline stages (ordered). Earlier stages auto-advance from app actions;
# later stages must be set manually from the dashboard.
STAGES = ['initial', 'review', 'quote_prep', 'repricing', 'sent', 'po']
STAGE_LABELS = {
    'initial':    'Initial Processing',
    'review':     'Under Review',
    'quote_prep': 'Quote Preparation',
    'repricing':  'Repricing',
    'sent':       'Sent to Customer',
    'po':         'Converted to PO',
}
AUTO_STAGES = {'initial', 'review', 'quote_prep'}


def _stage_rank(stage: str) -> int:
    try:
        return STAGES.index(stage)
    except ValueError:
        return 0


def advance_stage(entry: dict, new_stage: str, *, force: bool = False, meta: dict | None = None) -> bool:
    """Move entry to ``new_stage``. By default never moves backwards.

    Returns True if the stage actually changed (and was persisted).
    """
    if new_stage not in STAGES:
        return False
    current = entry.get('stage') or 'initial'
    if not force and _stage_rank(new_stage) <= _stage_rank(current):
        # Still record meta updates if provided (e.g. PO no after the stage was already set)
        if meta:
            entry.setdefault('stage_meta', {}).update(meta)
            _persist_entry(entry)
        return False
    entry['stage'] = new_stage
    history = entry.setdefault('stage_history', [])
    history.append({'stage': new_stage, 'at': _dt.datetime.now().strftime('%d %b %Y %H:%M')})
    if meta:
        entry.setdefault('stage_meta', {}).update(meta)
    _persist_entry(entry)
    return True


def _persist_entry(entry: dict) -> None:
    """Save a single entry to Supabase if connected, otherwise to the local JSON."""
    from services import storage as _storage
    try:
        uid = _storage.save_quote(entry)
    except Exception as exc:
        st.toast(f'Database save failed — {exc}', icon='🚨')
        _save_history_local()
        return
    if uid:
        entry['supabase_id'] = uid
    else:
        _save_history_local()


# ---------------------------------------------------------------------------
# Time-in-stage helpers
# ---------------------------------------------------------------------------

_TS_FMT = '%d %b %Y %H:%M'


def _parse_stage_ts(s: str) -> _dt.datetime | None:
    if not s:
        return None
    try:
        return _dt.datetime.strptime(s, _TS_FMT)
    except (ValueError, TypeError):
        return None


def stage_durations(entry: dict) -> dict[str, _dt.timedelta]:
    """Time spent IN each stage (delta between consecutive stage_history entries).

    The current stage's duration is measured up to "now".
    """
    out: dict[str, _dt.timedelta] = {}
    history = entry.get('stage_history') or []
    if not history:
        return out
    parsed = [(h.get('stage'), _parse_stage_ts(h.get('at'))) for h in history]
    parsed = [(s, t) for s, t in parsed if s and t]
    if not parsed:
        return out
    for i, (stage, ts) in enumerate(parsed):
        end = parsed[i + 1][1] if i + 1 < len(parsed) else _dt.datetime.now()
        out[stage] = out.get(stage, _dt.timedelta(0)) + (end - ts)
    return out


def time_to_sent_days(entry: dict) -> float | None:
    """Days from the first stage_history entry to the first 'sent' entry."""
    history = entry.get('stage_history') or []
    parsed = [(h.get('stage'), _parse_stage_ts(h.get('at'))) for h in history]
    parsed = [(s, t) for s, t in parsed if s and t]
    if not parsed:
        return None
    first_ts = parsed[0][1]
    sent_ts = next((t for s, t in parsed if s == 'sent'), None)
    if not sent_ts:
        return None
    return (sent_ts - first_ts).total_seconds() / 86400.0


def current_stage_age_days(entry: dict) -> float | None:
    """Days the entry has been sitting in its current stage."""
    history = entry.get('stage_history') or []
    parsed = [(h.get('stage'), _parse_stage_ts(h.get('at'))) for h in history]
    parsed = [(s, t) for s, t in parsed if s and t]
    if not parsed:
        return None
    last_stage, last_ts = parsed[-1]
    return (_dt.datetime.now() - last_ts).total_seconds() / 86400.0


# ---------------------------------------------------------------------------
# Outcome (Won / Lost) helpers
# ---------------------------------------------------------------------------

def get_outcome(entry: dict) -> str:
    """Return 'won' if PO recorded, otherwise stage_meta.outcome ('lost' / '')."""
    if (entry.get('stage') or 'initial') == 'po':
        return 'won'
    return ((entry.get('stage_meta') or {}).get('outcome') or '').lower()


def set_outcome(entry: dict, outcome: str) -> None:
    """Persist outcome ('lost' or '' to clear) on stage_meta."""
    meta = entry.setdefault('stage_meta', {})
    if outcome:
        meta['outcome'] = outcome
    else:
        meta.pop('outcome', None)
    _persist_entry(entry)


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
        'stage': 'initial',
        'stage_history': [],
        'stage_meta': {},
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
        # Preserve any stage progress already on the active entry; let the new
        # stage default to quote_prep if it's still in an early stage.
        prior_stage = active.get('stage') or 'initial'
        prior_history = active.get('stage_history') or []
        prior_meta = active.get('stage_meta') or {}
        active.update(entry)
        active['pdf_ready'] = True
        active['stage'] = prior_stage
        active['stage_history'] = prior_history
        active['stage_meta'] = prior_meta
        # Generating the PDF means we're past quote prep.
        advance_stage(active, 'quote_prep')
        try:
            uid = _storage.save_quote(active)
        except Exception as exc:
            st.toast(f'Database save failed — {exc}', icon='🚨')
            uid = None
            _save_history_local()
        if uid:
            active['supabase_id'] = uid
        st.session_state.pop('_active_hist_entry', None)
        return
    # No pending entry - fresh insert.
    entry.setdefault('stage', 'quote_prep')
    entry.setdefault('stage_history', [{
        'stage': 'quote_prep',
        'at': _dt.datetime.now().strftime('%d %b %Y %H:%M'),
    }])
    entry.setdefault('stage_meta', {})
    try:
        uid = _storage.save_quote(entry)
    except Exception as exc:
        st.toast(f'Database save failed — {exc}', icon='🚨')
        uid = None
        _save_history_local()
    if uid:
        entry['supabase_id'] = uid
    st.session_state.run_history.insert(0, entry)
    st.session_state.run_history = st.session_state.run_history[:_HISTORY_LIMIT]


def _save_processing_stub(source_label: str = '') -> dict:
    """Create and persist a placeholder entry BEFORE the LLM call starts.

    This makes the enquiry immediately visible on the dashboard even if the user
    navigates away while processing. _save_extraction_history() will update this
    same record with real items once the LLM finishes.
    """
    now = _dt.datetime.now().strftime('%d %b %Y %H:%M')
    entry: dict = {
        'timestamp':     now,
        'customer':      '',
        'project_ref':   '',
        'quote_no':      '',
        'custom_label':  source_label,  # filename (no ext) for files; '' for email
        'quote_data':    {},
        'n_items':       0,
        'n_ready':       0,
        'n_check':       0,
        'n_missing':     0,
        'n_regret':      0,
        'items':         [],
        'stage':         'initial',
        'stage_history': [{'stage': 'initial', 'at': now}],
        'stage_meta':    {},
        'pdf_ready':     False,
        'processing':    True,
    }
    from services import storage as _storage
    try:
        uid = _storage.save_quote(entry)
    except Exception as exc:
        st.toast(f'Database save failed — {exc}', icon='🚨')
        uid = None
        _save_history_local()
    if uid:
        entry['supabase_id'] = uid
    st.session_state.run_history.insert(0, entry)
    st.session_state.run_history = st.session_state.run_history[:_HISTORY_LIMIT]
    # Keep reference so _save_extraction_history() updates this record.
    st.session_state._active_hist_entry = entry
    return entry


def _save_extraction_history():
    """Update the processing stub (or create a fresh entry) after LLM extraction."""
    items = st.session_state.working_items
    if not items:
        return

    # If a processing stub exists for this run, update it in place.
    active = st.session_state.get('_active_hist_entry')
    if active is not None and active in st.session_state.run_history and active.get('processing'):
        prior_stage_history = active.get('stage_history') or []
        prior_supabase_id   = active.get('supabase_id')
        prior_stage         = active.get('stage') or 'initial'
        prior_meta          = active.get('stage_meta') or {}
        active.update(_make_history_entry(items, st.session_state.get('_quote_data') or {}, quote_pdf=None))
        active['pdf_ready']     = False
        active['processing']    = False
        active['stage']         = prior_stage
        active['stage_history'] = prior_stage_history
        active['stage_meta']    = prior_meta
        if prior_supabase_id:
            active['supabase_id'] = prior_supabase_id
        _persist_entry(active)
        return

    # No stub active — create a fresh entry (fallback / manual-add path).
    entry = _make_history_entry(items, st.session_state.get('_quote_data') or {}, quote_pdf=None)
    entry['pdf_ready']  = False
    entry['processing'] = False
    entry['stage_history'] = [{'stage': 'initial', 'at': _dt.datetime.now().strftime('%d %b %Y %H:%M')}]
    from services import storage as _storage
    try:
        uid = _storage.save_quote(entry)
    except Exception as exc:
        st.toast(f'Database save failed — {exc}', icon='🚨')
        uid = None
        _save_history_local()
    if uid:
        entry['supabase_id'] = uid
    st.session_state.run_history.insert(0, entry)
    st.session_state.run_history = st.session_state.run_history[:_HISTORY_LIMIT]
    st.session_state._active_hist_entry = entry


def sync_active_entry_items() -> dict | None:
    """If there's an active history entry for this session, refresh its items
    from session_state.working_items so the dashboard / sidebar match what the
    user is currently editing. Returns the entry (or None)."""
    active = st.session_state.get('_active_hist_entry')
    if active is None or active not in st.session_state.run_history:
        return None
    items = st.session_state.get('working_items') or []
    active['items'] = [dict(i) for i in items]
    active['n_items'] = len(items)
    active['n_ready']   = sum(1 for i in items if i.get('status') == STATUS_READY)
    active['n_check']   = sum(1 for i in items if i.get('status') == STATUS_CHECK)
    active['n_missing'] = sum(1 for i in items if i.get('status') == STATUS_MISSING)
    active['n_regret']  = sum(1 for i in items if i.get('status') == STATUS_REGRET)
    return active


def mark_active_review() -> None:
    """Auto-advance the active session entry to ``review`` after the user edits
    anything in the working list. Idempotent."""
    active = st.session_state.get('_active_hist_entry')
    if active is None or active not in st.session_state.run_history:
        return
    sync_active_entry_items()
    advance_stage(active, 'review')


def mark_active_quote_prep() -> None:
    """Auto-advance the active session entry to ``quote_prep`` when the user
    opens the Quote Form. Idempotent."""
    active = st.session_state.get('_active_hist_entry')
    if active is None or active not in st.session_state.run_history:
        return
    sync_active_entry_items()
    advance_stage(active, 'quote_prep')


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
    # Re-attach this run as the active session entry so further edits flow
    # back into the same history record (and stage updates persist).
    st.session_state._active_hist_entry = run


def _history_pdf_bytes(run):
    pdf_b64 = run.get('quote_pdf_b64')
    if not pdf_b64:
        return None
    try:
        return base64.b64decode(pdf_b64)
    except Exception:
        return None
