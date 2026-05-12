import datetime as _dt
import os as _os

import streamlit as st

from ui.history import _history_pdf_bytes, _restore_history_entry, _save_history_local


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar():
    with st.sidebar:
        # -- Compact status strip --------------------------------------------------
        from services import storage as _storage_status
        _ai_on = bool(_os.environ.get('OPENAI_API_KEY'))
        _db_on = _storage_status.is_connected()
        _ai_color = '#22c55e' if _ai_on else '#ef4444'
        _db_color = '#22c55e' if _db_on else '#f59e0b'
        _ai_txt = 'AI on' if _ai_on else 'Rule-based'
        _db_txt = 'Cloud' if _db_on else 'Local'
        st.markdown(
            '<div class="gq-status-strip">'
            f'<span style="color:{_ai_color};font-size:0.7rem">&#x25cf;</span> <span>{_ai_txt}</span>'
            '<span style="margin:0 0.5rem;opacity:0.3">|</span>'
            f'<span style="color:{_db_color};font-size:0.7rem">&#x25cf;</span> <span>{_db_txt}</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        if not _ai_on:
            api_key_input = st.text_input(
                'OpenAI API Key', type='password', placeholder='sk-...', label_visibility='collapsed',
                help='Paste your key to enable AI extraction',
            )
            if api_key_input:
                clean_key = api_key_input.encode('ascii', errors='ignore').decode('ascii').strip()
                _os.environ['OPENAI_API_KEY'] = clean_key
                st.rerun()

        # Doc Assistant link (compact)
        st.markdown(
            '<a href="/Doc_Assistant" target="_blank" style="'
            'display:flex;align-items:center;gap:0.4rem;'
            'background:#2e4470;color:#e8ecf1 !important;text-decoration:none;'
            'border:1px solid #3d5a8a;border-radius:6px;'
            'padding:0.35rem 0.75rem;font-size:0.8rem;font-weight:500;'
            'margin:0.5rem 0;width:100%;box-sizing:border-box;"'
            ' onmouseover="this.style.background=\'#3d5a8a\'"'
            ' onmouseout="this.style.background=\'#2e4470\'">'
            '&#128196;&nbsp; Doc Assistant&nbsp;<span style="opacity:0.6;font-size:0.75rem">&#8599;</span>'
            '</a>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr style="margin:0.5rem 0;border-color:#2e4470">', unsafe_allow_html=True)

        # -- Quote History ---------------------------------------------------------
        st.markdown('<div class="gq-sidebar-title" style="margin-bottom:0.3rem">Quote History</div>',
                    unsafe_allow_html=True)

        history = st.session_state.run_history
        if not history:
            st.markdown('<p style="font-size:0.8rem;opacity:0.5;margin:0.4rem 0">No quotes saved yet.</p>',
                        unsafe_allow_html=True)
        else:
            import datetime as _dt

            def _age_group(ts: str) -> str:
                if not ts:
                    return 'Older'
                try:
                    d = _dt.date.fromisoformat(ts[:10])
                except Exception:
                    return 'Older'
                today = _dt.date.today()
                delta = (today - d).days
                if delta == 0:
                    return 'Today'
                if delta == 1:
                    return 'Yesterday'
                if delta <= 7:
                    return 'Last 7 days'
                if delta <= 30:
                    return 'Last 30 days'
                return d.strftime('%B %Y')

            # Group runs by age
            _groups: dict[str, list] = {}
            _group_order: list[str] = []
            for _run in history:
                _g = _age_group(_run.get('timestamp', ''))
                if _g not in _groups:
                    _groups[_g] = []
                    _group_order.append(_g)
                _groups[_g].append(_run)

            _sel = st.session_state.get('_hist_selected')

            for _grp in _group_order:
                st.markdown(f'<div class="gq-hist-group">{_grp}</div>', unsafe_allow_html=True)
                for _run in _groups[_grp]:
                    _run_idx = history.index(_run)
                    _pdf_ready = _run.get('pdf_ready', True)
                    _label = (_run.get('custom_label') or _run.get('quote_no') or
                              _run.get('customer') or _run.get('project_ref') or
                              f'Enquiry {_run_idx + 1}')
                    _is_sel = _sel == _run_idx
                    _arrow = '▾' if _is_sel else '▸'
                    _dot = ' ·' if not _pdf_ready else ''
                    if st.button(
                        f'{_arrow} {_label}{_dot}',
                        key=f'hist_row_{_run_idx}',
                        help='Click to expand' if not _is_sel else 'Click to collapse',
                        use_container_width=True,
                    ):
                        st.session_state._hist_selected = None if _is_sel else _run_idx
                        st.rerun()

                    if _is_sel:
                        _n_regret_h = _run.get('n_regret', 0)
                        _pdf_status = 'Enquiry saved - quotation not prepared' if not _pdf_ready else ''
                        _cust = _run.get('customer') or 'No customer'
                        _proj = _run.get('project_ref') or ''
                        _proj_html = f' | {_proj}' if _proj else ''
                        _status_html = (f'<div class="gq-hist-meta" style="opacity:0.7">{_pdf_status}</div>'
                                        if _pdf_status else '')
                        _regret_html = (f'<span class="gq-pill gq-pill-regret">Regret: {_n_regret_h}</span>'
                                        if _n_regret_h else '')
                        st.markdown(
                            f'<div class="gq-hist-detail">'
                            f'<div class="gq-hist-meta">{_run.get("timestamp", "")}</div>'
                            f'<div class="gq-hist-meta">{_cust}{_proj_html}</div>'
                            f'{_status_html}'
                            f'<div class="gq-hist-pills">'
                            f'<span class="gq-pill gq-pill-ready">Ready: {_run.get("n_ready", 0)}</span>'
                            f'<span class="gq-pill gq-pill-check">Check: {_run.get("n_check", 0)}</span>'
                            f'<span class="gq-pill gq-pill-missing">Missing: {_run.get("n_missing", 0)}</span>'
                            f'{_regret_html}'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )
                        _rename_cols = st.columns([4, 1])
                        _new_name = _rename_cols[0].text_input(
                            'Rename', value=_run.get('custom_label') or '',
                            placeholder=_label,
                            key=f'rename_input_{_run_idx}',
                            label_visibility='collapsed',
                        )
                        if _rename_cols[1].button('✓', key=f'rename_btn_{_run_idx}', help='Save name'):
                            _run['custom_label'] = _new_name.strip() or ''
                            from services import storage as _storage_rename
                            _storage_rename.save_quote(_run)
                            _save_history_local()
                            st.rerun()
                        _d1, _d2 = st.columns(2)
                        if _d1.button('Restore', key=f'restore_{_run_idx}'):
                            _restore_history_entry(_run)
                            st.session_state._hist_selected = None
                            st.rerun()
                        if _d2.button('Quote Form', key=f'quote_form_{_run_idx}'):
                            _restore_history_entry(_run)
                            st.session_state._show_quote_page = True
                            st.session_state._hist_selected = None
                            st.rerun()
                        _pdf_bytes = _history_pdf_bytes(_run)
                        if _pdf_bytes:
                            st.download_button(
                                'Download PDF',
                                data=_pdf_bytes,
                                file_name=_run.get('quote_pdf_name') or 'quotation.pdf',
                                mime='application/pdf',
                                key=f'hist_pdf_{_run_idx}',
                                use_container_width=True,
                            )
                        if st.button('Delete', key=f'delete_{_run_idx}', type='secondary', use_container_width=True):
                            from services import storage as _storage
                            _supabase_id = _run.get('supabase_id')
                            if _supabase_id:
                                _storage.delete_quote(_supabase_id)
                            st.session_state.run_history.pop(_run_idx)
                            if _run is st.session_state.get('_active_hist_entry'):
                                st.session_state.pop('_active_hist_entry', None)
                            st.session_state._hist_selected = None
                            _save_history_local()
                            st.rerun()


