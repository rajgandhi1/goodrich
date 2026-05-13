"""Dashboard landing page for quote pipeline operations."""
from __future__ import annotations

import datetime as _dt
from collections import Counter
from html import escape as _escape

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


META_STAGES = {'repricing', 'sent', 'po'}


_STAGE_STYLES = {
    'initial': ('#eef2ff', '#3730a3', '#6366f1'),
    'review': ('#fff7ed', '#9a3412', '#f97316'),
    'quote_prep': ('#eff6ff', '#1d4ed8', '#3b82f6'),
    'repricing': ('#fef3c7', '#92400e', '#f59e0b'),
    'sent': ('#ecfdf5', '#047857', '#10b981'),
    'po': ('#dcfce7', '#166534', '#22c55e'),
}


def _safe(value: object) -> str:
    return _escape(str(value or ''), quote=True)


def _items_processed(history: list[dict]) -> int:
    return sum(int(r.get('n_items') or 0) for r in history)


def _top_gasket_types(history: list[dict], top_n: int = 5) -> list[tuple[str, int]]:
    c: Counter = Counter()
    for run in history:
        for item in run.get('items') or []:
            c[(item.get('gasket_type') or 'UNKNOWN').upper()] += 1
    return c.most_common(top_n)


def _stage_count(history: list[dict], stage: str) -> int:
    return sum(1 for r in history if (r.get('stage') or 'initial') == stage)


def _conversion_rate(history: list[dict]) -> float:
    if not history:
        return 0.0
    converted = sum(
        1 for r in history
        if (r.get('stage') or 'initial') in ('sent', 'po') and get_outcome(r) != 'lost'
    )
    return 100.0 * converted / len(history)


def _win_rate(history: list[dict]) -> float | None:
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
    parts = [run.get(k) for k in ('quote_no', 'customer', 'project_ref') if run.get(k)]
    if parts:
        return ' - '.join(parts)
    ts = run.get('timestamp', '')
    return f'Enquiry - {ts}' if ts else 'New Enquiry'


def _health_label(history: list[dict]) -> tuple[str, str]:
    if not history:
        return 'Ready for intake', 'Start by creating a new enquiry.'
    stale = sum(
        1 for r in history
        if (current_stage_age_days(r) or 0) >= 7 and (r.get('stage') or 'initial') != 'po'
    )
    if stale:
        return f'{stale} ageing quote{"s" if stale != 1 else ""}', 'Review quotes older than 7 days.'
    pending = sum(1 for r in history if (r.get('stage') or 'initial') in ('initial', 'review'))
    if pending:
        return f'{pending} pending review', 'Clear review queue to keep the pipeline moving.'
    return 'Pipeline healthy', 'No urgent ageing or review backlog.'


def _render_metric_row(history: list[dict]) -> None:
    total_quotes = len(history)
    items_done = _items_processed(history)
    pending = sum(1 for r in history if (r.get('stage') or 'initial') in ('initial', 'review'))
    conv = _conversion_rate(history)
    po_count = _stage_count(history, 'po')
    win_rate = _win_rate(history)
    avg_tts = _avg_time_to_sent(history)

    cards = [
        ('Total quotes', f'{total_quotes:,}', 'Active enquiries in the workspace', 'indigo'),
        ('Items processed', f'{items_done:,}', 'Line items extracted and normalized', 'emerald'),
        ('Pending review', f'{pending:,}', 'Initial or review-stage quotes', 'amber'),
        ('Conversion', f'{conv:.0f}%', 'Quotes sent or converted to PO', 'blue'),
        ('Converted to PO', f'{po_count:,}', 'Won opportunities recorded', 'green'),
        ('Win rate', f'{win_rate:.0f}%' if win_rate is not None else '-', 'Won vs lost decisions', 'violet'),
        ('Avg time to send', f'{avg_tts:.1f}d' if avg_tts is not None else '-', 'First intake to customer sent', 'slate'),
    ]
    html = ['<div class="gq-kpi-grid">']
    for label, value, hint, tone in cards:
        html.append(
            f'<div class="gq-kpi-card tone-{tone}">'
            f'<div class="gq-kpi-topline">{_safe(label)}</div>'
            f'<div class="gq-kpi-value">{_safe(value)}</div>'
            f'<div class="gq-kpi-hint">{_safe(hint)}</div>'
            f'</div>'
        )
    html.append('</div>')
    st.markdown(''.join(html), unsafe_allow_html=True)


def _render_top_types(history: list[dict]) -> None:
    top = _top_gasket_types(history)
    if not top:
        return
    with st.container(border=True):
        st.markdown(
            '<div class="gq-section-title">Demand mix</div>'
            '<div class="gq-section-sub">Most frequently processed gasket categories.</div>',
            unsafe_allow_html=True,
        )
        df = pd.DataFrame(top, columns=['Gasket Type', 'Items'])
        chart_col, table_col = st.columns([3, 2])
        with chart_col:
            st.bar_chart(df.set_index('Gasket Type'), height=260)
        with table_col:
            st.dataframe(df, hide_index=True, use_container_width=True, height=260)


def _render_pipeline(history: list[dict]) -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="gq-section-head">'
            '<div><div class="gq-section-title">Pipeline board</div>'
            '<div class="gq-section-sub">Stages move from intake through review, quote prep, customer sent, and PO.</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(len(STAGES))
        for col, stage in zip(cols, STAGES):
            bg, fg, accent = _STAGE_STYLES[stage]
            runs_in_stage = [r for r in history if (r.get('stage') or 'initial') == stage]
            with col:
                st.markdown(
                    f'<div class="gq-lane-head" style="background:{bg};color:{fg};border-color:{accent}">'
                    f'<div class="gq-lane-label">{_safe(STAGE_LABELS[stage])}</div>'
                    f'<div class="gq-lane-count">{len(runs_in_stage)}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                for run in runs_in_stage[:6]:
                    _render_pipeline_card(run, stage)
                if len(runs_in_stage) > 6:
                    st.caption(f'+ {len(runs_in_stage) - 6} more in History')


def _render_pipeline_card(run: dict, stage: str) -> None:
    _, _, accent = _STAGE_STYLES[stage]
    label = _label_for(run)
    cust = run.get('customer') or run.get('project_ref') or '-'
    ts = run.get('timestamp') or ''
    detail = 'Processing' if run.get('processing') else f'{run.get("n_items", 0)} items'
    st.markdown(
        f'<div class="gq-pipeline-card" style="border-left-color:{accent}">'
        f'<div class="gq-pipeline-title">{_safe(label)}</div>'
        f'<div class="gq-pipeline-meta">{_safe(cust)}</div>'
        f'<div class="gq-pipeline-foot">{_safe(ts)} &middot; {_safe(detail)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_history_table(history: list[dict]) -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="gq-section-title">Quote history</div>'
            '<div class="gq-section-sub">Search, reopen, move stage, download PDF, or record outcomes.</div>',
            unsafe_allow_html=True,
        )
        if not history:
            st.info('No quotes yet. Head to the Quote Workspace to create one.')
            return

        f1, f2, f3 = st.columns([2, 3, 5])
        stage_filter = f1.selectbox(
            'Stage', ['All'] + [STAGE_LABELS[s] for s in STAGES],
            key='dash_stage_filter',
        )
        text_filter = f2.text_input(
            'Search',
            placeholder='customer / quote no / project ref',
            key='dash_text_filter',
        ).strip().lower()

        stage_key = None
        if stage_filter != 'All':
            stage_key = next(s for s, lbl in STAGE_LABELS.items() if lbl == stage_filter)

        filtered: list[tuple[int, dict]] = []
        for idx, run in enumerate(history):
            if stage_key and (run.get('stage') or 'initial') != stage_key:
                continue
            if text_filter:
                hay = ' '.join(
                    str(run.get(k) or '') for k in ('customer', 'project_ref', 'quote_no', 'custom_label')
                ).lower()
                if text_filter not in hay:
                    continue
            filtered.append((idx, run))

        if not filtered:
            st.caption('No quotes match these filters.')
            return

        st.markdown('<div class="gq-history-spacer"></div>', unsafe_allow_html=True)
        for idx, run in filtered:
            _render_history_row(idx, run)


def _status_pill(label: str, tone: str = 'slate') -> str:
    return f'<span class="gq-status-pill pill-{tone}">{_safe(label)}</span>'


def _render_history_row(idx: int, run: dict) -> None:
    stage = run.get('stage') or 'initial'
    bg, fg, _ = _STAGE_STYLES[stage]
    label = _label_for(run)
    cust = run.get('customer') or '-'
    proj = run.get('project_ref') or ''
    ts = run.get('timestamp') or '-'
    n_items = run.get('n_items') or 0
    n_ready = run.get('n_ready') or 0
    n_check = run.get('n_check') or 0
    n_missing = run.get('n_missing') or 0
    outcome = get_outcome(run)
    age = current_stage_age_days(run)
    renaming = st.session_state.get(f'_renaming_{idx}', False)

    with st.container(border=True):
        cols = st.columns([3.5, 2.5, 1.7, 2.2, 2.4])
        with cols[0]:
            title_col, edit_col = st.columns([6, 1])
            title_col.markdown(
                f'<div class="gq-row-title">{_safe(label)}</div>'
                f'<div class="gq-row-sub">{_safe(cust)}{(" &middot; " + _safe(proj)) if proj else ""}</div>',
                unsafe_allow_html=True,
            )
            if edit_col.button('Edit', key=f'dash_rename_btn_{idx}', help='Rename this enquiry'):
                st.session_state[f'_renaming_{idx}'] = not renaming
                st.rerun()

        age_html = ''
        if age is not None:
            tone = 'red' if age >= 7 else ('amber' if age >= 3 else 'blue')
            age_html = _status_pill(f'{_format_age(age)} in stage', tone)
        if run.get('processing'):
            items_html = _status_pill('Processing', 'amber')
        else:
            items_html = (
                f'<div class="gq-item-stats">'
                f'<span><b>{n_items}</b> items</span>'
                f'<span class="ok">{n_ready} ready</span>'
                f'<span class="warn">{n_check} check</span>'
                f'<span class="bad">{n_missing} missing</span>'
                f'</div>'
            )
        cols[1].markdown(
            f'<div class="gq-row-date">{_safe(ts)}</div>{age_html}{items_html}',
            unsafe_allow_html=True,
        )

        outcome_pill = ''
        if outcome == 'won':
            outcome_pill = _status_pill('Won', 'green')
        elif outcome == 'lost':
            outcome_pill = _status_pill('Lost', 'red')
        cols[2].markdown(
            f'<span class="gq-stage-pill" style="background:{bg};color:{fg}">{_safe(STAGE_LABELS[stage])}</span>'
            f'{outcome_pill}',
            unsafe_allow_html=True,
        )

        with cols[3]:
            stage_options = [STAGE_LABELS[s] for s in STAGES]
            current_label = STAGE_LABELS[stage]
            new_label = st.selectbox(
                'Set stage',
                stage_options,
                index=stage_options.index(current_label),
                key=f'dash_set_stage_{idx}',
                label_visibility='collapsed',
            )
            if new_label != current_label:
                new_stage = next(s for s, lbl in STAGE_LABELS.items() if lbl == new_label)
                if new_stage in META_STAGES:
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
                if b3.button('Del', key=f'dash_del_{idx}', use_container_width=True, help='Delete this enquiry'):
                    st.session_state[f'_del_confirm_{idx}'] = True
                    st.rerun()
            else:
                if b3.button('Confirm', key=f'dash_del_confirm_{idx}', use_container_width=True, type='primary'):
                    _delete_history_entry(idx, run)
                    st.rerun()

        if renaming:
            rc1, rc2, rc3, _ = st.columns([4, 1, 1, 4])
            new_name = rc1.text_input(
                'Name',
                value=run.get('custom_label') or '',
                placeholder='e.g. NRL Enquiry May 2026',
                key=f'dash_rename_input_{idx}',
                label_visibility='collapsed',
            )
            if rc2.button('Save', key=f'dash_rename_save_{idx}', type='primary', use_container_width=True):
                run['custom_label'] = new_name.strip()
                _persist_entry(run)
                st.session_state.pop(f'_renaming_{idx}', None)
                st.rerun()
            if rc3.button('Cancel', key=f'dash_rename_cancel_{idx}', use_container_width=True):
                st.session_state.pop(f'_renaming_{idx}', None)
                st.rerun()

        if stage == 'sent':
            wl_cols = st.columns([1, 1, 8])
            if outcome != 'won' and wl_cols[0].button(
                'Won',
                key=f'dash_won_{idx}',
                use_container_width=True,
                help='Move to Converted to PO',
            ):
                st.session_state[f'_pending_stage_{idx}'] = 'po'
                st.rerun()
            if outcome != 'lost' and wl_cols[1].button(
                'Lost',
                key=f'dash_lost_{idx}',
                use_container_width=True,
                help='Mark as lost; quote stays in Sent stage',
            ):
                set_outcome(run, 'lost')
                st.rerun()
            if outcome == 'lost' and wl_cols[1].button(
                'Reopen',
                key=f'dash_reopen_{idx}',
                use_container_width=True,
                help='Clear the Lost flag',
            ):
                set_outcome(run, '')
                st.rerun()

        pending = st.session_state.get(f'_pending_stage_{idx}')
        if pending:
            _render_pending_stage_form(idx, run, pending)

        meta = run.get('stage_meta') or {}
        meta_bits: list[str] = []
        if meta.get('po_no'):
            meta_bits.append(f'PO: {meta["po_no"]}')
        if meta.get('po_value'):
            meta_bits.append(f'INR {meta["po_value"]}')
        if meta.get('sent_to'):
            meta_bits.append(f'Sent to: {meta["sent_to"]}')
        if meta.get('sent_at'):
            meta_bits.append(f'on {meta["sent_at"]}')
        if meta.get('reprice_note'):
            meta_bits.append(f'Reprice: {meta["reprice_note"]}')
        if meta_bits:
            st.markdown(
                f'<div class="gq-row-meta">{" &middot; ".join(_safe(bit) for bit in meta_bits)}</div>',
                unsafe_allow_html=True,
            )


def _render_pending_stage_form(idx: int, run: dict, new_stage: str) -> None:
    label = STAGE_LABELS[new_stage]
    existing = run.get('stage_meta') or {}
    today = _dt.date.today().isoformat()
    with st.form(key=f'dash_meta_form_{idx}_{new_stage}', clear_on_submit=False):
        st.markdown(f'**Advance to {label}** - capture context, then save.')
        meta: dict = {}
        if new_stage == 'sent':
            c1, c2 = st.columns(2)
            meta['sent_to'] = c1.text_input(
                'Recipient email',
                value=existing.get('sent_to', ''),
                placeholder='buyer@example.com',
                key=f'meta_sent_to_{idx}',
            )
            meta['sent_at'] = c2.text_input('Date sent', value=existing.get('sent_at', today), key=f'meta_sent_at_{idx}')
            meta['sent_note'] = st.text_input(
                'Note (optional)',
                value=existing.get('sent_note', ''),
                key=f'meta_sent_note_{idx}',
            )
        elif new_stage == 'po':
            c1, c2, c3 = st.columns([2, 2, 2])
            meta['po_no'] = c1.text_input(
                'PO number',
                value=existing.get('po_no', ''),
                placeholder='e.g. 4500123456',
                key=f'meta_po_no_{idx}',
            )
            meta['po_value'] = c2.text_input(
                'PO value (INR)',
                value=existing.get('po_value', ''),
                placeholder='e.g. 245000',
                key=f'meta_po_value_{idx}',
            )
            meta['po_date'] = c3.text_input('PO date', value=existing.get('po_date', today), key=f'meta_po_date_{idx}')
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
    return f'{days / 7:.0f}w'


def _has_workspace_page() -> bool:
    from pathlib import Path

    return (Path(__file__).resolve().parents[1] / 'pages' / '2_Quote_Workspace.py').exists()


def _delete_history_entry(idx: int, run: dict) -> None:
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
    from ui.sidebar import _status_html

    history = st.session_state.run_history or []
    health_title, health_sub = _health_label(history)

    st.markdown(
        f'<div class="gq-dashboard-hero">'
        f'<div>'
        f'<div class="gq-eyebrow">Goodrich Gasket Quote Operations</div>'
        f'<h1>Quote Pipeline Dashboard</h1>'
        f'<p>Track every enquiry from document intake to customer quote and purchase order.</p>'
        f'</div>'
        f'<div class="gq-hero-status">'
        f'<div class="gq-hero-status-label">Operational status</div>'
        f'<div class="gq-hero-status-value">{_safe(health_title)}</div>'
        f'<div class="gq-hero-status-sub">{_safe(health_sub)}</div>'
        f'<div class="gq-hero-dots">{_status_html()}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    cta_col, refresh_col, _ = st.columns([1.6, 1.2, 7.2])
    with cta_col:
        if st.button('+ New Enquiry', type='primary', key='dash_new_enq', use_container_width=True):
            st.session_state.working_items = []
            st.session_state._quote_data = {}
            st.session_state._quote_excel = None
            st.session_state.pop('_active_hist_entry', None)
            st.session_state._show_quote_page = False
            if _has_workspace_page():
                st.switch_page('pages/2_Quote_Workspace.py')
    with refresh_col:
        if st.button('Refresh', key='dash_refresh', use_container_width=True, help='Reload history from database'):
            st.session_state._history_loaded = False
            st.rerun()

    _render_metric_row(history)

    chart_col, board_col = st.columns([4, 8])
    with chart_col:
        _render_top_types(history)
    with board_col:
        _render_pipeline(history)

    _render_history_table(history)
