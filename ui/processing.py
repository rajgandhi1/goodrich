import os as _os

import streamlit as st

from core.formatter import format_description
from core.rules import apply_rules
from ui.editor import _build_preview_df


def process_and_append(source, source_type: str):
    """
    Extract, apply rules, and append processed items to working_items.
    Pipeline: document_reader (GPT-4o-mini) → rules → formatter
    """
    from core.document_reader import read_document_smart, SmartParseError

    status_text = st.empty()
    progress_bar = st.progress(0)
    preview_ph   = st.empty()

    api_key = _os.environ.get('OPENAI_API_KEY')
    if not api_key:
        st.warning('An OpenAI API key is required. Enter it in the sidebar.')
        progress_bar.empty(); status_text.empty()
        return False

    try:
        from openai import OpenAI as _OAI
        _client = _OAI(api_key=api_key, timeout=180.0)
    except Exception as e:
        st.error(f'Could not create OpenAI client: {e}')
        progress_bar.empty(); status_text.empty()
        return False

    status_text.text('Sending document to LLM')
    progress_bar.progress(10)

    # Accumulates processed items streamed in chunk by chunk for live preview
    _streamed: list[dict] = []
    _line_offset_ref = [
        max((i.get('line_no') or 0 for i in st.session_state.working_items), default=0)
    ]

    def _on_chunk_items(chunk_items):
        for item in chunk_items:
            item = apply_rules(item)
            item['ggpl_description'] = format_description(item)
            _line_offset_ref[0] += 1
            item['line_no'] = _line_offset_ref[0]
            _streamed.append(item)
        status_text.text(f'LLM processing... {len(_streamed)} item(s) extracted so far')
        preview_ph.dataframe(
            _build_preview_df(_streamed),
            use_container_width=False,
            hide_index=True,
            height=min(80 + 35 * len(_streamed), 400),
        )

    def _on_progress(done, total):
        progress_bar.progress(10 + int(done / total * 75))

    try:
        extracted_items, n_skipped = read_document_smart(
            source, source_type, _client,
            progress_cb=_on_progress,
            on_chunk_items=_on_chunk_items,
        )
    except SmartParseError as e:
        err_msg = str(e)
        if 'no extractable text' in err_msg.lower() or 'scanned' in err_msg.lower():
            st.warning(
                'PDF appears to be a scanned image — text cannot be extracted. '
                'Copy the text from your PDF viewer and paste it into the Email tab.'
            )
        elif 'rate_limit' in err_msg.lower() or '429' in err_msg:
            st.warning('OpenAI rate limit hit. Wait 60 seconds and try again.')
        elif 'authentication' in err_msg.lower() or 'invalid api key' in err_msg.lower():
            st.warning('Invalid OpenAI API key. Check it in the sidebar.')
        elif 'no_items_found' in err_msg:
            _is_cover = (
                source_type == 'email' and len(str(source).strip()) < 500
                and not any(kw in str(source).upper() for kw in
                            ['150#', '300#', 'PN ', 'GASKET', 'ASME', 'CNAF',
                             'PTFE', 'SPIRAL', 'RTJ', 'NEOPRENE', 'EPDM', 'GRAPHITE'])
            )
            if _is_cover:
                st.warning(
                    'The email body appears to be a cover note. '
                    'The actual line items are in an **attached Excel or PDF** — '
                    'upload it using the Excel or PDF tab.'
                )
            else:
                st.warning(
                    'No gasket line items were found in this document. '
                    'GPT-4o read the full content but found no gasket specifications.\n\n'
                    '**Possible reasons:**\n'
                    '- Cover letter / admin file with no item details\n'
                    '- Scanned PDF (copy-paste text into the Email tab)\n'
                    '- All items are non-gasket products'
                )
        else:
            st.warning(f'Smart Parse error: {err_msg}')
        progress_bar.empty(); status_text.empty()
        return False

    if n_skipped:
        st.info(f'{n_skipped} non-gasket item(s) automatically filtered out.')

    if extracted_items:
        first_item = extracted_items[0]
        if first_item.get('_doc_row_count'):
            st.info(f'Processed {first_item["_doc_row_count"]} source row(s) from the uploaded Excel file.')
        if first_item.get('_smart_parse_partial'):
            failed = first_item.get('_smart_parse_failed_chunks') or []
            st.warning(
                f'Smart Parse completed partially: {len(failed)} chunk(s) failed after retries. '
                'The extracted rows were added; retry the file or split the failed section if rows are missing.'
            )

    # ── Common tail: rules + formatter ────────────────────────────────────
    progress_bar.progress(88)
    n = len(extracted_items)
    if n == 0:
        st.warning('No gasket line items were extracted from the document.')
        progress_bar.empty()
        status_text.empty()
        return False

    step = max(1, n // 20)
    processed = []
    existing = st.session_state.working_items
    line_offset = (max(i.get('line_no', 0) for i in existing) if existing else 0)

    for i, extracted in enumerate(extracted_items, 1):
        item = apply_rules(extracted)
        item['ggpl_description'] = format_description(item)
        item['line_no'] = line_offset + i
        processed.append(item)
        progress_bar.progress(88 + int(i / n * 11))
        if i % step == 0 or i == n:
            status_text.text(f'Applying business rules... {i}/{n} items')
            preview_ph.dataframe(
                _build_preview_df(processed),
                use_container_width=False,
                hide_index=True,
                height=min(80 + 35 * len(processed), 400),
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


