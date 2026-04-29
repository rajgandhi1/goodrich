"""
Smart Parse mode — reads the entire customer enquiry document with a single
GPT-4o call and returns structured gasket line items.

Used as an alternative to parser.py → extractor.py in Classic mode.
The downstream rules.py → formatter.py → exporter.py pipeline is unchanged.
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
# Default item template — every field rules.py expects
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

_SMART_PARSE_SYSTEM_PROMPT = r"""You are a gasket procurement document reader for Goodrich Gasket Pvt. Ltd.

Read the customer enquiry document (email, Excel data, or PDF text) and extract EVERY gasket line item.
Return ONLY a JSON object: {"items": [...]}. No markdown, no explanation.

## OUTPUT SCHEMA (one object per gasket line item)
{
  "line_no": <integer|null>,
  "quantity": <number|null>,
  "uom": <"NOS"|"M">,
  "raw_description": "<exact original text of this gasket spec, verbatim>",
  "size": <"6\""|"100 NB"|"DN 100"|null>,
  "size_type": <"NPS"|"NB"|"DN"|"OD_ID"|"UNKNOWN">,
  "od_mm": <number|null>,
  "id_mm": <number|null>,
  "rating": <"150#"|"300#"|"600#"|"900#"|"1500#"|"2500#"|"PN 6"|"PN 10"|"PN 16"|"PN 25"|"PN 40"|"PN 63"|null>,
  "gasket_type": <"SOFT_CUT"|"SPIRAL_WOUND"|"RTJ"|"KAMM"|"DJI"|"ISK"|"ISK_RTJ">,
  "moc": <material string|null>,
  "face_type": <"RF"|"FF"|null>,
  "thickness_mm": <number|null>,
  "standard": <"ASME B16.20"|"ASME B16.21"|"EN 1514-1"|"EN 1514-2"|"API 6A"|null>,
  "special": <notes or special requirements|null>,
  "confidence": <"HIGH"|"MEDIUM"|"LOW">,
  "sw_winding_material": <"SS316"|"SS304"|"SS316L"|"INCONEL 625"|null>,
  "sw_filler": <"GRAPHITE"|"PTFE"|"FLEXIBLE GRAPHITE"|null>,
  "sw_inner_ring": <"SS316"|"SS304"|"CS"|null>,
  "sw_outer_ring": <"CS"|"SS304"|"SS316"|null>,
  "rtj_groove_type": <"OCT"|"OVAL"|null>,
  "rtj_hardness_bhn": <number|null>,
  "ring_no": <"R-24"|"BX-155"|"RX-53"|null>,
  "kamm_core_material": <"SS316"|"CS"|"ALLOY 625"|null>,
  "kamm_surface_material": <"GRAPHITE"|"PTFE"|"MICA"|null>,
  "kamm_covering_layer": <"GRAPHITE"|"PTFE"|"MICA"|"NON ASBESTOS"|null>,
  "kamm_rib": <"WITH RIB"|"WITHOUT RIB"|null>,
  "kamm_core_thk": <number|null>,
  "kamm_integral_outer_ring": <"INTEGRAL"|null>,
  "dji_filler": <"GRAPHITE"|"ASBESTOS FREE"|null>,
  "dji_rib": <"WITH RIB"|"WITHOUT RIB"|null>,
  "dji_face_type": <"RF"|"FF"|null>,
  "dji_id_first": <true|false>,
  "isk_style": <"STYLE-CS"|"STYLE-N"|"FCS"|"TYPE-E"|"TYPE-F"|"TYPE-D"|null>,
  "isk_type": <"TYPE-E"|"TYPE-F"|"TYPE-D"|null>,
  "isk_fire_safety": <"FIRE SAFE"|"NON FIRE SAFE"|null>,
  "isk_gasket_material": <"GRE G10"|"GRE G11"|"PTFE"|"PEEK"|"Mica"|null>,
  "isk_core_material": <"SS316"|"CS"|"DUPLEX"|"UNS S32760"|"INC 625"|null>,
  "isk_sleeve_material": <"GRE G10"|"PTFE"|"Mylar"|null>,
  "isk_washer_material": <"Zinc Plated CS"|"SS316"|"MS"|null>,
  "isk_primary_seal": <"Viton O-ring"|"PTFE Spring Energised"|"Graphite"|"EPDM O-ring"|null>,
  "isk_secondary_seal": <"Mica"|"Graphite"|null>,
  "isk_insulating_washer": <"G10"|"G11"|"Mica"|"Mylar"|null>,
  "is_gasket": <true|false>
}

## FIELD RULES

raw_description: Copy verbatim from the document. For structured Excel rows, join all relevant cells.

size & size_type:
- NPS inch: size="6\"", size_type="NPS"
- NB metric nominal bore: size="100 NB", size_type="NB"
- DN: size="DN 100", size_type="DN"
- OD/ID dimensions: od_mm=372.0, id_mm=315.0, size_type="OD_ID", size=null
- Mixed fractions: "1 1/2" or "1.5" → size="1-1/2\"", size_type="NPS"

rating: "Class 150"→"150#", "CL300"→"300#", "PN10"→"PN 10", "PN-16"→"PN 16".
Valid ASME classes: 150, 300, 600, 900, 1500, 2500.

gasket_type keywords:
- SPIRAL_WOUND: "spiral wound", "SPW", "SW gasket", winding/inner ring/outer ring
- RTJ: "RTJ", "ring type joint", "ring joint", "R-XX", "OVAL ring", "OCTAGONAL"
- KAMM: "kammprofile", "cam profile", "KAMM", grooved metal
- DJI: "double jacket", "double jacketed", "DJI"
- ISK: "insulating gasket", "insulation kit", "ISK", "flange isolation"
- ISK_RTJ: ISK + RTJ in same item
- SOFT_CUT: everything else (rubber, PTFE, CNAF, neoprene, EPDM, graphite sheet, etc.)

moc rules:
- SOFT_CUT: material of gasket (CNAF, EPDM, PTFE, NEOPRENE, GRAPHITE, VITON, etc.)
- RTJ: ring material (SOFT IRON→"SOFTIRON", SS316, INCONEL 625)
- SPIRAL_WOUND/KAMM/DJI: moc must be null; use type-specific sub-fields instead
- RUBBER without specific type: moc=null, special="MOC ambiguous — confirm rubber type"

Material normalization: 304SS→SS304, 316SS→SS316, CARBON STEEL/MS→CS, SOFT IRON→SOFTIRON

face_type: RF/FF for SOFT_CUT and ISK only. Null for SW, RTJ, KAMM, DJI.

uom: "M" if unit is meters (sheet supply). "NOS" for pieces/sets/units.

confidence:
- HIGH: gasket_type specific AND size AND rating AND (moc OR material fields) all found
- MEDIUM: one critical field missing
- LOW: two or more missing, or gasket_type defaulted to SOFT_CUT without clear type keywords

## is_gasket FIELD — CRITICAL
Set is_gasket=true ONLY for items that are gaskets or gasket kits. Set is_gasket=false for everything else.

Gasket products (is_gasket=true):
- Flat ring gaskets, sheet gaskets (soft cut, CNAF, PTFE, rubber, neoprene, graphite, etc.)
- Spiral wound gaskets
- Ring type joint (RTJ) rings
- Kammprofile gaskets
- Double jacket gaskets
- Flange insulation kits / insulating gasket kits (ISK) — even though they are "kits", they contain the gasket

NOT gaskets (is_gasket=false — include in output but mark false so caller can filter):
- Cam & groove couplings, hose couplings, adapters, plugs
- Bolts, studs, nuts, fasteners
- Flanges, pipes, fittings, valves
- Gasket cements, coatings, tapes
- Packing, mechanical seals, O-rings (standalone, not part of an ISK)
- Administrative rows: totals, headers, notes, project descriptions, contact info

## CRITICAL RULES
1. One object per physical line item — include ALL items (gaskets and non-gaskets), but set is_gasket correctly.
2. raw_description must be verbatim from source — never paraphrase or clean it.
3. null for all fields not applicable to this gasket type.
4. SPIRAL_WOUND: moc must be null; winding metal goes in sw_winding_material.
5. Do NOT invent values not present in the source text.
6. Skip only administrative rows: page headers, column headers, totals rows, blank rows.
7. If quantity or line_no is absent, use null — do not guess.

## EXAMPLES

Example 1 — SOFT_CUT ambiguous rubber:
Input row: "1  Gasket - Rubber - 6'' PN10  27  m"
{"line_no":1,"quantity":27,"uom":"M","raw_description":"Gasket - Rubber - 6'' PN10","size":"6\"","size_type":"NPS","od_mm":null,"id_mm":null,"rating":"PN 10","gasket_type":"SOFT_CUT","moc":null,"face_type":null,"thickness_mm":null,"standard":null,"special":"MOC ambiguous — confirm rubber type","confidence":"LOW","sw_winding_material":null,"sw_filler":null,"sw_inner_ring":null,"sw_outer_ring":null,"rtj_groove_type":null,"rtj_hardness_bhn":null,"ring_no":null,"kamm_core_material":null,"kamm_surface_material":null,"kamm_covering_layer":null,"kamm_rib":null,"kamm_core_thk":null,"kamm_integral_outer_ring":null,"dji_filler":null,"dji_rib":null,"dji_face_type":null,"dji_id_first":false,"isk_style":null,"isk_type":null,"isk_fire_safety":null,"isk_gasket_material":null,"isk_core_material":null,"isk_sleeve_material":null,"isk_washer_material":null,"isk_primary_seal":null,"isk_secondary_seal":null,"isk_insulating_washer":null}

Example 2 — SPIRAL_WOUND:
Input row: "6\" Spiral Wound SS316 Winding GRAPHITE Filler SS316 IR CS OR 900# ASME B16.20"
{"line_no":null,"quantity":null,"uom":"NOS","raw_description":"6\" Spiral Wound SS316 Winding GRAPHITE Filler SS316 IR CS OR 900# ASME B16.20","size":"6\"","size_type":"NPS","od_mm":null,"id_mm":null,"rating":"900#","gasket_type":"SPIRAL_WOUND","moc":null,"face_type":null,"thickness_mm":null,"standard":"ASME B16.20","special":null,"confidence":"HIGH","sw_winding_material":"SS316","sw_filler":"GRAPHITE","sw_inner_ring":"SS316","sw_outer_ring":"CS","rtj_groove_type":null,"rtj_hardness_bhn":null,"ring_no":null,"kamm_core_material":null,"kamm_surface_material":null,"kamm_covering_layer":null,"kamm_rib":null,"kamm_core_thk":null,"kamm_integral_outer_ring":null,"dji_filler":null,"dji_rib":null,"dji_face_type":null,"dji_id_first":false,"isk_style":null,"isk_type":null,"isk_fire_safety":null,"isk_gasket_material":null,"isk_core_material":null,"isk_sleeve_material":null,"isk_washer_material":null,"isk_primary_seal":null,"isk_secondary_seal":null,"isk_insulating_washer":null}

Example 3 — RTJ:
Input row: "RING JOINT GASKET 6in R46 OCTAGONAL 1500lb ASME B16.20 INCONEL 625"
{"line_no":null,"quantity":null,"uom":"NOS","raw_description":"RING JOINT GASKET 6in R46 OCTAGONAL 1500lb ASME B16.20 INCONEL 625","size":"6\"","size_type":"NPS","od_mm":null,"id_mm":null,"rating":"1500#","gasket_type":"RTJ","moc":"INCONEL 625","face_type":null,"thickness_mm":null,"standard":"ASME B16.20","special":null,"confidence":"HIGH","sw_winding_material":null,"sw_filler":null,"sw_inner_ring":null,"sw_outer_ring":null,"rtj_groove_type":"OCT","rtj_hardness_bhn":null,"ring_no":"R-46","kamm_core_material":null,"kamm_surface_material":null,"kamm_covering_layer":null,"kamm_rib":null,"kamm_core_thk":null,"kamm_integral_outer_ring":null,"dji_filler":null,"dji_rib":null,"dji_face_type":null,"dji_id_first":false,"isk_style":null,"isk_type":null,"isk_fire_safety":null,"isk_gasket_material":null,"isk_core_material":null,"isk_sleeve_material":null,"isk_washer_material":null,"isk_primary_seal":null,"isk_secondary_seal":null,"isk_insulating_washer":null}
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
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
    parts = []
    total_rows = 0
    was_truncated = False

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheet_rows = []
        for row in ws.iter_rows(values_only=True):
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
        text = str(source)
        if len(text) > 40000:
            text = text[:40000]
            metadata['was_truncated'] = True
        metadata['char_count'] = len(text)
        return text, metadata

    elif source_type == 'excel':
        text, was_truncated, row_count = _excel_to_text(source, max_rows=300)
        if len(text) > 40000:
            text = text[:40000]
            was_truncated = True
        metadata['char_count'] = len(text)
        metadata['was_truncated'] = was_truncated
        metadata['row_count'] = row_count
        return text, metadata

    elif source_type == 'pdf':
        text = extract_text_from_pdf(source)
        if not text.strip():
            raise SmartParseError(
                'PDF has no extractable text — it appears to be a scanned image. '
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

def _validate_and_normalize_output(raw_items: list) -> list[dict]:
    """Coerce GPT-4o output list to the exact schema rules.py expects."""
    if not isinstance(raw_items, list):
        raise SmartParseError(f'LLM output is not a list (got {type(raw_items).__name__})')
    if len(raw_items) == 0:
        raise SmartParseError('LLM returned empty list — no gasket line items found in document')

    result = []
    skipped_non_gasket = 0
    for i, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            logger.warning(f'Smart Parse: item {i} is not a dict — skipping')
            continue

        # Filter out non-gasket items before any further processing
        is_gasket_val = raw.get('is_gasket', True)
        if is_gasket_val is False or str(is_gasket_val).lower() == 'false':
            desc_preview = str(raw.get('raw_description', ''))[:60]
            logger.info(f'Smart Parse: skipping non-gasket item — {desc_preview}')
            skipped_non_gasket += 1
            continue

        # Start from template, overlay LLM values for known fields
        item: dict = dict(_ITEM_TEMPLATE)
        for k, v in raw.items():
            if k in _ITEM_TEMPLATE:
                item[k] = v

        # Normalize string "null"/"none"/"" → actual None (except sentinel fields)
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
            f'(cam & groove, fittings, etc.) — {len(result)} gasket item(s) remain'
        )

    return result, skipped_non_gasket


# ---------------------------------------------------------------------------
# GPT-4o call
# ---------------------------------------------------------------------------

def _call_gpt4o(openai_client, document_text: str, source_type: str) -> list[dict]:
    """
    Single GPT-4o call. Returns list of item dicts.
    Raises SmartParseError with a specific, actionable message on failure.
    """
    # Check Redis cache first
    r = _get_redis_smart()
    cache_key = _smart_cache_key(document_text)
    if r:
        try:
            hit = r.get(cache_key)
            if hit:
                cached = json.loads(hit)
                logger.info(f'Smart Parse: cache hit ({len(cached)} items)')
                return cached
        except Exception:
            pass

    user_msg = (
        f'Document type: {source_type}\n\n'
        f'--- DOCUMENT CONTENT START ---\n'
        f'{document_text}\n'
        f'--- DOCUMENT CONTENT END ---\n\n'
        f'Extract all gasket line items and return {{"items": [...]}}. '
        f'Include every schema field in each item.'
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
            max_tokens=16000,
        )
    except Exception as e:
        err = str(e)
        if 'rate_limit' in err.lower() or '429' in err:
            raise SmartParseError(
                'OpenAI rate limit reached — too many requests. '
                'Wait 60 seconds then try again, or switch to Classic mode.'
            )
        if 'authentication' in err.lower() or '401' in err or 'invalid api key' in err.lower():
            raise SmartParseError(
                'Invalid OpenAI API key. Check that the key in the sidebar starts with "sk-" '
                'and has not expired.'
            )
        if 'timeout' in err.lower() or 'timed out' in err.lower():
            raise SmartParseError(
                'GPT-4o call timed out after 180 seconds. The document may be too long. '
                'Try reducing the file to 50 items or fewer, or switch to Classic mode.'
            )
        if 'connection' in err.lower() or 'network' in err.lower():
            raise SmartParseError(
                f'Network error reaching OpenAI API: {err}. '
                'Check your internet connection and try again.'
            )
        raise SmartParseError(f'GPT-4o API call failed: {err}')

    choice = response.choices[0]
    if choice.finish_reason == 'length':
        raise SmartParseError(
            'GPT-4o output was cut off because the document produced too many line items. '
            'Split the Excel/email into two parts (e.g. rows 1–50 and 51–100) '
            'and process each separately.'
        )

    raw_content = choice.message.content or '{}'
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise SmartParseError(
            f'GPT-4o returned malformed JSON (rare — usually fixed by retrying): {e}'
        )

    # Unwrap: handle {"items": [...]}, {"gaskets": [...]}, or bare [...]
    if isinstance(parsed, list):
        items_list = parsed
    elif isinstance(parsed, dict):
        items_list = None
        for v in parsed.values():
            if isinstance(v, list):
                items_list = v
                break
        if items_list is None:
            raise SmartParseError(
                f'GPT-4o returned a JSON object but no list of items was found inside it. '
                f'Keys returned: {list(parsed.keys())}. This is unexpected — try again.'
            )
    else:
        raise SmartParseError(
            f'GPT-4o returned an unexpected response structure '
            f'(expected JSON array, got {type(parsed).__name__}). Try again.'
        )

    result, skipped = _validate_and_normalize_output(items_list)

    # Cache only the gasket items
    if r:
        try:
            r.setex(cache_key, _SMART_CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    logger.info(f'Smart Parse: extracted {len(result)} gasket item(s) from {source_type} ({skipped} non-gasket skipped)')
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
            f'Smart Parse: document truncated{row_info} — '
            f'{metadata["char_count"]:,} chars sent to GPT-4o. '
            f'Consider splitting the file if items are missing.'
        )

    if progress_cb:
        progress_cb(3, 10)

    items, skipped_non_gasket = _call_gpt4o(openai_client, document_text, source_type)

    if progress_cb:
        progress_cb(9, 10)

    if metadata.get('was_truncated') and items:
        items[0]['_doc_was_truncated'] = True

    return items, skipped_non_gasket
