"""
Supabase-backed persistent storage for quote history.

Degrades gracefully when SUPABASE_URL / SUPABASE_KEY are not configured —
falls back to the local JSON file so local dev still works without credentials.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

_client = None
_init_attempted = False


def _get_credentials() -> tuple[str, str]:
    """Return (url, key) from env vars or Streamlit secrets, whichever is set."""
    url = os.environ.get('SUPABASE_URL', '').strip()
    key = os.environ.get('SUPABASE_KEY', '').strip()
    if url and key:
        return url, key
    try:
        import streamlit as st
        url = str(st.secrets.get('SUPABASE_URL', '') or '').strip()
        key = str(st.secrets.get('SUPABASE_KEY', '') or '').strip()
    except Exception:
        pass
    return url, key


def _get_client():
    global _client, _init_attempted
    # If already connected, return cached client.
    if _client is not None:
        return _client
    # If we already tried and got no credentials, retry on each call
    # so secrets set after module import are picked up.
    url, key = _get_credentials()
    if not url or not key:
        return None
    # Only attempt connection once per process to avoid repeated failures.
    if _init_attempted:
        return _client
    _init_attempted = True
    try:
        from supabase import create_client
        _client = create_client(url, key)
        logger.info('Supabase connected')
    except Exception as e:
        logger.warning(f'Supabase init failed: {e}')
    return _client


def is_connected() -> bool:
    return _get_client() is not None


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_quote(entry: dict) -> str | None:
    """Upsert a quote entry. Returns the Supabase UUID on success, None on failure.

    If entry already has a 'supabase_id', performs an UPDATE; otherwise INSERT.
    The returned UUID should be stored back into the entry as entry['supabase_id'].
    """
    sb = _get_client()
    if not sb:
        return None
    try:
        items_val = entry.get('items', [])
        qdata_val = entry.get('quote_data') or {}
        row = {
            'quote_no':       entry.get('quote_no') or '',
            'customer':       entry.get('customer') or '',
            'project_ref':    entry.get('project_ref') or '',
            'custom_label':   entry.get('custom_label') or '',
            'timestamp':      entry.get('timestamp') or '',
            'n_items':        int(entry.get('n_items', 0)),
            'n_ready':        int(entry.get('n_ready', 0)),
            'n_check':        int(entry.get('n_check', 0)),
            'n_missing':      int(entry.get('n_missing', 0)),
            'n_regret':       int(entry.get('n_regret', 0)),
            'items':          items_val if isinstance(items_val, list) else json.loads(items_val),
            'quote_data':     qdata_val if isinstance(qdata_val, dict) else json.loads(qdata_val),
            'quote_pdf_b64':  entry.get('quote_pdf_b64') or '',
            'quote_pdf_name': entry.get('quote_pdf_name') or '',
            'stage':          entry.get('stage') or 'initial',
            'stage_history':  entry.get('stage_history') or [],
            'stage_meta':     entry.get('stage_meta') or {},
        }
        supabase_id = entry.get('supabase_id')
        if supabase_id:
            result = sb.table('quotes').update(row).eq('id', supabase_id).execute()
        else:
            result = sb.table('quotes').insert(row).execute()
        if result.data:
            return result.data[0].get('id')
    except Exception as e:
        logger.warning(f'Supabase save failed: {e}')
        raise RuntimeError(str(e)) from e
    return None


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_quotes(limit: int = 100) -> list[dict]:
    """Return most-recent quotes from Supabase, newest first. Empty list on failure."""
    sb = _get_client()
    if not sb:
        return []
    try:
        result = (
            sb.table('quotes')
            .select('*')
            .order('created_at', desc=True)
            .limit(limit)
            .execute()
        )
        entries = []
        for row in result.data or []:
            entry: dict = {
                'supabase_id':  row.get('id'),
                'quote_no':     row.get('quote_no') or '',
                'customer':     row.get('customer') or '',
                'project_ref':  row.get('project_ref') or '',
                'custom_label': row.get('custom_label') or '',
                'timestamp':    row.get('timestamp') or (row.get('created_at') or '')[:16],
                'n_items':     row.get('n_items', 0),
                'n_ready':     row.get('n_ready', 0),
                'n_check':     row.get('n_check', 0),
                'n_missing':   row.get('n_missing', 0),
                'n_regret':    row.get('n_regret', 0),
                'quote_pdf_b64':  row.get('quote_pdf_b64') or '',
                'quote_pdf_name': row.get('quote_pdf_name') or '',
                'stage':          row.get('stage') or 'initial',
            }
            # items, quote_data, stage_history, stage_meta come back as jsonb
            for key, default in (
                ('items', []),
                ('quote_data', {}),
                ('stage_history', []),
                ('stage_meta', {}),
            ):
                val = row.get(key)
                if isinstance(val, (list, dict)):
                    entry[key] = val
                elif isinstance(val, str):
                    try:
                        entry[key] = json.loads(val)
                    except Exception:
                        entry[key] = default
                else:
                    entry[key] = default
            entries.append(entry)
        return entries
    except Exception as e:
        logger.warning(f'Supabase load failed: {e}')
        return []


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
# Load single
# ---------------------------------------------------------------------------

def load_quote(supabase_id: str) -> dict | None:
    """Fetch a single quote by UUID. Returns None if not found or on error."""
    sb = _get_client()
    if not sb or not supabase_id:
        return None
    try:
        result = sb.table('quotes').select('*').eq('id', supabase_id).limit(1).execute()
        rows = result.data or []
        if not rows:
            return None
        row = rows[0]
        entry: dict = {
            'supabase_id':    row.get('id'),
            'quote_no':       row.get('quote_no') or '',
            'customer':       row.get('customer') or '',
            'project_ref':    row.get('project_ref') or '',
            'custom_label':   row.get('custom_label') or '',
            'timestamp':      row.get('timestamp') or (row.get('created_at') or '')[:16],
            'n_items':        row.get('n_items', 0),
            'n_ready':        row.get('n_ready', 0),
            'n_check':        row.get('n_check', 0),
            'n_missing':      row.get('n_missing', 0),
            'n_regret':       row.get('n_regret', 0),
            'quote_pdf_b64':  row.get('quote_pdf_b64') or '',
            'quote_pdf_name': row.get('quote_pdf_name') or '',
            'stage':          row.get('stage') or 'initial',
        }
        for key, default in (
            ('items', []),
            ('quote_data', {}),
            ('stage_history', []),
            ('stage_meta', {}),
        ):
            val = row.get(key)
            if isinstance(val, (list, dict)):
                entry[key] = val
            elif isinstance(val, str):
                try:
                    entry[key] = json.loads(val)
                except Exception:
                    entry[key] = default
            else:
                entry[key] = default
        return entry
    except Exception as e:
        logger.warning(f'Supabase load_quote failed: {e}')
        return None


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_quote(supabase_id: str) -> bool:
    """Delete a quote by UUID. Returns True on success."""
    sb = _get_client()
    if not sb or not supabase_id:
        return False
    try:
        sb.table('quotes').delete().eq('id', supabase_id).execute()
        return True
    except Exception as e:
        logger.warning(f'Supabase delete failed: {e}')
        return False
