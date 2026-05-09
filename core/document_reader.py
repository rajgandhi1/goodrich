"""
Smart Parse mode — reads the customer enquiry document with parallel GPT-4o-mini
calls (one per chunk of rows) and returns structured gasket line items.
"""
from __future__ import annotations

import io
import json
import hashlib
import logging
import os
import concurrent.futures
import threading

logger = logging.getLogger(__name__)

_SMART_CACHE_TTL = 7 * 24 * 3600
_CHUNK_SIZE = 30
_MAX_WORKERS = 1  # sequential — avoids burst rate limits on gpt-4o (30K TPM tier 1)


class SmartParseError(Exception):
    """Raised when Smart Parse cannot complete."""


_SYSTEM_PROMPT = """You are an expert in industrial gasket procurement. Extract every line item from the customer enquiry document and return ONLY valid JSON: {"items": [...]}.

FIELDS per item (omit a field entirely if value is unknown — never output null):
- line_no (int), quantity (number), uom ("NOS" or "M"), raw_description (verbatim copy of input text), is_gasket (bool)
- size (string, keep as found), size_type ("NPS"/"NB"/"DN"/"OD_ID"/"UNKNOWN")
- rating: normalise to "150#"/"300#"/"600#" etc. or "PN 10"/"PN 16" etc.
  Variants: "# 150", "#  300", "CL 150", "Class 300" → "150#", "300#"; "PN16", "PN-16" → "PN 16"
- gasket_type: "SOFT_CUT" / "SPIRAL_WOUND" / "RTJ" / "KAMM" / "DJI" / "ISK"
- moc: for SOFT_CUT only — the sealing material (EPDM, NEOPRENE, CNAF, PTFE, VITON, etc.)
  Unspecified rubber with no clear type → omit moc, set special="MOC ambiguous - confirm rubber type"
- face_type: "RF" or "FF" — for SOFT_CUT and ISK only
- thickness_mm (number): default 3 for SOFT_CUT, 4.5 for SPIRAL_WOUND if not stated
- standard: "ASME B16.21" (SOFT_CUT, # rating), "EN 1514-1" (SOFT_CUT, PN rating), "ASME B16.20" (SW/RTJ)
  NPS ≥26": use "ASME B16.47" instead of B16.21
- od_mm, id_mm (numbers): when size is given as OD×ID in mm; for "A×B mm" use larger value as od_mm
- special: genuine technical notes only — ignore plant tag numbers, MR/RFQ references, area codes

SPIRAL_WOUND — always extract all four material fields:
- sw_winding_material: the metal strip (e.g. SS316, SS304, INCONEL 625, HASTELLOY C276)
- sw_filler: filler/sealing element (GRAPHITE, FLEXIBLE GRAPHITE, PTFE, MICA, CERAMIC)
- sw_inner_ring: inner ring material if present (e.g. SS316, SS304, CS)
- sw_outer_ring: outer centering ring material (e.g. CS, SS304, SS316) — often mandatory

RTJ: ring_no (R-/RX-/BX- number), rtj_groove_type ("OCT"/"OVL"/"BX"), rtj_hardness_bhn (number)
KAMM: kamm_core_material, kamm_surface_material, kamm_core_thk, kamm_integral_outer_ring
DJI: dji_filler, dji_face_type, dji_id_first (bool — true when ID listed before OD in input)
ISK: isk_style, isk_type, isk_fire_safety, isk_gasket_material, isk_core_material, isk_sleeve_material, isk_washer_material, isk_primary_seal, isk_insulating_washer

NORMALISATION:
- is_gasket=false for bolts, studs, nuts, flanges, fittings, pipes (still include the row)
- Materials: SS 316 / 316SS / S.S.316L → SS316/SS316L; M.S./Mild Steel/Carbon Steel → CS; 304SS → SS304
- Duplex → UNS S31803; Super Duplex/2507 → UNS S32750
- Ignore plant area tags and procurement reference codes embedded in descriptions — they are not materials or sizes
- uom "M" (metres) = sheet/roll supply, not individual gaskets
"""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from a PDF using pdfplumber. Returns empty string on failure."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        return '\n'.join(parts)
    except ImportError:
        raise SmartParseError('pdfplumber not installed. Run: pip install pdfplumber')
    except Exception as e:
        logger.warning(f'PDF text extraction failed: {e}')
        return ''


def _excel_to_text(excel_bytes: bytes, max_rows: int = 400) -> tuple[str, bool, int]:
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
                continue
            if total_rows >= max_rows:
                was_truncated = True
                break
            sheet_rows.append('\t'.join(cells))
            total_rows += 1
        if sheet_rows:
            parts.append(f'=== Sheet: {sheet_name} ===')
            parts.extend(sheet_rows)

    return '\n'.join(parts), was_truncated, total_rows


def _sanitize_text(text: str) -> str:
    import unicodedata
    import re
    text = unicodedata.normalize('NFKC', text)
    text = text.encode('ascii', errors='replace').decode('ascii')
    text = re.sub(r'\?+', ' ', text)
    return text


def _prepare_document_text(source, source_type: str) -> tuple[str, dict]:
    metadata: dict = {'char_count': 0, 'was_truncated': False}

    if source_type == 'email':
        text = _sanitize_text(str(source))
        if len(text) > 50000:
            text = text[:50000]
            metadata['was_truncated'] = True
    elif source_type == 'excel':
        text, was_truncated, row_count = _excel_to_text(source, max_rows=400)
        text = _sanitize_text(text)
        if len(text) > 50000:
            text = text[:50000]
            was_truncated = True
        metadata['was_truncated'] = was_truncated
        metadata['row_count'] = row_count
    elif source_type == 'pdf':
        text = _sanitize_text(extract_text_from_pdf(source))
        if not text.strip():
            raise SmartParseError(
                'PDF has no extractable text - it appears to be a scanned image. '
                'Open the PDF, select all text (Ctrl+A), copy it, then paste into the Email tab.'
            )
        if len(text) > 50000:
            text = text[:50000]
            metadata['was_truncated'] = True
    else:
        raise SmartParseError(f'Unknown source_type: {source_type!r}')

    metadata['char_count'] = len(text)
    return text, metadata


def _split_into_chunks(document_text: str, chunk_size: int = _CHUNK_SIZE) -> list[str]:
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
                header_lines.append(line)
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
        non_empty = [l for l in lines if l.strip()]
        if len(non_empty) <= chunk_size:
            return [document_text]
        return [
            '\n'.join(non_empty[i:i + chunk_size])
            for i in range(0, len(non_empty), chunk_size)
        ]


def _get_redis():
    url = os.environ.get('REDIS_URL')
    if not url:
        return None
    try:
        import redis
        return redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    except Exception:
        return None


def _cache_key(content: str) -> str:
    return f'gq:smart:{hashlib.sha256(content.encode()).hexdigest()[:20]}'


def _call_single_chunk(openai_client, chunk_text: str, source_type: str) -> list[dict]:
    """Call gpt-4o-mini on one chunk of document text. Returns raw item dicts (not validated)."""
    user_msg = f'Document type: {source_type}\n\n--- DOCUMENT ---\n{chunk_text}\n--- END ---'
    try:
        resp = openai_client.chat.completions.create(
            model='gpt-4o',
            temperature=0,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {'role': 'user', 'content': user_msg},
            ],
            timeout=120,
            max_tokens=8192,
        )
        content = resp.choices[0].message.content or '{}'
        finish_reason = resp.choices[0].finish_reason
    except UnicodeEncodeError:
        raise SmartParseError(
            'API key contains a non-ASCII character. Clear the key, retype it, and try again.'
        )
    except Exception as e:
        err = str(e)
        if 'rate_limit' in err.lower() or '429' in err:
            raise SmartParseError('OpenAI rate limit reached. Wait 60 seconds and try again.')
        if 'authentication' in err.lower() or '401' in err or 'invalid api key' in err.lower():
            raise SmartParseError('Invalid OpenAI API key. Check the key in the sidebar.')
        if 'timeout' in err.lower() or 'timed out' in err.lower():
            raise SmartParseError('Request timed out. Check your internet connection and try again.')
        raise SmartParseError(f'OpenAI API call failed: {err}')

    if finish_reason == 'length':
        raise SmartParseError('Response cut off — chunk too large. Try splitting the file.')

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise SmartParseError(f'Model returned malformed JSON: {e}')

    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                return v
    raise SmartParseError('Unexpected response structure from model.')


def _normalize_items(raw_items: list) -> tuple[list[dict], int]:
    """Coerce raw LLM output to the schema that rules.py expects."""
    KEEP_AS_STRING = {'uom', 'raw_description', 'gasket_type', 'size_type', 'confidence'}
    FLOAT_FIELDS = ('od_mm', 'id_mm', 'thickness_mm', 'rtj_hardness_bhn', 'kamm_core_thk', 'quantity')
    INT_FIELDS = ('line_no',)
    UPPER_FIELDS = ('gasket_type', 'size_type', 'face_type', 'rtj_groove_type', 'uom', 'confidence', 'isk_fire_safety')

    result = []
    skipped = 0
    all_non_gasket = []

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        is_gasket = raw.get('is_gasket', True)
        if is_gasket is False or str(is_gasket).lower() == 'false':
            skipped += 1
            all_non_gasket.append(raw)
            continue

        item = dict(raw)

        # Normalize null strings
        for k, v in item.items():
            if k not in KEEP_AS_STRING and isinstance(v, str) and v.strip().lower() in ('null', 'none', ''):
                item[k] = None

        # Type coercions
        for f in FLOAT_FIELDS:
            if item.get(f) is not None:
                try:
                    item[f] = float(item[f])
                except (TypeError, ValueError):
                    item[f] = None

        for f in INT_FIELDS:
            if item.get(f) is not None:
                try:
                    item[f] = int(float(item[f]))
                except (TypeError, ValueError):
                    item[f] = None

        item['dji_id_first'] = bool(item.get('dji_id_first', False))

        # Defaults
        if not item.get('uom'):
            item['uom'] = 'NOS'
        if not item.get('gasket_type'):
            item['gasket_type'] = 'SOFT_CUT'
        if not item.get('size_type'):
            item['size_type'] = 'UNKNOWN'
        if not item.get('confidence'):
            item['confidence'] = 'MEDIUM'

        for f in UPPER_FIELDS:
            if isinstance(item.get(f), str):
                item[f] = item[f].strip().upper()

        result.append(item)

    # Safety: if every item was filtered as non-gasket, un-filter them
    if not result and all_non_gasket:
        logger.warning('All items classified as non-gasket — returning unfiltered')
        for raw in all_non_gasket:
            item = dict(raw)
            item['_all_filtered_fallback'] = True
            result.append(item)
        skipped = 0

    return result, skipped


def _call_llm_parallel(
    openai_client,
    document_text: str,
    source_type: str,
    progress_cb=None,
    on_chunk_items=None,
) -> tuple[list[dict], int]:
    r = _get_redis()
    cache_key = _cache_key(document_text)
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
    logger.info(f'Smart Parse: {len(chunks)} chunk(s), {len(document_text):,} chars')

    all_raw: list[dict] = []
    done_count = 0
    lock = threading.Lock()

    def _process(idx_chunk):
        import time as _time
        idx, chunk = idx_chunk
        logger.info(f'Smart Parse: chunk {idx}/{len(chunks)}...')
        for attempt in range(3):
            try:
                raw = _call_single_chunk(openai_client, chunk, source_type)
                logger.info(f'Smart Parse: chunk {idx} done — {len(raw)} item(s)')
                return raw
            except SmartParseError as e:
                err = str(e).lower()
                if 'timed out' in err and attempt < 2:
                    logger.warning(f'Smart Parse: chunk {idx} timed out, retry {attempt + 1}...')
                    _time.sleep(5)
                elif 'rate limit' in err and attempt < 2:
                    wait = 30 * (attempt + 1)
                    logger.warning(f'Smart Parse: chunk {idx} rate limited, waiting {wait}s...')
                    _time.sleep(wait)
                else:
                    raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {
            executor.submit(_process, (i, chunk)): i
            for i, chunk in enumerate(chunks, 1)
        }
        for future in concurrent.futures.as_completed(futures):
            chunk_raw = future.result()
            with lock:
                all_raw.extend(chunk_raw)
                done_count += 1

            if on_chunk_items and chunk_raw:
                try:
                    chunk_items, _ = _normalize_items(chunk_raw)
                    on_chunk_items(chunk_items)
                except Exception:
                    pass

            if progress_cb:
                with lock:
                    progress_cb(done_count, len(chunks))

    result, skipped = _normalize_items(all_raw)

    if r:
        try:
            r.setex(cache_key, _SMART_CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    logger.info(f'Smart Parse: done — {len(result)} items, {skipped} non-gasket skipped')
    return result, skipped


def read_document_smart(
    source,
    source_type: str,
    openai_client,
    progress_cb=None,
    on_chunk_items=None,
) -> tuple[list[dict], int]:
    """
    Main entry point. Converts input to text, calls LLM in parallel chunks,
    returns (items, skipped_count).
    Raises SmartParseError on failure.
    """
    if progress_cb:
        progress_cb(1, 10)

    document_text, metadata = _prepare_document_text(source, source_type)

    if metadata.get('was_truncated'):
        logger.warning(f'Document truncated at {metadata["char_count"]:,} chars')

    if progress_cb:
        progress_cb(3, 10)

    def _chunk_progress(done, total):
        if progress_cb:
            progress_cb(3 + int(done / total * 6), 10)

    items, skipped = _call_llm_parallel(
        openai_client, document_text, source_type,
        progress_cb=_chunk_progress,
        on_chunk_items=on_chunk_items,
    )

    if progress_cb:
        progress_cb(9, 10)

    if metadata.get('was_truncated') and items:
        items[0]['_doc_was_truncated'] = True

    return items, skipped
