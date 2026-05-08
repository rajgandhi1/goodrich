"""
Smart Parse mode - reads the entire customer enquiry document with a single
GPT-4o call and returns structured gasket line items.

Used as an alternative to parser.py -> extractor.py in Classic mode.
The downstream rules.py -> formatter.py -> exporter.py pipeline is unchanged.
"""
from __future__ import annotations

import io
import json
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

_SMART_CACHE_TTL = 7 * 24 * 3600  # 7 days


class SmartParseError(Exception):
    """Raised when Smart Parse cannot complete. Triggers Classic mode fallback."""


# ---------------------------------------------------------------------------
# Default item template - every field rules.py expects
# ---------------------------------------------------------------------------

_ITEM_TEMPLATE: dict = {
    'line_no': None, 'quantity': None, 'uom': 'NOS', 'raw_description': '',
    'size': None, 'size_type': 'UNKNOWN', 'od_mm': None, 'id_mm': None,
    'rating': None, 'gasket_type': 'SOFT_CUT',
    'moc': None, 'face_type': None, 'thickness_mm': None,
    'standard': None, 'special': None, 'confidence': 'MEDIUM',
    'is_gasket': True,
    'sw_winding_material': None, 'sw_filler': None,
    'sw_inner_ring': None, 'sw_outer_ring': None,
    'rtj_groove_type': None, 'rtj_hardness_bhn': None, 'ring_no': None,
    'kamm_core_material': None, 'kamm_surface_material': None,
    'kamm_covering_layer': None, 'kamm_rib': None,
    'kamm_core_thk': None, 'kamm_integral_outer_ring': None,
    'dji_filler': None, 'dji_rib': None, 'dji_face_type': None, 'dji_id_first': False,
    'isk_style': None, 'isk_type': None, 'isk_fire_safety': None,
    'isk_gasket_material': None, 'isk_core_material': None,
    'isk_sleeve_material': None, 'isk_washer_material': None,
    'isk_primary_seal': None, 'isk_secondary_seal': None,
    'isk_insulating_washer': None,
}

# ---------------------------------------------------------------------------
# GPT-4o system prompt
# ---------------------------------------------------------------------------

_SMART_PARSE_SYSTEM_PROMPT = """You are a gasket procurement data extraction assistant. Extract every gasket line item and return ONLY valid JSON: {"items": [...]}. No markdown, no explanation.

Output ONLY these fields per item (skip a field entirely if the value is null/unknown - do NOT output null):
line_no, quantity, uom, raw_description, is_gasket,
size, size_type, rating, gasket_type, confidence,
moc, face_type, standard, thickness_mm, special,
sw_winding_material, sw_filler, sw_inner_ring, sw_outer_ring,
rtj_groove_type, rtj_hardness_bhn, ring_no,
kamm_core_material, kamm_surface_material, kamm_covering_layer, kamm_rib, kamm_core_thk,
dji_filler, dji_rib, dji_face_type,
isk_gasket_material, isk_core_material, isk_sleeve_material, isk_fire_safety

Rules:
- uom: "NOS" or "M" (meters = sheet supply)
- size: keep as found, e.g. "25 mm NB", "6\\"", "DN 100"
- size_type: "NPS" / "NB" / "DN" / "OD_ID" / "UNKNOWN"
- rating: output as "150#" / "300#" / "600#" etc. or "PN 10" / "PN 16". "# 300" or "#  150" (hash before number) means the same - output as "300#" / "150#"
- gasket_type: "SOFT_CUT" / "SPIRAL_WOUND" / "RTJ" / "KAMM" / "DJI" / "ISK"
- moc: for SOFT_CUT only; omit for SPIRAL_WOUND/RTJ/KAMM/DJI
- face_type: "RF" or "FF" for SOFT_CUT/ISK only; omit for all others
- is_gasket: true for gaskets; false for bolts, flanges, fittings (still include the row)
- raw_description: exact verbatim copy from source
- SPIRAL_WOUND: sw_winding_material = strip metal (e.g. SS316), sw_filler = GRAPHITE/PTFE, sw_inner_ring / sw_outer_ring = ring materials
- Normalize: 316SS->SS316, carbon steel/MS->CS, CL300->300#, Class 150->150#
- Unspecified rubber: omit moc, set special="MOC ambiguous - confirm rubber type"
"""


# ---------------------------------------------------------------------------
# Redis cache helpers
# ---------------------------------------------------------------------------

def _get_redis_smart():
    url = os.environ.get('REDIS_URL')
    if not url:
        return None
    try:
        import redis
        return redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    except Exception:
        return None


def _smart_cache_key(content: str) -> str:
    digest = hashlib.sha256(content.encode()).hexdigest()[:20]
    return f'gq:smart:{digest}'


# ---------------------------------------------------------------------------
# Input preparation
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from a PDF using pdfplumber. Returns empty string on failure."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return '\n'.join(text_parts)
    except ImportError:
        raise SmartParseError(
            'pdfplumber not installed. Run: pip install pdfplumber'
        )
    except Exception as e:
        logger.warning(f'PDF text extraction failed: {e}')
        return ''


def _excel_to_text(excel_bytes: bytes, max_rows: int = 300) -> str:
    """
    Convert Excel workbook to tab-separated text.

    Skips fully empty rows. Caps at max_rows data rows across all sheets.
    Returns a (text, was_truncated, total_row_count) tuple.
    """
    import openpyxl
    from core.parser import worksheet_rows_with_merged_values
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
    parts = []
    total_rows = 0
    was_truncated = False

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheet_rows = []
        for row in worksheet_rows_with_merged_values(ws):
            cells = [str(c) if c is not None else '' for c in row]
            if not any(c.strip() for c in cells):
                continue  # skip fully empty rows
            if total_rows >= max_rows:
                was_truncated = True
                break
            sheet_rows.append('\t'.join(cells))
            total_rows += 1
        if sheet_rows:
            parts.append(f'=== Sheet: {sheet_name} ===')
            parts.extend(sheet_rows)

    text = '\n'.join(parts)
    return text, was_truncated, total_rows


def _sanitize_text(text: str) -> str:
    """Normalize to ASCII-safe text before sending to GPT-4o."""
    import unicodedata
    # NFKC: resolve ligatures, fractions, compatibility variants
    text = unicodedata.normalize('NFKC', text)
    # Encode to ASCII, replacing any non-ASCII character with a plain space.
    # This handles narrow no-break spaces, em dashes, arrows, etc. universally.
    text = text.encode('ascii', errors='replace').decode('ascii')
    # Replace the '?' placeholders from non-ASCII with space so descriptions stay readable
    # (encode 'replace' uses '?' — swap for space to avoid confusing the LLM)
    import re
    text = re.sub(r'\?+', ' ', text)
    return text

def _prepare_document_text(source, source_type: str) -> tuple[str, dict]:
    """
    Convert raw input to a plain text string ready for the LLM.

    Returns (text, metadata) where metadata contains:
      - 'char_count': int
      - 'was_truncated': bool
      - 'row_count': int (Excel only)
      - 'page_count': int (PDF only)
    """
    metadata: dict = {'char_count': 0, 'was_truncated': False}

    if source_type == 'email':
        text = _sanitize_text(str(source))
        if len(text) > 40000:
            text = text[:40000]
            metadata['was_truncated'] = True
        metadata['char_count'] = len(text)
        return text, metadata

    elif source_type == 'excel':
        text, was_truncated, row_count = _excel_to_text(source, max_rows=300)
        text = _sanitize_text(text)
        if len(text) > 40000:
            text = text[:40000]
            was_truncated = True
        metadata['char_count'] = len(text)
        metadata['was_truncated'] = was_truncated
        metadata['row_count'] = row_count
        return text, metadata

    elif source_type == 'pdf':
        text = _sanitize_text(extract_text_from_pdf(source))
        if not text.strip():
            raise SmartParseError(
                'PDF has no extractable text - it appears to be a scanned image. '
                'Open the PDF, select all text (Ctrl+A), copy it, '
                'then paste into the Email tab.'
            )
        if len(text) > 40000:
            text = text[:40000]
            metadata['was_truncated'] = True
        metadata['char_count'] = len(text)
        return text, metadata

    else:
        raise SmartParseError(f'Unknown source_type: {source_type!r}')


# ---------------------------------------------------------------------------
# Output validation & normalization
# ---------------------------------------------------------------------------

def _validate_and_normalize_output(raw_items: list) -> tuple[list[dict], int]:
    """Coerce GPT-4o output list to the exact schema rules.py expects."""
    if not isinstance(raw_items, list):
        raise SmartParseError(f'LLM output is not a list (got {type(raw_items).__name__})')
    if len(raw_items) == 0:
        raise SmartParseError(
            'no_items_found'  # sentinel - caller maps to user-friendly message
        )

    result = []
    skipped_raw = []   # keep filtered items in case we need the safety fallback
    skipped_non_gasket = 0
    for i, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            logger.warning(f'Smart Parse: item {i} is not a dict - skipping')
            continue

        # Filter out non-gasket items before any further processing
        is_gasket_val = raw.get('is_gasket', True)
        if is_gasket_val is False or str(is_gasket_val).lower() == 'false':
            desc_preview = str(raw.get('raw_description', ''))[:60]
            logger.info(f'Smart Parse: skipping non-gasket item - {desc_preview}')
            skipped_non_gasket += 1
            skipped_raw.append(raw)
            continue

        # Start from template, overlay LLM values for known fields
        item: dict = dict(_ITEM_TEMPLATE)
        for k, v in raw.items():
            if k in _ITEM_TEMPLATE:
                item[k] = v

        # Normalize string "null"/"none"/"" -> actual None (except sentinel fields)
        _KEEP_AS_STRING = {'uom', 'raw_description', 'gasket_type', 'size_type', 'confidence'}
        for k, v in item.items():
            if k not in _KEEP_AS_STRING and isinstance(v, str) and v.strip().lower() in ('null', 'none', ''):
                item[k] = None

        # Float coercions
        for f in ('od_mm', 'id_mm', 'thickness_mm', 'rtj_hardness_bhn', 'kamm_core_thk'):
            val = item.get(f)
            if val is not None:
                try:
                    item[f] = float(val)
                except (TypeError, ValueError):
                    item[f] = None

        # Int coercions
        for f in ('line_no',):
            val = item.get(f)
            if val is not None:
                try:
                    item[f] = int(float(val))
                except (TypeError, ValueError):
                    item[f] = None

        # Quantity as float
        val = item.get('quantity')
        if val is not None:
            try:
                item['quantity'] = float(val)
            except (TypeError, ValueError):
                item['quantity'] = None

        # Bool coercion
        item['dji_id_first'] = bool(item.get('dji_id_first', False))

        # Ensure critical defaults
        if not item.get('uom'):
            item['uom'] = 'NOS'
        if not item.get('gasket_type'):
            item['gasket_type'] = 'SOFT_CUT'
        if not item.get('size_type'):
            item['size_type'] = 'UNKNOWN'
        if not item.get('confidence'):
            item['confidence'] = 'MEDIUM'

        # Uppercase certain enum fields
        for f in ('gasket_type', 'size_type', 'face_type', 'rtj_groove_type',
                   'uom', 'confidence', 'isk_fire_safety'):
            v = item.get(f)
            if isinstance(v, str):
                item[f] = v.strip().upper()

        result.append(item)

    if skipped_non_gasket:
        logger.info(
            f'Smart Parse: filtered out {skipped_non_gasket} non-gasket item(s) '
            f'(cam & groove, fittings, etc.) - {len(result)} gasket item(s) remain'
        )

    # Safety fallback: if ALL items were filtered as non-gasket, the is_gasket
    # classification may have been too aggressive (e.g. document title context
    # confused the model). Return everything unfiltered with a flag so the caller
    # can warn the user rather than silently failing.
    if len(result) == 0 and skipped_non_gasket > 0:
        logger.warning(
            f'Smart Parse: all {skipped_non_gasket} item(s) were classified as non-gasket - '
            f'is_gasket filter may be wrong; returning all items unfiltered'
        )
        # Process the skipped items as if they were gaskets
        for raw in skipped_raw:
            item: dict = dict(_ITEM_TEMPLATE)
            for k, v in raw.items():
                if k in _ITEM_TEMPLATE:
                    item[k] = v
            item['_all_filtered_fallback'] = True
            result.append(item)
        skipped_non_gasket = 0  # reset - we un-filtered them

    return result, skipped_non_gasket


# ---------------------------------------------------------------------------
# GPT-4o call
# ---------------------------------------------------------------------------

_CHUNK_SIZE = 50  # rows per GPT-4o call


def _split_into_chunks(document_text: str, chunk_size: int = _CHUNK_SIZE) -> list[str]:
    """
    Split document text into chunks of chunk_size rows/lines.

    Excel (tab-separated): header lines (sheet marker + column row) are prepended
    to every chunk so GPT-4o always has column context.

    PDF / email (plain text): split by non-empty lines; no header prepended.

    Returns a single-element list when no split is needed.
    """
    lines = document_text.splitlines()
    is_excel = any(l.startswith('=== Sheet:') for l in lines[:5])

    if is_excel:
        header_lines: list[str] = []
        data_lines: list[str] = []
        found_data = False
        for line in lines:
            if line.startswith('=== Sheet:'):
                header_lines.append(line)
                found_data = False
            elif not found_data and line.strip():
                header_lines.append(line)  # column header row
                found_data = True
            else:
                data_lines.append(line)

        if len(data_lines) <= chunk_size:
            return [document_text]

        header = '\n'.join(header_lines)
        return [
            f'{header}\n' + '\n'.join(data_lines[i:i + chunk_size])
            for i in range(0, len(data_lines), chunk_size)
        ]
    else:
        # PDF / email - split by non-empty lines
        non_empty = [l for l in lines if l.strip()]
        if len(non_empty) <= chunk_size:
            return [document_text]

        return [
            '\n'.join(non_empty[i:i + chunk_size])
            for i in range(0, len(non_empty), chunk_size)
        ]


def _gpt4o_single_chunk(openai_client, chunk_text: str, source_type: str) -> list[dict]:
    """Call GPT-4o on one chunk of document text. Returns raw item dicts (not validated)."""
    user_msg = (
        f'Document type: {source_type}\n\n'
        f'--- DOCUMENT CONTENT START ---\n'
        f'{chunk_text}\n'
        f'--- DOCUMENT CONTENT END ---'
    )
    try:
        response = openai_client.chat.completions.create(
            model='gpt-4o',
            temperature=0,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': _SMART_PARSE_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_msg},
            ],
            timeout=180,
            max_tokens=16384,
        )
    except UnicodeEncodeError:
        raise SmartParseError(
            'Your OpenAI API key contains an invisible non-ASCII character '
            '(likely a narrow no-break space from copy-pasting). '
            'Clear the key in the sidebar, retype or re-paste it, and try again.'
        )
    except Exception as e:
        err = str(e)
        if 'rate_limit' in err.lower() or '429' in err:
            raise SmartParseError(
                'OpenAI rate limit reached - too many requests. '
                'Wait 60 seconds then try again, or switch to Classic mode.'
            )
        if 'authentication' in err.lower() or '401' in err or 'invalid api key' in err.lower():
            raise SmartParseError(
                'Invalid OpenAI API key. Check that the key in the sidebar starts with "sk-" '
                'and has not expired.'
            )
        if 'timeout' in err.lower() or 'timed out' in err.lower():
            raise SmartParseError(
                'GPT-4o call timed out after 180 seconds. '
                'Check your internet connection and try again.'
            )
        if 'connection' in err.lower() or 'network' in err.lower():
            raise SmartParseError(
                f'Network error reaching OpenAI API: {err}. '
                'Check your internet connection and try again.'
            )
        if 'ascii' in err.lower() and 'encode' in err.lower():
            raise SmartParseError(
                'Your OpenAI API key contains an invisible non-ASCII character '
                '(likely a narrow no-break space from copy-pasting). '
                'Clear the key in the sidebar, retype or re-paste it, and try again.'
            )
        raise SmartParseError(f'GPT-4o API call failed: {err}')

    choice = response.choices[0]
    if choice.finish_reason == 'length':
        raise SmartParseError(
            'GPT-4o output was cut off mid-response. '
            'This chunk is too large - reduce CHUNK_SIZE or split the file.'
        )

    raw_content = choice.message.content or '{}'
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise SmartParseError(f'GPT-4o returned malformed JSON: {e}')

    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                return v
        raise SmartParseError(f'GPT-4o returned a JSON object with no list. Keys: {list(parsed.keys())}')
    raise SmartParseError(f'GPT-4o returned unexpected structure: {type(parsed).__name__}')


def _call_gpt4o(openai_client, document_text: str, source_type: str, progress_cb=None) -> tuple[list[dict], int]:
    """
    GPT-4o call with automatic chunking for large documents.
    Splits into chunks of CHUNK_SIZE rows, calls in parallel, merges results.
    Returns (items, skipped_count).
    """
    import concurrent.futures

    # Check Redis cache first (keyed on full document)
    r = _get_redis_smart()
    cache_key = _smart_cache_key(document_text)
    if r:
        try:
            hit = r.get(cache_key)
            if hit:
                cached = json.loads(hit)
                logger.info(f'Smart Parse: cache hit ({len(cached)} items)')
                return cached, 0
        except Exception:
            pass

    chunks = _split_into_chunks(document_text)
    logger.info(f'Smart Parse: {len(chunks)} chunk(s) for {source_type}')

    # Parallel API calls for each chunk
    all_raw: list[dict] = []
    if len(chunks) == 1:
        all_raw = _gpt4o_single_chunk(openai_client, chunks[0], source_type)
        if progress_cb:
            progress_cb(1, 1)
    else:
        done_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            futures = [
                executor.submit(_gpt4o_single_chunk, openai_client, chunk, source_type)
                for chunk in chunks
            ]
            for future in concurrent.futures.as_completed(futures):
                all_raw.extend(future.result())
                done_count += 1
                if progress_cb:
                    progress_cb(done_count, len(chunks))

    result, skipped = _validate_and_normalize_output(all_raw)

    if r:
        try:
            r.setex(cache_key, _SMART_CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    logger.info(f'Smart Parse: extracted {len(result)} item(s) from {source_type} ({skipped} non-gasket skipped)')
    return result, skipped


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def read_document_smart(
    source,
    source_type: str,
    openai_client,
    progress_cb=None,
) -> tuple[list[dict], int]:
    """
    Main Smart Parse entry point.

    Converts raw input to text, sends one GPT-4o call that reads the entire
    document, and returns (items, skipped_count) where items are structured
    gasket-only dicts ready for rules.py and skipped_count is the number of
    non-gasket items that were filtered out.

    Raises:
        SmartParseError: triggers Classic mode fallback in the caller
    """
    if progress_cb:
        progress_cb(1, 10)

    document_text, metadata = _prepare_document_text(source, source_type)

    if metadata.get('was_truncated'):
        row_count = metadata.get('row_count', '')
        row_info = f' ({row_count} rows read)' if row_count else ''
        logger.warning(
            f'Smart Parse: document truncated{row_info} - '
            f'{metadata["char_count"]:,} chars sent to GPT-4o. '
            f'Consider splitting the file if items are missing.'
        )

    if progress_cb:
        progress_cb(3, 10)

    def _chunk_progress(done, total):
        # Map chunk completion (0→total) onto the 3→9 slice of the outer scale
        if progress_cb:
            progress_cb(3 + int(done / total * 6), 10)

    items, skipped_non_gasket = _call_gpt4o(openai_client, document_text, source_type, progress_cb=_chunk_progress)

    if progress_cb:
        progress_cb(9, 10)

    if metadata.get('was_truncated') and items:
        items[0]['_doc_was_truncated'] = True

    return items, skipped_non_gasket
