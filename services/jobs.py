"""Background extraction jobs — run LLM processing in a daemon thread.

The thread outlives page navigation in Streamlit because it runs in the same
Python worker process. Results are written directly to Supabase so any page
that reloads will pick them up.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

# supabase_id → running Thread
_active: dict[str, threading.Thread] = {}


def submit(supabase_id: str, source, source_type: str, api_key: str) -> None:
    """Spawn a daemon thread to run extraction and persist results to Supabase."""
    t = threading.Thread(
        target=_run,
        args=(supabase_id, source, source_type, api_key),
        daemon=True,
        name=f'gq-extract-{supabase_id[:8]}',
    )
    t.start()
    _active[supabase_id] = t
    logger.info('Background job started: %s', supabase_id[:8])


def is_running(supabase_id: str) -> bool:
    t = _active.get(supabase_id)
    return t is not None and t.is_alive()


def _run(supabase_id: str, source, source_type: str, api_key: str) -> None:
    try:
        from openai import OpenAI
        from core.document_reader import read_document_smart
        from core.rules import apply_rules, STATUS_READY, STATUS_CHECK, STATUS_MISSING, STATUS_REGRET
        from core.formatter import format_description
        from services import storage as _storage

        client = OpenAI(api_key=api_key, timeout=180.0)
        raw_items, _ = read_document_smart(source, source_type, client)

        processed = []
        for idx, item in enumerate(raw_items, 1):
            item = apply_rules(item)
            item['ggpl_description'] = format_description(item)
            item['line_no'] = idx
            processed.append(item)

        fields = {
            'items':      processed,
            'n_items':    len(processed),
            'n_ready':    sum(1 for i in processed if i.get('status') == STATUS_READY),
            'n_check':    sum(1 for i in processed if i.get('status') == STATUS_CHECK),
            'n_missing':  sum(1 for i in processed if i.get('status') == STATUS_MISSING),
            'n_regret':   sum(1 for i in processed if i.get('status') == STATUS_REGRET),
            'pdf_ready':  False,
        }

        # Load the stub so we keep its other fields (customer, timestamp, stage…)
        stub = _storage.load_quote(supabase_id)
        if stub:
            stub.update(fields)
            _storage.save_quote(stub)
        else:
            # Supabase not connected — nothing we can do from a background thread
            logger.warning('Background job %s: stub not found in Supabase', supabase_id[:8])

        logger.info('Background job %s done: %d items', supabase_id[:8], len(processed))
    except Exception as exc:
        logger.error('Background job %s failed: %s', supabase_id[:8], exc)
    finally:
        _active.pop(supabase_id, None)
