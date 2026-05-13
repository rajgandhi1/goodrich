"""Dashboard landing page — pipeline view of quote history."""
from __future__ import annotations

import datetime as _dt
from collections import Counter

import pandas as pd
import streamlit as st

from ui.history import (
    STAGES,
    STAGE_LABELS,
    advance_stage,
    current_stage_age_days,
    get_outcome,
    set_outcome,
    time_to_sent_days,
    _history_pdf_bytes,
    _persist_entry,
    _restore_history_entry,
)


# Stages whose advance needs extra context — show an inline form first.
META_STAGES = {'repricing', 'sent', 'po'}


_STAGE_COLORS = {
    'initial':    ('#eef2fa', '#2e4470'),
    'review':     ('#fff8e6', '#9a6800'),
    'quote_prep': ('#e6efff', '#1d4ed8'),
    'repricing':  ('#ffe9d6', '#b45309'),
    'sent':       ('#e6f4ec', '#1a7a3c'),
    'po':         ('#dbf7e3', '#0f5132'),
}


def _items_processed(history: list[dict]) -> int:
    return sum(int(r.get('n_items') or 0) for r in history)


def _top_gasket_types(history: list[dict], top_n: int = 5) -> list[tuple[str, int]]:
    c: Counter = Counter()
    for run in history:
        for item in run.get('items') or []:
            t = (item.get('gasket_type') or 'UNKNOWN').upper()
            c[t] += 1
    return c.most_common(top_n)


def _stage_count(history: list[dict], stage: str) -> int:
    return sum(1 for r in history if (r.get('stage') or 'initial') == stage)


def _conversion_rate(history: list[dict]) -> float:
    """% of quotes that reached `sent` or `po` (excluding lost)."""
    if not history:
        return 0.0
    closed = sum(1 for r in history
                 if (r.get('stage') or 'initial') in ('sent', 'po')
                 and get_outcome(r) != 'lost')
    return 100.0 * closed / len(history)


def _win_rate(history: list[dict]) -> float | None:
    """Wins / (Wins + Losses) among quotes that reached the customer."""
    decided = [r for r in history if get_outcome(r) in ('won', 'lost')]
    if not decided:
        return None
    wins = sum(1 for r in decided if get_outcome(r) == 'won')
    return 100.0 * wins / len(decided)


def _avg_time_to_sent(history: list[dict]) -> float | None:
    deltas = [d for d in (time_to_sent_days(r) for r in history) if d is not None]
    return sum(deltas) / len(deltas) if deltas else None


def _label_for(run: dict) -> str:
    if run.get('custom_label'):
        return run['custom_label']
    parts = []
    if run.get('quote_no'):
        parts.append(run['quote_no'])
    if run.get('customer'):
        parts.append(run['customer'])
    if run.get('project_ref'):
        parts.append(run['project_ref'])
    if parts:
        return ' — '.join(parts)
    ts = run.get('timestamp', '')
    return f"Enquiry — {ts}" if ts else "New Enquiry"


def _render_metric_row(history: list[dict]) -> None:
    total_quotes = len(history)
    items_done   = _items_processed(history)
    pending      = sum(1 for r in history if (r.get('stage') or 'initial') in ('initial', 'review'))
    conv         = _conversion_rate(history)
    po_count     = _stage_count(history, 'po')
    win_rate     = _win_rate(history)
    avg_tts      = _avg_time_to_sent(history)

    win_html = f'{win_rate:.0f}%' if win_rate is not None else '—'
    tts_html = f'{avg_tts:.1f}d' if avg_tts is not None else '—'

    st.markdown(f"""
    <div class="gq-metrics">
      <div class="gq-metric gq-total">
        <div class="val">{total_quotes}</div>
        <div class="lbl">Total Quotes</div>
      </div>
      <div class="gq-metric gq-ready">
        <div class="val">{items_done}</div>
        <div class="lbl">Items Processed</div>
      </div>
      <div class="gq-metric gq-check">
        <div class="val">{pending}</div>
        <div class="lbl">Pending Review</div>
      </div>
      <div class="gq-metric gq-total">
        <div class="val">{conv:.0f}%</div>
        <div class="lbl">Conversion Rate</div>
      </div>
      <div class="gq-metric gq-ready">
        <div class="val">{po_count}</div>
        <div class="lbl">Converted to PO</div>
      </div>
      <div class="gq-metric gq-check">
        <div class="val">{win_html}</div>
        <div class="lbl">Win Rate</div>
      </div>
      <div class="gq-metric gq-total">
        <div class="val">{tts_html}</div>
        <div class="lbl">Avg Days → Sent</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _render_top_types(history: list[dict]) -> None:
    top = _top_gasket_types(history)
    if not top:
        return
    st.markdown('#### Top Gasket Types Processed')
    df = pd.DataFrame(top, columns=['Gasket Type', 'Items'])
    chart_col, table_col = st.columns([3, 2])
    with chart_col:
        st.bar_chart(df.set_index('Gasket Type'), height=240)
    with table_col:
        st.dataframe(df, hide_index=True, use_container_width=True, height=240)


def _render_pipeline(history: list[dict]) -> None:
    st.markdown('#### Pipeline')
    st.caption('Stages auto-advance through Initial → Review → Quote Prep. '
               'Move forward to Repricing, Sent, or PO from each card.')
    cols = st.columns(len(STAGES))
    for col, stage in zip(cols, STAGES):
        bg, fg = _STAGE_COLORS[stage]
        runs_in_stage = [r for r in history if (r.get('stage') or 'initial') == stage]
        col.markdown(
            f'<div style="background:{bg};color:{fg};padding:0.5rem 0.7rem;'
            f'border-radius:8px;text-align:center;font-weight:600;'
            f'margin-bottom:0.4rem;">'
            f'<div style="font-size:0.72rem;letter-spacing:0.4px;text-transform:uppercase;opacity:0.85">{STAGE_LABELS[stage]}</div>'
            f'<div style="font-size:1.4rem;line-height:1.1">{len(runs_in_stage)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        with col:
            for run in runs_in_stage[:6]:
                _render_pipeline_card(run, stage)
            if len(runs_in_stage) > 6:
                col.caption(f'+ {len(runs_in_stage) - 6} more — see History below')


def _render_pipeline_card(run: dict, stage: str) -> None:
    label = _label_for(run)
    cust = run.get('customer') or run.get('project_ref') or '—'
    ts = run.get('timestamp') or ''
    st.markdown(
        f'<div style="background:#1e2d48;border-radius:6px;padding:0.4rem 0.5rem;'
        f'margin-bottom:0.35rem;font-size:0.74rem;color:#e8ecf1">'
        f'<div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{label}</div>'
        f'<div style="opacity:0.65;font-size:0.7rem">{cust}</div>'
        f'<div style="opacity:0.5;font-size:0.68rem">{ts} · '
        f'{"⏳ processing" if run.get("processing") else str(run.get("n_items", 0)) + " items"}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_history_table(history: list[dict]) -> None:
    st.markdown('#### History')
    if not history:
        st.info('No quotes yet — head to the Quote Workspace to create one.')
        return

    f1, f2, f3 = st.columns([2, 3, 5])
    stage_filter = f1.selectbox(
        'Stage', ['All'] + [STAGE_LABELS[s] for s in STAGES],
        key='dash_stage_filter',
    )
    text_filter = f2.text_input('Search', placeholder='customer / quote no / project ref',
                                key='dash_text_filter').strip().lower()

    if stage_filter == 'All':
        stage_key = None
    else:
        stage_key = next(s for s, lbl in STAGE_LABELS.items() if lbl == stage_filter)

    filtered: list[tuple[int, dict]] = []
    for idx, run in enumerate(history):
        if stage_key and (run.get('stage') or 'initial') != stage_key:
            continue
        if text_filter:
            hay = ' '.join(str(run.get(k) or '') for k in
                           ('customer', 'project_ref', 'quote_no', 'custom_label')).lower()
            if text_filter not in hay:
                continue
        filtered.append((idx, run))

    if not filtered:
        st.caption('No quotes match these filters.')
        return

    for idx, run in filtered:
        _render_history_row(idx, run)


def _render_history_row(idx: int, run: dict) -> None:
    stage = run.get('stage') or 'initial'
    bg, fg = _STAGE_COLORS[stage]
    label = _label_for(run)
    cust = run.get('customer') or '—'
    proj = run.get('project_ref') or ''
    ts = run.get('timestamp') or ''
    n_items = run.get('n_items') or 0
    n_ready = run.get('n_ready') or 0
    n_check = run.get('n_check') or 0
    n_missing = run.get('n_missing') or 0
    outcome = get_outcome(run)
    age = current_stage_age_days(run)

    renaming = st.session_state.get(f'_renaming_{idx}', False)
    with st.container():
        cols = st.columns([3, 3, 1.4, 2, 2])
        with cols[0]:
            lc, ec = st.columns([5, 1])
            lc.markdown(
                f'**{label}**  \n<span style="font-size:0.75rem;opacity:0.7">{cust}'
                f'{" · " + proj if proj else ""}</span>',
                unsafe_allow_html=True,
            )
            if ec.button('✏', key=f'dash_rename_btn_{idx}',
                         help='Rename this enquiry', use_container_width=True):
                st.session_state[f'_renaming_{idx}'] = not renaming
                st.rerun()
        age_html = ''
        if age is not None:
            age_color = '#b91c1c' if age >= 7 else ('#9a6800' if age >= 3 else '#5a7aab')
            age_html = (f' · <span style="color:{age_color}">'
                        f'{_format_age(age)} in stage</span>')
        if run.get('processing'):
            items_html = '<span style="color:#9a6800">⏳ Processing…</span>'
        else:
            items_html = (
                f'<b>{n_items}</b> items · '
                f'<span style="color:#1a7a3c">✓{n_ready}</span> '
                f'<span style="color:#9a6800">!{n_check}</span> '
                f'<span style="color:#b91c1c">×{n_missing}</span>'
            )
        cols[1].markdown(
            f'<span style="font-size:0.75rem;opacity:0.7">{ts}{age_html}</span>  \n'
            f'<span style="font-size:0.72rem">{items_html}</span>',
            unsafe_allow_html=True,
        )
        outcome_pill = ''
        if outcome == 'won':
            outcome_pill = ('<span style="background:#dbf7e3;color:#0f5132;padding:2px 8px;'
                            'border-radius:12px;font-size:0.65rem;font-weight:700;'
                            'margin-left:4px">WON</span>')
        elif outcome == 'lost':
            outcome_pill = ('<span style="background:#fde2e2;color:#991b1b;padding:2px 8px;'
                            'border-radius:12px;font-size:0.65rem;font-weight:700;'
                            'margin-left:4px">LOST</span>')
        cols[2].markdown(
            f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:12px;'
            f'font-size:0.7rem;font-weight:600">{STAGE_LABELS[stage]}</span>{outcome_pill}',
            unsafe_allow_html=True,
        )

        with cols[3]:
            stage_options = [STAGE_LABELS[s] for s in STAGES]
            current_label = STAGE_LABELS[stage]
            new_label = st.selectbox(
                'Set stage', stage_options,
                index=stage_options.index(current_label),
                key=f'dash_set_stage_{idx}',
                label_visibility='collapsed',
            )
            if new_label != current_label:
                new_stage = next(s for s, lbl in STAGE_LABELS.items() if lbl == new_label)
                if new_stage in META_STAGES:
                    # Defer the advance — show a form below and let the user fill in.
                    st.session_state[f'_pending_stage_{idx}'] = new_stage
                    st.rerun()
                else:
                    advance_stage(run, new_stage, force=True)
                    st.rerun()

        with cols[4]:
            b1, b2, b3 = st.columns(3)
            if b1.button('Open', key=f'dash_open_{idx}', use_container_width=True):
                _restore_history_entry(run)
                if _has_workspace_page():
                    st.switch_page('pages/2_Quote_Workspace.py')
                else:
                    st.rerun()
            pdf_bytes = _history_pdf_bytes(run)
            if pdf_bytes:
                b2.download_button(
                    'PDF',
                    data=pdf_bytes,
                    file_name=run.get('quote_pdf_name') or 'quotation.pdf',
                    mime='application/pdf',
                    key=f'dash_pdf_{idx}',
                    use_container_width=True,
                )
            del_confirmed = st.session_state.get(f'_del_confirm_{idx}', False)
            if not del_confirmed:
                if b3.button('🗑', key=f'dash_del_{idx}', use_container_width=True,
                             help='Delete this enquiry'):
                    st.session_state[f'_del_confirm_{idx}'] = True
                    st.rerun()
            else:
                if b3.button('Confirm?', key=f'dash_del_confirm_{idx}',
                             use_container_width=True, type='primary',
                             help='Click again to permanently delete'):
                    _delete_history_entry(idx, run)
                    st.rerun()

        # Inline rename form
        if renaming:
            rc1, rc2, rc3, _ = st.columns([4, 1, 1, 4])
            new_name = rc1.text_input(
                'Name', value=run.get('custom_label') or '',
                placeholder='e.g. NRL Enquiry May 2026',
                key=f'dash_rename_input_{idx}',
                label_visibility='collapsed',
            )
            if rc2.button('Save', key=f'dash_rename_save_{idx}', type='primary',
                          use_container_width=True):
                run['custom_label'] = new_name.strip()
                _persist_entry(run)
                st.session_state.pop(f'_renaming_{idx}', None)
                st.rerun()
            if rc3.button('Cancel', key=f'dash_rename_cancel_{idx}',
                          use_container_width=True):
                st.session_state.pop(f'_renaming_{idx}', None)
                st.rerun()

        # Won / Lost controls — only meaningful at the 'sent' stage.
        if stage == 'sent':
            wl_cols = st.columns([1, 1, 8])
            if outcome != 'won' and wl_cols[0].button(
                '✓ Won', key=f'dash_won_{idx}', use_container_width=True,
                help='Move to Converted to PO',
            ):
                st.session_state[f'_pending_stage_{idx}'] = 'po'
                st.rerun()
            if outcome != 'lost' and wl_cols[1].button(
                '✗ Lost', key=f'dash_lost_{idx}', use_container_width=True,
                help='Mark as lost — quote stays in Sent stage',
            ):
                set_outcome(run, 'lost')
                st.rerun()
            if outcome == 'lost' and wl_cols[1].button(
                '↺ Reopen', key=f'dash_reopen_{idx}', use_container_width=True,
                help='Clear the Lost flag',
            ):
                set_outcome(run, '')
                st.rerun()

        # Pending stage form (deferred advance for sent / po / repricing).
        pending = st.session_state.get(f'_pending_stage_{idx}')
        if pending:
            _render_pending_stage_form(idx, run, pending)

        # Meta summary line
        meta = run.get('stage_meta') or {}
        meta_bits: list[str] = []
        if meta.get('po_no'):         meta_bits.append(f'PO: {meta["po_no"]}')
        if meta.get('po_value'):      meta_bits.append(f'₹{meta["po_value"]}')
        if meta.get('sent_to'):       meta_bits.append(f'Sent to: {meta["sent_to"]}')
        if meta.get('sent_at'):       meta_bits.append(f'on {meta["sent_at"]}')
        if meta.get('reprice_note'):  meta_bits.append(f'Reprice: {meta["reprice_note"]}')
        if meta_bits:
            st.markdown(
                f'<div style="font-size:0.72rem;opacity:0.65;padding-left:0.2rem">'
                f'{" · ".join(meta_bits)}</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<hr style="margin:0.4rem 0;border-color:#2e4470;opacity:0.5">',
                    unsafe_allow_html=True)


def _render_pending_stage_form(idx: int, run: dict, new_stage: str) -> None:
    """Inline form to capture context before advancing to repricing/sent/po."""
    label = STAGE_LABELS[new_stage]
    existing = run.get('stage_meta') or {}
    today = _dt.date.today().isoformat()
    with st.form(key=f'dash_meta_form_{idx}_{new_stage}', clear_on_submit=False):
        st.markdown(f'**Advance to {label}** — capture context, then save.')
        meta: dict = {}
        if new_stage == 'sent':
            c1, c2 = st.columns(2)
            meta['sent_to'] = c1.text_input(
                'Recipient email', value=existing.get('sent_to', ''),
                placeholder='buyer@example.com',
                key=f'meta_sent_to_{idx}',
            )
            meta['sent_at'] = c2.text_input(
                'Date sent', value=existing.get('sent_at', today),
                key=f'meta_sent_at_{idx}',
            )
            meta['sent_note'] = st.text_input(
                'Note (optional)', value=existing.get('sent_note', ''),
                key=f'meta_sent_note_{idx}',
            )
        elif new_stage == 'po':
            c1, c2, c3 = st.columns([2, 2, 2])
            meta['po_no'] = c1.text_input(
                'PO number', value=existing.get('po_no', ''),
                placeholder='e.g. 4500123456',
                key=f'meta_po_no_{idx}',
            )
            meta['po_value'] = c2.text_input(
                'PO value (INR)', value=existing.get('po_value', ''),
                placeholder='e.g. 245000',
                key=f'meta_po_value_{idx}',
            )
            meta['po_date'] = c3.text_input(
                'PO date', value=existing.get('po_date', today),
                key=f'meta_po_date_{idx}',
            )
        elif new_stage == 'repricing':
            meta['reprice_note'] = st.text_input(
                'Reason for repricing',
                value=existing.get('reprice_note', ''),
                placeholder='e.g. customer asked for 5% discount',
                key=f'meta_reprice_note_{idx}',
            )

        save_col, cancel_col, _ = st.columns([1, 1, 4])
        save = save_col.form_submit_button('Save & Advance', type='primary')
        cancel = cancel_col.form_submit_button('Cancel', type='secondary')
        if cancel:
            st.session_state.pop(f'_pending_stage_{idx}', None)
            st.rerun()
        if save:
            # Strip empty values so we don't pollute meta.
            clean_meta = {k: v.strip() for k, v in meta.items() if v and v.strip()}
            advance_stage(run, new_stage, force=True, meta=clean_meta)
            st.session_state.pop(f'_pending_stage_{idx}', None)
            st.rerun()


def _format_age(days: float) -> str:
    if days < 1:
        hrs = max(1, int(days * 24))
        return f'{hrs}h'
    if days < 14:
        return f'{days:.0f}d'
    weeks = days / 7
    return f'{weeks:.0f}w'


def _has_workspace_page() -> bool:
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / 'pages' / '2_Quote_Workspace.py').exists()


def _delete_history_entry(idx: int, run: dict) -> None:
    """Remove entry from session state and Supabase."""
    from services import storage as _storage
    supabase_id = run.get('supabase_id')
    if supabase_id:
        _storage.delete_quote(supabase_id)
    history = st.session_state.run_history
    try:
        history.remove(run)
    except ValueError:
        if 0 <= idx < len(history):
            history.pop(idx)
    st.session_state[f'_del_confirm_{idx}'] = False


def render_dashboard() -> None:
    """Render the dashboard landing page."""
    from ui.sidebar import _status_html
    st.markdown(
        f'<div class="gq-header">'
        f'<div class="gq-header-icon">📊</div>'
        f'<div style="flex:1">'
        f'<p class="gq-header-title">Quote Pipeline Dashboard</p>'
        f'<p class="gq-header-sub">Goodrich Gasket — track every enquiry from intake to PO</p>'
        f'</div>'
        f'<div style="font-size:0.78rem;color:#c8d8f0;display:flex;gap:1rem;align-items:center">'
        f'{_status_html()}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    cta_col, refresh_col, _ = st.columns([2, 1, 7])
    with cta_col:
        if st.button('＋ New Enquiry', type='primary', key='dash_new_enq',
                     use_container_width=True):
            st.session_state.working_items = []
            st.session_state._quote_data = {}
            st.session_state._quote_excel = None
            st.session_state.pop('_active_hist_entry', None)
            st.session_state._show_quote_page = False
            if _has_workspace_page():
                st.switch_page('pages/2_Quote_Workspace.py')
    with refresh_col:
        if st.button('🔄 Refresh', key='dash_refresh', use_container_width=True,
                     help='Reload history from database'):
            st.session_state._history_loaded = False
            st.rerun()

    history = st.session_state.run_history or []
    _render_metric_row(history)
    _render_top_types(history)
    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)
    _render_pipeline(history)
    st.markdown('<div style="height:0.8rem"></div>', unsafe_allow_html=True)
    _render_history_table(history)
