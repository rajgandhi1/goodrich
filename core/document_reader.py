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
import re
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
- od_mm, id_mm (numbers): only when value is already given in mm. Otherwise leave both blank and put the OD/ID exactly as written (any unit — inches, feet-inches, fractions) into `size`, with size_type="OD_ID". Code will handle unit conversion.
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
    """Convert Excel to cleaned markdown tables for LLM input.

    Improvements over openpyxl approach:
    - Drops columns that are >80% empty (PO numbers, plant tags, etc.)
    - Detects header row automatically (first row with ≥3 non-empty cells)
    - Strips whitespace, collapses runs of spaces, removes literal 'nan'
    - Outputs markdown tables — more readable for the LLM than tab-separated
    """
    import re
    import pandas as pd

    parts: list[str] = []
    total_rows = 0
    was_truncated = False

    all_sheets: dict = pd.read_excel(
        io.BytesIO(excel_bytes),
        sheet_name=None,
        header=None,
        dtype=str,
        na_filter=False,
    )

    for sheet_name, raw_df in all_sheets.items():
        if raw_df.empty:
            continue

        # Clean every cell: strip whitespace, collapse spaces, drop 'nan'/'none'/'#N/A'
        def _clean(val: str) -> str:
            val = str(val).strip()
            val = re.sub(r'\s+', ' ', val)
            if val.lower() in ('nan', 'none', '#n/a', 'n/a', '#na', '-'):
                return ''
            return val

        df = raw_df.map(_clean)  # type: ignore[arg-type]

        # Remove fully-empty rows
        df = df[df.apply(lambda r: any(c for c in r), axis=1)].reset_index(drop=True)
        if df.empty:
            continue

        # Detect header row: first row with ≥3 non-empty cells
        header_idx = 0
        for i, row in df.iterrows():
            if sum(1 for c in row if c) >= 3:
                header_idx = int(i)  # type: ignore[arg-type]
                break

        df.columns = df.iloc[header_idx].tolist()
        df = df.iloc[header_idx + 1:].reset_index(drop=True)

        # Drop columns where >80% of values are empty
        min_fill = max(1, int(len(df) * 0.20))
        df = df.loc[:, df.apply(lambda col: (col != '').sum() >= min_fill)]

        # Drop duplicate column names (keep first occurrence)
        seen: set = set()
        keep_cols = []
        for col in df.columns:
            key = str(col).strip().lower()
            if key not in seen:
                seen.add(key)
                keep_cols.append(col)
        df = df[keep_cols]

        # Remove rows that are entirely empty after column filtering
        df = df[df.apply(lambda r: any(c for c in r), axis=1)].reset_index(drop=True)
        if df.empty:
            continue

        # Truncate to max_rows across all sheets
        remaining = max_rows - total_rows
        if remaining <= 0:
            was_truncated = True
            break
        if len(df) > remaining:
            df = df.iloc[:remaining]
            was_truncated = True

        total_rows += len(df)

        # Render as markdown table
        headers = [str(c) for c in df.columns]
        sep = ['---'] * len(headers)
        md_rows = [
            '| ' + ' | '.join(headers) + ' |',
            '| ' + ' | '.join(sep) + ' |',
        ]
        for _, row in df.iterrows():
            cells = [str(v).replace('|', '/') for v in row]
            md_rows.append('| ' + ' | '.join(cells) + ' |')

        parts.append(f'=== Sheet: {sheet_name} ===')
        parts.extend(md_rows)

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

    if not is_excel:
        non_empty = [l for l in lines if l.strip()]
        if len(non_empty) <= chunk_size:
            return [document_text]
        return [
            '\n'.join(non_empty[i:i + chunk_size])
            for i in range(0, len(non_empty), chunk_size)
        ]

    # Excel: markdown table format — sheet marker + col header + separator are repeated in each chunk
    # Structure per sheet: "=== Sheet: X ===" / "| col | ... |" / "| --- | ... |" / data rows...
    header_prefix: list[str] = []  # lines that repeat at top of every chunk
    data_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('=== Sheet:'):
            # Grab sheet marker + col header + separator (next 2 lines)
            header_prefix = [line]
            if i + 1 < len(lines):
                header_prefix.append(lines[i + 1])  # | col | ... |
            if i + 2 < len(lines):
                header_prefix.append(lines[i + 2])  # | --- | ... |
            i += 3
        else:
            if line.strip():
                data_lines.append(line)
            i += 1

    if len(data_lines) <= chunk_size:
        return [document_text]

    prefix = '\n'.join(header_prefix)
    return [
        f'{prefix}\n' + '\n'.join(data_lines[j:j + chunk_size])
        for j in range(0, len(data_lines), chunk_size)
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
            model='gpt-4.1-mini',
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
        if 'insufficient_quota' in err.lower():
            raise SmartParseError(
                'OpenAI account quota exceeded — your prepaid credit has run out. '
                'Add credits at platform.openai.com/settings/billing, then try again.'
            )
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


_FT_IN_RE = re.compile(
    r"(\d+)\s*[’'`]\s*-?\s*(\d+)(?:\s+(\d+)\s*/\s*(\d+))?\s*[”\"]?"
)
_IN_RE = re.compile(r"(\d+)(?:\s+(\d+)\s*/\s*(\d+))?\s*[”\"]")
_MM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mm", re.I)
_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _token_to_mm(token: str) -> float | None:
    """Parse one dimension token (mm, inches, feet-inches, with optional fraction) to mm."""
    if not token:
        return None
    s = str(token).strip()
    m = _MM_RE.search(s)
    if m:
        return float(m.group(1))
    m = _FT_IN_RE.search(s)
    if m:
        ft = int(m.group(1)); inch = int(m.group(2))
        if m.group(3) and m.group(4):
            inch += int(m.group(3)) / int(m.group(4))
        return round((ft * 12 + inch) * 25.4, 3)
    m = _IN_RE.search(s)
    if m:
        inch = int(m.group(1))
        if m.group(2) and m.group(3):
            inch += int(m.group(2)) / int(m.group(3))
        return round(inch * 25.4, 3)
    m = _NUM_RE.search(s)
    if m:
        return float(m.group(1))
    return None


def _parse_od_id(size_str: str) -> tuple[float | None, float | None]:
    """Extract (od_mm, id_mm) from a free-form size string containing OD and ID."""
    if not size_str:
        return None, None
    s = str(size_str)
    # Labelled OD/ID — match the value immediately preceding the label
    label = r"[\d\.\s/'’`\"”-]+"
    od = re.search(rf"({label})\s*(?:O\.?\s*D\.?|OD\b)", s, re.I)
    id_ = re.search(rf"({label})\s*(?:I\.?\s*D\.?|ID\b)", s, re.I)
    if od and id_:
        return _token_to_mm(od.group(1)), _token_to_mm(id_.group(1))
    # Unlabelled "A x B" — assume larger is OD
    m = re.search(r"(.+?)\s*[xX×]\s*(.+)", s)
    if m:
        a, b = _token_to_mm(m.group(1)), _token_to_mm(m.group(2))
        if a and b:
            return (max(a, b), min(a, b))
    return None, None


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

        # Fill od_mm/id_mm from `size` when LLM left them blank (handles inches, feet-inches, fractions)
        if item.get('od_mm') is None or item.get('id_mm') is None:
            size_str = item.get('size') or ''
            if 'OD' in size_str.upper() or 'ID' in size_str.upper() or '×' in size_str or 'X' in size_str.upper():
                od, id_ = _parse_od_id(size_str)
                if item.get('od_mm') is None and od is not None:
                    item['od_mm'] = od
                if item.get('id_mm') is None and id_ is not None:
                    item['id_mm'] = id_

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
