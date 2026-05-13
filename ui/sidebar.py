"""Top navigation bar — replaces the old sidebar."""
from __future__ import annotations

import os as _os

import streamlit as st

from ui.history import _save_history_local


def _status_html() -> str:
    """Return HTML for the AI + Cloud status dots."""
    from services import storage as _storage
    ai_on = bool(_os.environ.get('OPENAI_API_KEY'))
    db_on = _storage.is_connected()

    ai_dot   = 'gq-dot-green' if ai_on else 'gq-dot-red'
    db_dot   = 'gq-dot-green' if db_on else 'gq-dot-amber'
    ai_label = 'AI ready' if ai_on else 'No API key'
    db_label = 'Cloud connected' if db_on else 'Local only'

    return (
        f'<span class="gq-topbar-dot">'
        f'<span class="gq-dot {ai_dot}"></span> {ai_label}</span>'
        f'<span style="opacity:0.3">|</span>'
        f'<span class="gq-topbar-dot">'
        f'<span class="gq-dot {db_dot}"></span> {db_label}</span>'
    )


def render_topbar(show_home: bool = True) -> None:
    """Compact top bar with optional back-to-dashboard button and status dots."""
    left, right = st.columns([1, 3])

    with left:
        if show_home:
            if st.button('← Dashboard', key='topbar_home', help='Return to the pipeline dashboard'):
                st.switch_page('app.py')

    with right:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:flex-end;'
            f'gap:1rem;font-size:0.78rem;color:#555;padding-top:0.4rem">'
            f'{_status_html()}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # API key banner — shown only when key is missing
    if not _os.environ.get('OPENAI_API_KEY'):
        with st.expander('⚠️ OpenAI API key required for AI extraction', expanded=False):
            col1, col2 = st.columns([4, 1])
            key_input = col1.text_input(
                'API Key', type='password', placeholder='sk-...',
                label_visibility='collapsed',
                key='topbar_api_key',
            )
            if col2.button('Save', key='topbar_api_key_save'):
                clean = key_input.encode('ascii', errors='ignore').decode('ascii').strip()
                if clean:
                    _os.environ['OPENAI_API_KEY'] = clean
                    st.rerun()


def render_sidebar() -> None:
    """Legacy shim — calls render_topbar so existing imports still work."""
    render_topbar()
