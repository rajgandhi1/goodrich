"""Shared bootstrap for every Streamlit page in this app.

Loads .env, copies Streamlit secrets into os.environ, sanitises the API key,
and seeds session_state defaults that the rest of the app expects.
"""
from __future__ import annotations

import os as _os

import streamlit as st

# ---- Env / secrets ---------------------------------------------------------
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except ImportError:
    pass

try:
    for _k in ('OPENAI_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY'):
        if not _os.environ.get(_k):
            _v = str(st.secrets.get(_k, '') or '').strip()
            if _v:
                _os.environ[_k] = _v
except Exception:
    pass

_raw_key = _os.environ.get('OPENAI_API_KEY', '')
if _raw_key:
    _clean = _raw_key.encode('ascii', errors='ignore').decode('ascii').strip()
    if _clean != _raw_key:
        _os.environ['OPENAI_API_KEY'] = _clean


_DEFAULTS: dict = {
    'working_items':      [],
    '_selected_rows':     set(),
    'filter_mode':        'All',
    'run_history':        [],
    '_history_loaded':    False,
    '_hist_selected':     None,
    '_show_confirm':      False,
    '_show_quote_page':   False,
    '_quote_data':        {},
    '_quote_excel':       None,
    '_input_reset_seq':   0,
    'chat_messages':      [],
    'chat_open':          False,
    'chat_loading':       False,
}


def init_session_state() -> None:
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v
