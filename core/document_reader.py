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
_CHUNK_SIZE = 20
_MAX_WORKERS = max(1, int(os.environ.get('SMART_PARSE_MAX_WORKERS', '3')))
_MIN_CALL_INTERVAL_SEC = max(0.0, float(os.environ.get('SMART_PARSE_MIN_CALL_INTERVAL_SEC', '0')))


class SmartParseError(Exception):
    """Raised when Smart Parse cannot complete."""


_SYSTEM_PROMPT = """You are an expert in industrial gasket procurement. Extract EVERY line item from the customer enquiry document and return ONLY valid JSON: {"items": [...]}.

IMPORTANT — Treat every row independently. Do NOT skip rows that look similar to earlier ones. Do NOT collapse or deduplicate. The output must have exactly as many items as gasket rows in the input. Quality must be the same for the last row as the first.

FIELDS per item (omit a field entirely if value is unknown — never output null):
- line_no (int), quantity (number), uom ("NOS" or "M"), raw_description (verbatim copy of input text), is_gasket (bool)
- source_sheet (string), source_row (int), source_index (int) when columns with these names are present
- size (string, keep as found), size_type ("NPS"/"NB"/"DN"/"OD_ID"/"UNKNOWN")
- rating: normalise to "150#"/"300#"/"600#" etc. or "PN 10"/"PN 16" etc.
  Variants: "# 150", "#  300", "CL 150", "Class 300" → "150#", "300#"; "PN16", "PN-16" → "PN 16"
- gasket_type — choose by PHYSICAL CONSTRUCTION described, not by the standard the customer cites (customers often cite the wrong standard):
    * SOFT_CUT — flat sheet cut to shape, single homogeneous material (rubber, CNAF, PTFE, graphite sheet)
    * SPIRAL_WOUND — alternating metal strip wound with soft filler ("spiral wound", "SW", winding + filler mentioned)
    * RTJ — solid metal ring sitting in a groove (ring joint / RJ / RTJ / ring gasket; oval / octagonal / BX profile)
    * KAMM — metal core/insert with thin soft sealing layer on both faces ("kammprofile", "profile gasket … metal core/insert", "grooved metal core")
    * DJI — double-jacketed: metal jacket fully enclosing a soft filler (heat exchanger style)
    * ISK — insulating gasket kit / flange insulation kit (includes sleeves, washers, kit components)
- moc — the principal sealing/body material. Populate for EVERY gasket type when the source names a material:
    * SOFT_CUT: the sheet material (EPDM, NEOPRENE, CNAF, PTFE, VITON, NBR, GRAPHITE SHEET, etc.)
    * RTJ: the ring metal verbatim (e.g. "SOFT IRON", "F5", "F11", "F22", "2-1/4 Cr - 1 Mo", "SS316", "INCONEL 625")
    * SPIRAL_WOUND: leave moc blank — materials live in sw_* fields
    * KAMM / DJI: jacket or core metal (e.g. "SS316", "CS"); soft layers go in *_filler / *_surface
    * ISK: gasket material when stated as a single grade (e.g. "G10", "PHENOLIC")
  Unspecified rubber with no clear type → omit moc, set special="MOC ambiguous - confirm rubber type"
- face_type: "RF" or "FF" — for SOFT_CUT and ISK only
- thickness_mm (number): default 3 for SOFT_CUT, 4.5 for SPIRAL_WOUND if not stated
- standard — this is the GASKET standard, not the flange standard. The two are different:
    * Real gasket standards: ASME B16.20 (metallic — SW/RTJ/jacketed), ASME B16.21 (non-metallic soft cut), API 6A (BX/R/RX wellhead rings), EN 1514-1..8, DIN 2690..2698, JIS B 2404
    * Flange standards (NOT gasket standards — ignore as the `standard`): ASME B16.5, ASME B16.47, API 6B, API 6BX, API 17D
    * If customer cites API 6B / API 6BX (flange type) for an RTJ → the gasket standard is API 6A
    * If customer cites ASME B16.5 (flange std) for a SW/RTJ → the gasket standard is ASME B16.20
    * If the customer cites a real gasket standard, use it verbatim. If they cite BOTH (e.g. "ASME B16.20 (ASME B16.47 SR A)" or "ASME B16.20 / ASME B16.47 Series A") preserve the SR/Series A annotation in the standard string — it tells GGPL the flange is a large-bore B16.47 type.
    * If no real gasket standard is cited, default: SOFT_CUT # → ASME B16.21 (≥26" → ASME B16.47); SOFT_CUT PN → EN 1514-1; SPW/RTJ → ASME B16.20
- od_mm, id_mm (numbers): only when value is already given in mm. Otherwise leave both blank and put the OD/ID exactly as written (any unit — inches, feet-inches, fractions) into `size`, with size_type="OD_ID". Code will handle unit conversion.
- special: genuine technical notes only (NACE MR0175, fire-safe, food-grade, oxygen service, certifications such as "NSF 61/ANSI 61-G", customer-side modifiers such as "MODIFIED" / "with steel insert"). Ignore plant tag numbers, MR / RFQ / PO reference codes, area / unit codes, drawing numbers.

SPIRAL_WOUND — always extract all four material fields when present:
- sw_winding_material: the metal strip (e.g. SS316, SS316L, SS304, INCONEL 625, HASTELLOY C276)
- sw_filler: filler/sealing element (GRAPHITE, FLEXIBLE GRAPHITE, PTFE, MICA, CERAMIC)
- sw_inner_ring: inner ring material if present (e.g. SS316, SS316L, SS304, CS)
- sw_outer_ring: outer centering ring material (e.g. CS, SS304, SS316) — often mandatory
- Pattern hints (general — work in any order/wording): "<metal> + <filler>" or "<metal>/<filler>" = winding/filler; "<material> OUTER" / "OUTER RING <material>" = outer; "<material> INNER" / "INNER RING <material>" = inner. Keep extracting these for every SW row, not just the first.

RTJ:
- ring_no — ONLY values that start with R- / RX- / BX- followed by digits (e.g. "R-23", "RX-46", "BX-156"). Any other token (E2E, D2A, A1A, area codes, drawing refs) is NOT a ring number — leave ring_no blank.
- rtj_groove_type — use the literal short code:
    * "OCT"  when source says octagonal / oct / 8-sided / "type O" / R-octagonal
    * "OVL"  when source says oval / elliptical / "type R"
    * "BX"   when source says BX / pressure-energised / "type BX"
    * If only "R" / "ring joint" / "RTJ" is stated with no profile, omit rtj_groove_type
- rtj_hardness_bhn (number) — only when an explicit BHN/HRBW number is in the source. Do NOT guess from material; the code applies material-based defaults afterwards.

KAMM: kamm_core_material, kamm_surface_material (graphite / PTFE / mica covering), kamm_core_thk, kamm_integral_outer_ring (bool)
DJI: dji_filler (soft inner filler), dji_face_type, dji_id_first (true when ID is listed BEFORE OD in input)
ISK: isk_style ("Type-E" full face / "Type-F" raised / "Type-D" RTJ), isk_type, isk_fire_safety, isk_gasket_material, isk_core_material, isk_sleeve_material, isk_washer_material, isk_primary_seal, isk_insulating_washer

NORMALISATION:
- is_gasket=false for bolts, studs, nuts, flanges, fittings, pipes (still include the row)
- Materials — normalise common variants:
    * SS 316 / 316SS / S.S.316 / AISI 316 / TYPE 316 → SS316; 316L variants → SS316L; 304 variants → SS304
    * M.S. / Mild Steel / Carbon Steel / Low Carbon Steel → CS
    * "Soft Iron", "S.I.", "SI" → SOFT IRON
    * Chrome-moly grades — keep both the F-grade AND the composition when both appear, prefer the F-grade alone otherwise: "F5" / "5% Cr - 1/2 Mo" → F5; "F11" / "1-1/4 Cr - 1/2 Mo" → F11; "F22" / "2-1/4 Cr - 1 Mo" → F22; "F91" / "9% Cr 1 Mo V" → F91
    * Duplex / 2205 / S31803 → UNS S31803; Super Duplex / 2507 / S32750 → UNS S32750
    * INCONEL X / INCOLOY X / HASTELLOY X / MONEL X — keep as stated; normalise to UPPERCASE with grade
- Ignore plant area tags, line numbers, equipment tags, MR / RFQ / PO references, drawing numbers — they are not materials, sizes, or ring numbers
- uom "M" (metres) = sheet / roll supply, not individual gaskets

REPETITION DISCIPLINE:
- The document may contain many rows with nearly-identical descriptions differing only in size or rating. Extract every one as a separate item with its own size and rating.
- Do NOT carry forward fields from a previous row by assumption — read every row's text on its own.
- Material/filler fields stay fully populated for every spiral wound / kammprofile / DJI / ISK row, even when the source repeats the same construction for dozens of rows.
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


def _excel_to_text(excel_bytes: bytes, max_rows: int | None = None) -> tuple[str, bool, int]:
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

        # Remove fully-empty rows, preserving the original 0-based Excel row index.
        df = df[df.apply(lambda r: any(c for c in r), axis=1)]
        if df.empty:
            continue

        # Detect header row: first row with ≥3 non-empty cells
        header_idx = df.index[0]
        for i, row in df.iterrows():
            if sum(1 for c in row if c) >= 3:
                header_idx = i
                break

        df.columns = df.loc[header_idx].tolist()
        df = df[df.index > header_idx].copy()

        # Drop columns where >95% of values are empty. Keep sparse but meaningful
        # columns such as MOC, remarks, ring material, or drawing references.
        min_fill = max(1, int(len(df) * 0.05))
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
        df = df[df.apply(lambda r: any(c for c in r), axis=1)]
        if df.empty:
            continue

        # Optional explicit row cap for callers that need one; default is no cap.
        if max_rows is not None:
            remaining = max_rows - total_rows
            if remaining <= 0:
                was_truncated = True
                break
            if len(df) > remaining:
                df = df.iloc[:remaining]
                was_truncated = True

        total_rows += len(df)

        df = df.copy()
        df.insert(0, 'source_index', range(total_rows - len(df) + 1, total_rows + 1))
        df.insert(0, 'source_row', [int(idx) + 1 for idx in df.index])
        df.insert(0, 'source_sheet', sheet_name)

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
        text, was_truncated, row_count = _excel_to_text(source, max_rows=None)
        text = _sanitize_text(text)
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

    # Excel: markdown table format. Chunk each sheet independently and repeat
    # that sheet's marker/header/separator in every chunk.
    chunks: list[str] = []
    sheet_marker: str | None = None
    header: str | None = None
    separator: str | None = None
    data_lines: list[str] = []

    def _flush_sheet() -> None:
        if not (sheet_marker and header and separator and data_lines):
            return
        prefix = '\n'.join([sheet_marker, header, separator])
        for j in range(0, len(data_lines), chunk_size):
            chunks.append(prefix + '\n' + '\n'.join(data_lines[j:j + chunk_size]))

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('=== Sheet:'):
            _flush_sheet()
            sheet_marker = line
            header = lines[i + 1] if i + 1 < len(lines) else None
            separator = lines[i + 2] if i + 2 < len(lines) else None
            data_lines = []
            i += 3
        else:
            if line.strip():
                data_lines.append(line)
            i += 1
    _flush_sheet()
    return chunks or [document_text]


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
    r'(\d+)\s*[\'`]\s*-?\s*(\d+)(?:\s+(\d+)\s*/\s*(\d+))?\s*"?'
)
_IN_RE = re.compile(r'(\d+)(?:\s+(\d+)\s*/\s*(\d+))?\s*"')
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
    """Simple fallback to extract od_mm/id_mm when the LLM leaves them blank."""
    if not size_str:
        return None, None
    s = str(size_str)

    labeled_patterns = [
        (
            r'O\.?D\.?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?\b.*?'
            r'I\.?D\.?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?\b',
            False,
        ),
        (
            r'I\.?D\.?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?\b.*?'
            r'O\.?D\.?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?\b',
            True,
        ),
        (
            r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*O\.?D\.?\b.*?'
            r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*I\.?D\.?\b',
            False,
        ),
        (
            r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*I\.?D\.?\b.*?'
            r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*O\.?D\.?\b',
            True,
        ),
    ]
    for pattern, reversed_order in labeled_patterns:
        m = re.search(pattern, s, re.I)
        if m:
            first, second = float(m.group(1)), float(m.group(2))
            return (second, first) if reversed_order else (first, second)

    def _find(label: str) -> float | None:
        # label before number: "OD 584MM", "OD: 48"
        m = re.search(rf'{label}\s*[:\s]\s*(\d+(?:\.\d+)?)', s, re.I)
        if m:
            return float(m.group(1))
        # number before label: "48 MM OD", "48.5OD"
        m = re.search(rf'(\d+(?:\.\d+)?)\s*(?:mm)?\s*{label}', s, re.I)
        if m:
            return float(m.group(1))
        return None

    od = _find(r'O\.?D\.?')
    id_ = _find(r'I\.?D\.?')
    if od is not None and id_ is not None:
        return od, id_
    return None, None


_GASKET_TYPE_ALIASES = {
    'SOFTCUT': 'SOFT_CUT',
    'SOFT CUT': 'SOFT_CUT',
    'SOFT_CUT': 'SOFT_CUT',
    'NON METALLIC': 'SOFT_CUT',
    'NON-METALLIC': 'SOFT_CUT',
    'SPIRAL': 'SPIRAL_WOUND',
    'SPIRAL WOUND': 'SPIRAL_WOUND',
    'SPIRAL_WOUND': 'SPIRAL_WOUND',
    'SW': 'SPIRAL_WOUND',
    'SPW': 'SPIRAL_WOUND',
    # Full-label variants the LLM sometimes returns verbatim from source text
    'SPIRAL WOUND GASKET': 'SPIRAL_WOUND',
    'SPIRAL WOUND METALLIC GASKET': 'SPIRAL_WOUND',
    'METALLIC SPIRAL WOUND GASKET': 'SPIRAL_WOUND',
    'SPIRALLY WOUND': 'SPIRAL_WOUND',
    # Common typos
    'SPRIAL WOUND': 'SPIRAL_WOUND',
    'SPRIAL WOUND GASKET': 'SPIRAL_WOUND',
    'SPRIRAL WOUND': 'SPIRAL_WOUND',
    'SPRIRAL WOUND GASKET': 'SPIRAL_WOUND',
    'RTJ': 'RTJ',
    'RING JOINT': 'RTJ',
    'RING_JOINT': 'RTJ',
    'RING TYPE JOINT': 'RTJ',
    'RING TYPE JOINT GASKET': 'RTJ',
    'RTJ GASKET': 'RTJ',
    'METALLIC RING JOINT': 'RTJ',
    'KAMM': 'KAMM',
    'KAMMPROFILE': 'KAMM',
    'CAMPROFILE': 'KAMM',
    'KAMMPROFILE GASKET': 'KAMM',
    'CAMPROFILE GASKET': 'KAMM',
    'DJI': 'DJI',
    'DOUBLE JACKET': 'DJI',
    'DOUBLE JACKETED': 'DJI',
    'DOUBLE_JACKETED': 'DJI',
    'DOUBLE JACKETED GASKET': 'DJI',
    'ISK': 'ISK',
    'INSULATING GASKET KIT': 'ISK',
    'FLANGE INSULATION KIT': 'ISK',
    'ISK_RTJ': 'ISK_RTJ',
}

_SIZE_TYPE_ALIASES = {
    'NPS': 'NPS',
    'INCH': 'NPS',
    'IN': 'NPS',
    'NB': 'NB',
    'DN': 'DN',
    'OD_ID': 'OD_ID',
    'OD/ID': 'OD_ID',
    'OD-ID': 'OD_ID',
    'CUSTOM': 'OD_ID',
    'UNKNOWN': 'UNKNOWN',
}


def _normalise_enum(value: object, aliases: dict[str, str], default: str) -> str:
    if value is None:
        return default
    key = re.sub(r'[\s\-]+', ' ', str(value).strip().upper()).replace(' ', '_')
    if key in aliases:
        return aliases[key]
    key_space = key.replace('_', ' ')
    return aliases.get(key_space, default)


def _normalise_uom(value: object) -> str:
    if value is None:
        return 'NOS'
    uom = str(value).strip().upper()
    if uom in ('M', 'MTR', 'MTRS', 'METER', 'METERS', 'METRE', 'METRES'):
        return 'M'
    return 'NOS'


def _looks_like_nominal_size(size_text: str) -> bool:
    return bool(re.search(r'["\']|\b(?:NPS|NB|DN|INCH|IN)\b', size_text, re.IGNORECASE))


def _infer_size_type(item: dict) -> str:
    current = _normalise_enum(item.get('size_type'), _SIZE_TYPE_ALIASES, 'UNKNOWN')
    size_text = str(item.get('size') or '')
    raw_text = str(item.get('raw_description') or '')

    if item.get('od_mm') is not None and item.get('id_mm') is not None and not size_text:
        return 'OD_ID'

    if current == 'OD_ID':
        if item.get('od_mm') is not None and item.get('id_mm') is not None:
            return 'OD_ID'
        if _looks_like_nominal_size(size_text):
            return 'NPS'
        return 'UNKNOWN'

    if current != 'UNKNOWN':
        return current

    if re.search(r'\bO\.?D\.?\b|\bI\.?D\.?\b', size_text + ' ' + raw_text, re.IGNORECASE):
        if item.get('od_mm') is not None and item.get('id_mm') is not None and not _looks_like_nominal_size(size_text):
            return 'OD_ID'
    if re.search(r'\bDN\b', size_text, re.IGNORECASE):
        return 'DN'
    if re.search(r'\bNB\b', size_text, re.IGNORECASE):
        return 'NB'
    if _looks_like_nominal_size(size_text):
        return 'NPS'
    return 'UNKNOWN'


def _normalise_llm_item_shape(item: dict) -> None:
    """Coerce variable LLM JSON into the stable internal schema."""
    if not item.get('raw_description'):
        item['raw_description'] = item.get('description') or ''

    item['gasket_type'] = _normalise_enum(item.get('gasket_type'), _GASKET_TYPE_ALIASES, 'SOFT_CUT')
    item['uom'] = _normalise_uom(item.get('uom'))
    item['size_type'] = _infer_size_type(item)

    if item.get('rtj_groove_type'):
        groove = str(item['rtj_groove_type']).strip().upper()
        item['rtj_groove_type'] = {'OVL': 'OVAL', 'OCT': 'OCTAGONAL'}.get(groove, groove)

    for key in (
        'moc', 'sw_winding_material', 'sw_filler', 'sw_inner_ring', 'sw_outer_ring',
        'kamm_core_material', 'kamm_surface_material', 'dji_filler',
        'isk_gasket_material', 'isk_core_material', 'isk_sleeve_material',
        'isk_washer_material', 'isk_primary_seal', 'isk_insulating_washer',
    ):
        if isinstance(item.get(key), str):
            item[key] = re.sub(r'\s+', ' ', item[key]).strip().upper()


def _normalize_items(raw_items: list) -> tuple[list[dict], int]:
    """Coerce raw LLM output to the schema that rules.py expects."""
    KEEP_AS_STRING = {'uom', 'raw_description', 'gasket_type', 'size_type', 'confidence', 'source_sheet'}
    FLOAT_FIELDS = ('od_mm', 'id_mm', 'thickness_mm', 'rtj_hardness_bhn', 'kamm_core_thk', 'quantity')
    INT_FIELDS = ('line_no', 'source_row', 'source_index')
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

        # Fill od_mm/id_mm from `size` (or raw_description as last resort) when LLM left them blank.
        # Also handles cases where LLM returned od_mm/id_mm as strings-with-units that failed float coercion.
        raw_od, raw_id = _parse_od_id(item.get('raw_description') or '')
        if raw_od is not None and raw_id is not None:
            item['od_mm'] = raw_od
            item['id_mm'] = raw_id

        if item.get('od_mm') is None or item.get('id_mm') is None:
            for _src in (item.get('size') or '', item.get('raw_description') or ''):
                if not _src:
                    continue
                _up = _src.upper()
                if 'OD' in _up or 'I.D' in _up or 'I D' in _up or ('ID' in _up and 'X' in _up):
                    od, id_ = _parse_od_id(_src)
                    if item.get('od_mm') is None and od is not None:
                        item['od_mm'] = od
                    if item.get('id_mm') is None and id_ is not None:
                        item['id_mm'] = id_
                if item.get('od_mm') is not None and item.get('id_mm') is not None:
                    break

        # The LLM sometimes marks plain NPS inch sizes such as `6"` as OD_ID
        # because the prompt discusses OD/ID handling. If no OD/ID dimensions
        # were actually extracted and the size is a normal nominal pipe size,
        # reset the type so rules.py validates size/rating/moc instead.
        if (
            str(item.get('size_type') or '').upper() == 'OD_ID'
            and item.get('od_mm') is None
            and item.get('id_mm') is None
        ):
            size_text = str(item.get('size') or '')
            if re.search(r'["\']|\b(?:NPS|NB|DN)\b', size_text, re.IGNORECASE):
                item['size_type'] = 'NPS'

        if not item.get('gasket_type'):
            item['gasket_type'] = 'SOFT_CUT'
        if not item.get('size_type'):
            item['size_type'] = 'UNKNOWN'
        if not item.get('confidence'):
            item['confidence'] = 'MEDIUM'

        for f in UPPER_FIELDS:
            if isinstance(item.get(f), str):
                item[f] = item[f].strip().upper()

        _normalise_llm_item_shape(item)

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

    raw_by_chunk: dict[int, list[dict]] = {}
    failures: list[dict] = []
    done_count = 0
    lock = threading.Lock()
    call_lock = threading.Lock()
    last_call_at = [0.0]

    def _process(idx_chunk):
        import time as _time
        idx, chunk = idx_chunk
        logger.info(f'Smart Parse: chunk {idx}/{len(chunks)}...')
        for attempt in range(3):
            try:
                with call_lock:
                    if last_call_at[0] and _MIN_CALL_INTERVAL_SEC:
                        elapsed = _time.monotonic() - last_call_at[0]
                        if elapsed < _MIN_CALL_INTERVAL_SEC:
                            _time.sleep(_MIN_CALL_INTERVAL_SEC - elapsed)
                    last_call_at[0] = _time.monotonic()
                raw = _call_single_chunk(openai_client, chunk, source_type)
                logger.info(f'Smart Parse: chunk {idx} done — {len(raw)} item(s)')
                return idx, raw, None
            except SmartParseError as e:
                err = str(e).lower()
                if any(fatal in err for fatal in ('invalid openai api key', 'account quota exceeded', 'api key contains')):
                    raise
                if 'rate limit' in err and attempt < 2:
                    wait = 30 * (attempt + 1)
                    logger.warning(f'Smart Parse: chunk {idx} rate limited, waiting {wait}s...')
                    _time.sleep(wait)
                elif attempt < 2:
                    wait = 5 * (attempt + 1)
                    logger.warning(f'Smart Parse: chunk {idx} failed, retry {attempt + 1} in {wait}s: {e}')
                    _time.sleep(wait)
                else:
                    logger.error(f'Smart Parse: chunk {idx} failed permanently: {e}')
                    return idx, [], str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {
            executor.submit(_process, (i, chunk)): i
            for i, chunk in enumerate(chunks, 1)
        }
        for future in concurrent.futures.as_completed(futures):
            chunk_idx, chunk_raw, chunk_error = future.result()
            with lock:
                if chunk_error:
                    failures.append({'chunk': chunk_idx, 'error': chunk_error})
                else:
                    raw_by_chunk[chunk_idx] = chunk_raw
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

    all_raw: list[dict] = []
    for idx in sorted(raw_by_chunk):
        all_raw.extend(raw_by_chunk[idx])

    if failures and not all_raw:
        detail = '; '.join(f'chunk {f["chunk"]}: {f["error"]}' for f in failures[:3])
        raise SmartParseError(f'All {len(chunks)} Smart Parse chunk(s) failed. {detail}')

    result, skipped = _normalize_items(all_raw)
    if failures and result:
        result[0]['_smart_parse_partial'] = True
        result[0]['_smart_parse_failed_chunks'] = failures
        result[0]['_smart_parse_total_chunks'] = len(chunks)

    if r and not failures:
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
    if metadata.get('row_count') and items:
        items[0]['_doc_row_count'] = metadata['row_count']

    return items, skipped
