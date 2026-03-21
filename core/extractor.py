from __future__ import annotations
"""
Extracts structured gasket fields from raw description strings.
Primary: LLM (Groq API). Fallback: regex-based extraction.
"""
import os
import re
import json
import time
import logging

logger = logging.getLogger(__name__)

_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    api_key = os.environ.get('GROQ_API_KEY') or _get_streamlit_secret('GROQ_API_KEY')
    if not api_key:
        return None
    try:
        from groq import Groq
        _groq_client = Groq(api_key=api_key, timeout=10.0)
        return _groq_client
    except Exception:
        return None

_FIELD_SCHEMA = """{
  "size": "e.g. 2\\" or OD 584MM or null",
  "size_type": "NPS | NB | OD_ID | UNKNOWN",
  "od_mm": null,
  "id_mm": null,
  "rating": "e.g. 150# or PN 10 or null",
  "gasket_type": "SOFT_CUT | SPIRAL_WOUND | RTJ | KAMM | DJI | ISK | ISK_RTJ",
  "moc": "normalized material name or null (leave null for spiral wound — built from sw_* fields)",
  "face_type": "RF | FF | null",
  "thickness_mm": 3,
  "standard": "ASME B16.21 | ASME B16.20 | EN 1514-1 | other | null",
  "special": "any special requirements e.g. FOOD GRADE or null",
  "sw_winding_material": "e.g. SS304 | SS316 | null (spiral wound only)",
  "sw_filler": "e.g. GRAPHITE | PTFE | MICA | null (spiral wound only)",
  "sw_inner_ring": "e.g. SS304 | CS | null (spiral wound only)",
  "sw_outer_ring": "e.g. CS | SS304 | null (spiral wound only)",
  "rtj_groove_type": "OCT | OVAL | null (RTJ only)",
  "rtj_hardness_bhn": "e.g. 90 | 130 | 160 | null (RTJ only — BHN hardness number)",
  "confidence": "HIGH | MEDIUM | LOW"
}"""

_BATCH_SIZE = 8  # descriptions per LLM call

_BATCH_SYSTEM_PROMPT = f"""You are a gasket specification extraction assistant for an oil & gas company.
Extract gasket specs from customer descriptions and return ONLY valid JSON.

Handle gasket types:
1. SOFT_CUT: flat ring (RF/FF), materials like CNAF, PTFE, NEOPRENE, EPDM, NATURAL RUBBER, GRAPHITE, VITON, NON ASBESTOS
2. SPIRAL_WOUND: metallic wound gasket, typically with graphite/PTFE filler and centering/inner rings
3. RTJ: Ring Type Joint — octagonal or oval metallic ring, e.g. Soft Iron, SS316, Low Carbon Steel
4. KAMM: Kammprofile gasket — serrated metal core with graphite facing; similar ring/filler structure to SW
5. DJI: Double Jacket (Jacketed) gasket — metallic jacket, usually Copper or SS, with graphite fill; dimensions given as ID × OD × THK
6. ISK: Insulating Gasket Kit — GRE (G10) or similar; spec details usually passed through from customer
7. ISK_RTJ: Insulating Gasket Kit for RTJ flanges

You will receive a numbered list of descriptions. Return a JSON object with key "results" containing an array of extractions in the same order.

Each extraction must follow this schema:
{_FIELD_SCHEMA}

Rules:
- size: NPS in inches (e.g. "6\\"") or OD×ID in mm. If NB given, convert: 150NB=6\\", 200NB=8\\", etc.
- rating: use format "150#", "300#", "PN 10", "PN 16"
- gasket_type: SPIRAL_WOUND if description mentions "spiral wound", "SW gasket", winding strip + filler + ring combo
- gasket_type: RTJ if description mentions "ring joint", "RTJ", "ring type joint", "octagonal ring", "oval ring", "ring gasket" with metallic material
- For SPIRAL_WOUND: set sw_winding_material (e.g. SS304), sw_filler (GRAPHITE/PTFE/MICA), sw_outer_ring (e.g. CS), sw_inner_ring if present; leave moc null
- For SOFT_CUT: set moc, leave sw_* and rtj_* fields null
- For RTJ: set moc (e.g. SOFTIRON, SOFTIRON GALVANISED, SS316, LOW CARBON STEEL), rtj_groove_type (OCT or OVAL), rtj_hardness_bhn (90 for soft iron, 120 for LCS, 160 for SS); leave sw_* fields null; standard is ASME B16.20
- Normalize winding materials: "304 SS" / "SS 304" / "304SS" → "SS304"; "316 SS" → "SS316"; "316L SS" → "SS316L"
- Normalize ring materials: "CARBON STEEL" / "MS" / "C.S." → "CS"
- Normalize RTJ MOC: "SOFT IRON" / "SOFTIRON" → "SOFTIRON"; "SOFT IRON GALVANISED" / "GALVANISED SOFT IRON" → "SOFTIRON GALVANISED"; "LOW CARBON STEEL" → "LOW CARBON STEEL"
- face_type: null for spiral wound and RTJ; RF/FF/null for soft cut
- thickness_mm: null for RTJ (rings have no thickness field); extract number for others; null if not stated
- standard: ASME B16.21 for soft cut; ASME B16.20 for spiral wound NPS≤24" and all RTJ; ASME B16.47 for NPS≥26" spiral wound
- special: capture FOOD GRADE, NACE, LETHAL, EIL APPROVED, SERIES B, etc.
- confidence: HIGH if all key fields clear, LOW if ambiguous"""


def extract_batch(items: list[dict], progress_cb=None) -> list[dict]:
    """
    Extract structured fields for all items.
    Deduplicates by description. Regex-first: only sends ambiguous items to LLM,
    in batches to minimise API calls.
    """
    unique_descs_list = list({item['description'] for item in items})
    total = len(unique_descs_list)
    cache = {}
    done = 0

    # Pass 1: regex extraction for all
    needs_llm = []
    for desc in unique_descs_list:
        result = _regex_extract(desc)
        if result['confidence'] == 'HIGH':
            cache[desc] = result
            done += 1
            if progress_cb:
                progress_cb(done, total)
        else:
            needs_llm.append(desc)

    # Pass 2: batch LLM for ambiguous items
    if needs_llm:
        client = _get_groq_client()
        for batch_start in range(0, len(needs_llm), _BATCH_SIZE):
            batch = needs_llm[batch_start:batch_start + _BATCH_SIZE]
            llm_results = _llm_extract_batch(client, batch) if client else [None] * len(batch)
            for desc, llm_result in zip(batch, llm_results):
                cache[desc] = llm_result if llm_result else _regex_extract(desc)
                done += 1
                if progress_cb:
                    progress_cb(done, total)

    results = []
    for item in items:
        extracted = cache[item['description']].copy()
        extracted['quantity'] = item.get('quantity')
        extracted['uom'] = item.get('uom', 'NOS')
        extracted['line_no'] = item.get('line_no')
        extracted['raw_description'] = item['description']
        results.append(extracted)
    return results


def _llm_extract_batch(client, descriptions: list[str]) -> list[dict | None]:
    """Send a batch of descriptions to Groq in one API call. Returns list of dicts (or None on failure)."""
    if not client:
        return [None] * len(descriptions)

    from data.reference_data import select_few_shot_examples
    examples = select_few_shot_examples(descriptions[0], n=4)
    examples_text = '\n'.join(
        f'Input: "{e["input"]}"\nOutput description: "{e["output"]}"'
        for e in examples
    )
    numbered = '\n'.join(f'{i + 1}. "{d}"' for i, d in enumerate(descriptions))
    user_msg = (
        f"Examples of customer→GGPL mappings:\n{examples_text}\n\n"
        f"Now extract fields from each of the following {len(descriptions)} descriptions "
        f"and return {{\"results\": [...]}} with one entry per description in order:\n{numbered}"
    )

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=[
                    {'role': 'system', 'content': _BATCH_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_msg},
                ],
                temperature=0.1,
                response_format={'type': 'json_object'},
                max_tokens=300 * len(descriptions),
            )
            data = json.loads(resp.choices[0].message.content)
            results = data.get('results', [])
            # Pad with None if model returned fewer items than expected
            while len(results) < len(descriptions):
                results.append(None)
            return results[:len(descriptions)]
        except Exception as e:
            msg = str(e)
            if '429' in msg or 'rate_limit' in msg.lower():
                wait = _parse_retry_wait(msg)
                logger.info(f'Rate limited — waiting {wait:.1f}s (attempt {attempt + 1}/3)')
                time.sleep(wait)
            else:
                logger.warning(f'LLM batch extraction failed: {e}')
                return [None] * len(descriptions)
    logger.warning('LLM batch extraction failed after 3 attempts')
    return [None] * len(descriptions)


def _parse_retry_wait(error_msg: str) -> float:
    """Extract the suggested wait time from a Groq 429 error message."""
    m = re.search(r'try again in ([\d.]+)s', error_msg)
    if m:
        return float(m.group(1)) + 0.5  # small buffer
    return 12.0  # safe default


def _get_streamlit_secret(key: str) -> str | None:
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Regex-based fallback extractor
# ---------------------------------------------------------------------------

_SIZE_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:NPS|NB|"|\')?\s*(?:X\s*(?:CL|CLASS|PN|#))?',
    re.IGNORECASE
)
_RATING_PATTERN = re.compile(
    r'(?:CL[-.\s]*|CLASS[-.\s]*)?(\d+)\s*#|(?:PN\s*)(\d+)',
    re.IGNORECASE
)
_THICKNESS_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*MM\s*(?:THK|THICK)',
    re.IGNORECASE
)
_OD_ID_PATTERN = re.compile(
    r'OD\s*[=]?\s*(\d+(?:\.\d+)?)\s*(?:MM)?\s*[Xx×,]?\s*ID\s*[=]?\s*(\d+(?:\.\d+)?)',
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Spiral wound detection & extraction helpers
# ---------------------------------------------------------------------------

_SW_DETECT_PATTERN = re.compile(
    r'\bSPIRAL\s*WOUND\b'                             # explicit "SPIRAL WOUND"
    r'|\bS\.?W\.?\s*GASKET\b'                         # "SW GASKET"
    r'|(?:SS\s*3\d{2}L?|304\s*SS|316\s*SS)\s*\+'     # "304 SS +" shorthand (metal + filler + ring)
    r'|\bWINDING\s*STRIP\b',
    re.IGNORECASE,
)

_RTJ_DETECT_PATTERN = re.compile(
    r'\bRING\s*(?:TYPE\s*)?JOINT\b'                  # "Ring Joint" / "Ring Type Joint"
    r'|\bRTJ\b'                                       # abbreviation
    r'|\bR\.T\.J\b'
    r'|\bOCTAGONAL\s*RING\b'
    r'|\bOVAL\s*RING\b',
    re.IGNORECASE,
)

_KAMM_DETECT_PATTERN = re.compile(
    r'\bKAMM(?:PROFILE|PROFIL)?\b'
    r'|\bCAM\s*PROFILE\b'
    r'|\bSERRATED\s*(?:METAL\s*)?(?:CORE\s*)?GASKET\b',
    re.IGNORECASE,
)

_DJI_DETECT_PATTERN = re.compile(
    r'\bDOUBLE\s*JACKET\b'
    r'|\bDJI\b'
    r'|\bJACKET\s*GASKET\b'
    r'|\bCOPPER\s*JACKET\b',
    re.IGNORECASE,
)

_ISK_DETECT_PATTERN = re.compile(
    r'\bINSULAT(?:ING|ION)\s*GASKET\b'
    r'|\bINSULATING\s*(?:GASKET\s*)?KIT\b'
    r'|\bISK\b'
    r'|\bGSKT\s*INSUL',
    re.IGNORECASE,
)

_SW_WINDING_PATTERN = re.compile(
    r'\b(SS\s*304L?|SS\s*316L?|SS\s*321|SS\s*347|304L?\s*SS|316L?\s*SS|321\s*SS|347\s*SS'
    r'|INCONEL\s*\d*|HASTELLOY\s*[A-Z]\d*|MONEL\s*\d*|DUPLEX|TITANIUM)\b',
    re.IGNORECASE,
)
_SW_FILLER_PATTERN = re.compile(
    r'\b(FLEXIBLE\s+GRAPHITE|GRAPHITE|PTFE|TEFLON|MICA|CERAMIC|MINERAL\s*WOOL)\b',
    re.IGNORECASE,
)
_SW_OUTER_RING_PATTERN = re.compile(
    r'\b(CS|CARBON\s*STEEL|M\.?S\.?|SS\s*304L?|SS\s*316L?|304\s*SS|316\s*SS)\s*(?:OUTER\s*)?(?:CENTERING\s*)?RING\b',
    re.IGNORECASE,
)
_SW_INNER_RING_PATTERN = re.compile(
    r'(?:\bINR\b|\bINNER\s+RING\b|\bINNER\s+CENTERING)\s*[,.]?\s*'
    r'(SS\s*\d{3}L?(?:/\d{3}L?)?|CS|CARBON\s*STEEL|304\s*SS|316\s*SS)',
    re.IGNORECASE,
)

_SW_MATERIAL_NORM = {
    # winding & ring material normalization (uppercase key → canonical)
    'SS304': 'SS304', 'SS 304': 'SS304', '304SS': 'SS304', '304 SS': 'SS304', '304': 'SS304',
    'SS316': 'SS316', 'SS 316': 'SS316', '316SS': 'SS316', '316 SS': 'SS316', '316': 'SS316',
    'SS316L': 'SS316L', 'SS 316L': 'SS316L', '316LSS': 'SS316L', '316L SS': 'SS316L',
    'SS304L': 'SS304L', 'SS 304L': 'SS304L',
    'SS321': 'SS321', 'SS 321': 'SS321', '321 SS': 'SS321',
    'SS347': 'SS347', 'SS 347': 'SS347', '347 SS': 'SS347',
    'CARBON STEEL': 'CS', 'CARBON  STEEL': 'CS', 'MS': 'CS', 'M.S.': 'CS', 'C.S.': 'CS',
    'INCONEL': 'INCONEL 625', 'HASTELLOY': 'HASTELLOY C276', 'MONEL': 'MONEL 400',
}


def _norm_sw_material(raw: str) -> str:
    """Normalize a winding/ring material string to canonical form."""
    key = re.sub(r'\s+', ' ', raw.strip().upper())
    # Try exact lookup first
    if key in _SW_MATERIAL_NORM:
        return _SW_MATERIAL_NORM[key]
    # Remove spaces and try again
    compact = key.replace(' ', '')
    if compact in _SW_MATERIAL_NORM:
        return _SW_MATERIAL_NORM[compact]
    return key


_SW_COMBINED_RING_PATTERN = re.compile(
    r'\b(SS\s*\d{3}L?|\d{3}L?\s*SS|CS|CARBON\s*STEEL|M\.?S\.?)\s+INNER\s*[&/,]\s*OUTER\s*RING\b',
    re.IGNORECASE,
)


def _extract_sw_components(desc: str) -> dict:
    """Extract spiral wound gasket components from description string (uppercase)."""
    winding_mat = None
    m = _SW_WINDING_PATTERN.search(desc)
    if m:
        winding_mat = _norm_sw_material(m.group(1))

    filler = None
    m = _SW_FILLER_PATTERN.search(desc)
    if m:
        filler = re.sub(r'\s+', ' ', m.group(1).upper())  # normalize spaces, keep FLEXIBLE GRAPHITE

    outer_ring = None
    inner_ring = None
    # Check for combined "MATERIAL inner& outer ring" phrasing
    m = _SW_COMBINED_RING_PATTERN.search(desc)
    if m:
        mat = _norm_sw_material(m.group(1))
        inner_ring = mat
        outer_ring = mat
    else:
        m = _SW_OUTER_RING_PATTERN.search(desc)
        if m:
            outer_ring = _norm_sw_material(m.group(1))
        m = _SW_INNER_RING_PATTERN.search(desc)
        if m:
            inner_ring = _norm_sw_material(m.group(1))

    return {
        'sw_winding_material': winding_mat,
        'sw_filler': filler,
        'sw_inner_ring': inner_ring,
        'sw_outer_ring': outer_ring,
    }


_MOC_KEYWORDS = [
    ('COMPRESSED NON ASBESTOS FIBER', ['CNAF', 'COMPRESSED NON ASBESTOS FIBER']),
    ('CNAF', ['CNAF']),
    ('NON ASBESTOS', ['NON ASBESTOS', 'NON-ASBESTOS']),
    ('NEOPRENE', ['NEOPRENE', 'CHLOROPRENE']),
    ('NATURAL RUBBER', ['NATURAL RUBBER']),
    ('EPDM', ['EPDM']),
    ('EXPANDED PTFE', ['EXPANDED PTFE', 'EPTFE']),
    ('PTFE ENVELOPED', ['PTFE ENVELOPED', 'PTFE ENVELOPE']),
    ('PTFE', ['PTFE', 'TEFLON']),
    ('VITON', ['VITON', 'FKM']),
    ('GRAPHITE', ['GRAPHITE', 'GRAFOIL', 'FLEXIBLE GRAPHITE']),
    ('BUTYL RUBBER', ['BUTYL']),
    ('NITRILE BUTADIENE RUBBER', ['NBR', 'NITRILE', 'BUNA-N', 'BUNA N']),
    ('RUBBER', ['RUBBER']),  # generic — will be flagged
]


_RTJ_MOC_MAP = {
    'SOFT IRON': 'SOFTIRON',
    'SOFTIRON': 'SOFTIRON',
    'SOFT IRON GALVANISED': 'SOFTIRON GALVANISED',
    'SOFT IRON GALVANIZED': 'SOFTIRON GALVANISED',
    'GALVANISED SOFT IRON': 'SOFTIRON GALVANISED',
    'GALVANIZED SOFT IRON': 'SOFTIRON GALVANISED',
    'GALVANISED': 'SOFTIRON GALVANISED',   # if "galvanised" appears with ring joint
    'LOW CARBON STEEL': 'LOW CARBON STEEL',
    'LCS': 'LOW CARBON STEEL',
    'CARBON STEEL': 'LOW CARBON STEEL',
    'SS316': 'SS316', 'SS 316': 'SS316', '316 SS': 'SS316', '316SS': 'SS316',
    'SS304': 'SS304', 'SS 304': 'SS304', '304 SS': 'SS304', '304SS': 'SS304',
    'SS316L': 'SS316L', 'SS 316L': 'SS316L',
    'F304': 'F304', 'F316': 'F316', 'F316L': 'F316L',
    'MONEL': 'MONEL 400', 'MONEL 400': 'MONEL 400',
    'INCONEL': 'INCONEL 625', 'INCONEL 625': 'INCONEL 625',
}

# BHN hardness defaults per RTJ MOC (max allowed per ASME B16.20)
_RTJ_HARDNESS = {
    'SOFTIRON': 90,
    'SOFTIRON GALVANISED': 90,
    'LOW CARBON STEEL': 120,
    'SS304': 160,
    'SS316': 160,
    'SS316L': 160,
    'SS304L': 160,
    'F304': 160,
    'F316': 160,
    'F316L': 160,
    'MONEL 400': 130,
    'INCONEL 625': 160,
}


def _extract_rtj_moc(desc: str) -> str | None:
    # Check combined "SOFT IRON GALVANISED" first (phrase and separate-word variants)
    has_softiron = 'SOFT IRON' in desc or 'SOFTIRON' in desc
    has_galvanised = 'GALVANISED' in desc or 'GALVANIZED' in desc
    if has_softiron and has_galvanised:
        return 'SOFTIRON GALVANISED'
    for raw, canon in _RTJ_MOC_MAP.items():
        if raw.upper() in desc:
            return canon
    return None


def _extract_rtj_groove(desc: str) -> str:
    if re.search(r'\bOVAL\b', desc):
        return 'OVAL'
    return 'OCT'  # octagonal is default for RTJ


def _extract_kamm_components(desc: str) -> dict:
    """Extract KAMMPROFILE-specific fields."""
    winding_m = _SW_WINDING_PATTERN.search(desc)
    winding_mat = _norm_sw_material(winding_m.group(1)) if winding_m else None
    filler_m = _SW_FILLER_PATTERN.search(desc)
    filler = re.sub(r'\s+', ' ', filler_m.group(1).upper()) if filler_m else 'GRAPHITE'

    outer_ring = None
    inner_ring = None
    # "INR SS316/316L CS centering ring" → inner=SS316, outer=CS via separate patterns
    combined_m = _SW_COMBINED_RING_PATTERN.search(desc)
    if combined_m:
        mat = _norm_sw_material(combined_m.group(1))
        inner_ring = mat
        outer_ring = mat
    else:
        outer_m = _SW_OUTER_RING_PATTERN.search(desc)
        outer_ring = _norm_sw_material(outer_m.group(1)) if outer_m else None
        inner_m = _SW_INNER_RING_PATTERN.search(desc)
        inner_ring = _norm_sw_material(inner_m.group(1)) if inner_m else None

    return {
        'sw_winding_material': winding_mat,
        'sw_filler': filler,
        'sw_inner_ring': inner_ring,
        'sw_outer_ring': outer_ring,
    }


def _extract_dji_dims(desc: str) -> tuple[float | None, float | None, float | None]:
    """Extract ID, OD, thickness from DJI descriptions like 'ID X OD X THK'."""
    # Pattern: "101X110 X1,5" or "13X18X1.5" — first dim is ID, second is OD
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*[Xx×]\s*(\d+(?:[.,]\d+)?)\s*[Xx×]\s*(\d+(?:[.,]\d+)?)', desc)
    if m:
        id_ = float(m.group(1).replace(',', '.'))
        od = float(m.group(2).replace(',', '.'))
        thk = float(m.group(3).replace(',', '.'))
        return id_, od, thk
    return None, None, None


def _extract_dji_moc(desc: str) -> str:
    """Extract jacket material from DJI descriptions."""
    if 'COPPER' in desc:
        return 'COPPER'
    if 'SS316' in desc or '316 SS' in desc or '316SS' in desc:
        return 'SS316'
    if 'SS304' in desc or '304 SS' in desc or '304SS' in desc:
        return 'SS304'
    if 'ALUMINIUM' in desc or 'ALUMINUM' in desc:
        return 'ALUMINIUM'
    return 'COPPER'  # most common


def _regex_extract(description: str) -> dict:
    desc = description.upper()

    _base_sw_none = {'sw_winding_material': None, 'sw_filler': None,
                     'sw_inner_ring': None, 'sw_outer_ring': None}
    _base_rtj_none = {'rtj_groove_type': None, 'rtj_hardness_bhn': None}

    # --- Priority 1: ISK (insulating gasket kit) — before RTJ since ISK-RTJ exists ---
    if _ISK_DETECT_PATTERN.search(desc):
        size, size_type = _extract_size(desc)
        is_rtj = bool(_RTJ_DETECT_PATTERN.search(desc))
        return {
            'size': size, 'size_type': size_type,
            'od_mm': None, 'id_mm': None,
            'rating': _extract_rating(desc),
            'gasket_type': 'ISK_RTJ' if is_rtj else 'ISK',
            'moc': None,
            'face_type': None,
            'thickness_mm': None,
            'standard': 'ASME B16.5',
            'special': _extract_special(desc),
            **_base_sw_none, **_base_rtj_none,
            'confidence': 'HIGH' if (size and _extract_rating(desc)) else 'LOW',
        }

    # --- Priority 2: KAMM (kammprofile) ---
    if _KAMM_DETECT_PATTERN.search(desc):
        od_id = _OD_ID_PATTERN.search(desc)
        if od_id:
            kamm = _extract_kamm_components(desc)
            return {
                'size': f"OD {od_id.group(1)}MM x ID {od_id.group(2)}MM",
                'size_type': 'OD_ID',
                'od_mm': float(od_id.group(1)), 'id_mm': float(od_id.group(2)),
                'rating': None,
                'gasket_type': 'KAMM',
                'moc': None,  # built from sw_winding_material by rules engine
                'face_type': None,
                'thickness_mm': _extract_thickness(desc),
                'standard': None,  # no standard for custom OD/ID KAMM
                'special': _extract_special(desc),
                **kamm, **_base_rtj_none,
                'confidence': 'MEDIUM',
            }
        size, size_type = _extract_size(desc)
        kamm = _extract_kamm_components(desc)
        return {
            'size': size, 'size_type': size_type,
            'od_mm': None, 'id_mm': None,
            'rating': _extract_rating(desc),
            'gasket_type': 'KAMM',
            'moc': None,
            'face_type': _extract_face(desc),
            'thickness_mm': _extract_thickness(desc) or 4.5,
            'standard': _extract_standard(desc),
            'special': _extract_special(desc),
            **kamm, **_base_rtj_none,
            'confidence': 'HIGH' if (size and _extract_rating(desc) and kamm['sw_winding_material']) else 'MEDIUM',
        }

    # --- Priority 3: DJI (double jacket) ---
    if _DJI_DETECT_PATTERN.search(desc):
        id_, od, thk = _extract_dji_dims(desc)
        dji_moc = _extract_dji_moc(desc)
        return {
            'size': f"OD {od}MM x ID {id_}MM" if od and id_ else None,
            'size_type': 'OD_ID',
            'od_mm': od, 'id_mm': id_,
            'rating': None,
            'gasket_type': 'DJI',
            'moc': dji_moc,
            'face_type': None,
            'thickness_mm': thk,
            'standard': None,
            'special': _extract_special(desc),
            **_base_sw_none, **_base_rtj_none,
            'confidence': 'HIGH' if (od and id_ and thk) else 'LOW',
        }

    # --- Priority 4: RTJ ---
    if _RTJ_DETECT_PATTERN.search(desc):
        size, size_type = _extract_size(desc)
        rtj_moc = _extract_rtj_moc(desc)
        groove = _extract_rtj_groove(desc)
        hardness = _RTJ_HARDNESS.get(rtj_moc) if rtj_moc else None
        return {
            'size': size, 'size_type': size_type,
            'od_mm': None, 'id_mm': None,
            'rating': _extract_rating(desc),
            'gasket_type': 'RTJ',
            'moc': rtj_moc,
            'face_type': None,
            'thickness_mm': None,
            'standard': 'ASME B16.20',
            'special': _extract_special(desc),
            **_base_sw_none,
            'rtj_groove_type': groove,
            'rtj_hardness_bhn': hardness,
            'confidence': 'HIGH' if (size and _extract_rating(desc) and rtj_moc) else 'MEDIUM',
        }

    # --- Priority 5: SPIRAL WOUND ---
    if _SW_DETECT_PATTERN.search(desc):
        size, size_type = _extract_size(desc)
        sw = _extract_sw_components(desc)
        return {
            'size': size, 'size_type': size_type,
            'od_mm': None, 'id_mm': None,
            'rating': _extract_rating(desc),
            'gasket_type': 'SPIRAL_WOUND',
            'moc': None,
            'face_type': None,
            'thickness_mm': _extract_thickness(desc),
            'standard': _extract_standard(desc),
            'special': _extract_special(desc),
            **sw, **_base_rtj_none,
            'confidence': 'HIGH' if (size and _extract_rating(desc) and sw['sw_winding_material']) else 'MEDIUM',
        }

    # --- Priority 6: OD × ID soft cut ---
    od_id = _OD_ID_PATTERN.search(desc)
    if od_id:
        return {
            'size': f"OD {od_id.group(1)}MM x ID {od_id.group(2)}MM",
            'size_type': 'OD_ID',
            'od_mm': float(od_id.group(1)),
            'id_mm': float(od_id.group(2)),
            'rating': _extract_rating(desc),
            'gasket_type': 'SOFT_CUT',
            'moc': _extract_moc(desc),
            'face_type': _extract_face(desc),
            'thickness_mm': _extract_thickness(desc),
            'standard': _extract_standard(desc),
            'special': _extract_special(desc),
            **_base_sw_none, **_base_rtj_none,
            'confidence': 'MEDIUM',
        }

    # --- Priority 7: NPS/NB soft cut ---
    size, size_type = _extract_size(desc)
    moc = _extract_moc(desc)
    return {
        'size': size, 'size_type': size_type,
        'od_mm': None, 'id_mm': None,
        'rating': _extract_rating(desc),
        'gasket_type': 'SOFT_CUT',
        'moc': moc,
        'face_type': _extract_face(desc),
        'thickness_mm': _extract_thickness(desc),
        'standard': _extract_standard(desc),
        'special': _extract_special(desc),
        **_base_sw_none, **_base_rtj_none,
        'confidence': 'MEDIUM' if (size and moc) else 'LOW',
    }


def _extract_size(desc: str) -> tuple[str | None, str]:
    from data.reference_data import NB_TO_NPS, normalize_size
    # "NB100", "NB 40", "DN15", "DN 25" — DN and NB are identical (metric nominal bore)
    m = re.search(r'\b(?:NB|DN)\s*(\d+(?:\.\d+)?)\b', desc, re.IGNORECASE)
    if m:
        return _nb_to_nps(int(float(m.group(1))), NB_TO_NPS), 'NB'
    # "100NB", "100 NB", "15DN", "25 DN"
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:NB|DN)\b', desc, re.IGNORECASE)
    if m:
        return _nb_to_nps(int(float(m.group(1))), NB_TO_NPS), 'NB'
    # "NPS 2", "NPS 1.5" — NPS prefix with space (common in enquiry descriptions)
    m = re.search(r'\bNPS\s+(\d+(?:\.\d+)?)\b', desc, re.IGNORECASE)
    if m:
        return m.group(1) + '"', 'NPS'
    # "24GASKET", "32GASKET" — bare number at start of KAMM/SPW descriptions
    m = re.match(r'^(\d+(?:\.\d+)?)\s*GASKET\b', desc, re.IGNORECASE)
    if m:
        return m.group(1) + '"', 'NPS'
    # Fractional NPS: "1 1/2\"", "3/4\"", "1 1/2 \"" (must check before plain digit pattern)
    m = re.search(r'(\d+\s+\d+/\d+|\d+/\d+)\s*["\']', desc)
    if m:
        norm = normalize_size(m.group(1))
        if norm:
            return norm, 'NPS'
    # "6\"", "6''", "6 NPS", "6 INCH"
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:"|\'\'|NPS\b|INCH\b)', desc, re.IGNORECASE)
    if m:
        return m.group(1) + '"', 'NPS'
    # "Gasket - Rubber - 6'' PN10"
    m = re.search(r'[-–]\s*(\d+(?:\.\d+)?)\s*(?:\'\'|"|NPS\b|NB\b)', desc)
    if m:
        return m.group(1) + '"', 'NPS'
    return None, 'UNKNOWN'


def _nb_to_nps(nb: int, nb_map: dict) -> str:
    """Convert NB (mm) to NPS inch string, or return raw value if not in map."""
    return nb_map.get(nb, f'{nb}"')


def _extract_rating(desc: str) -> str | None:
    m = re.search(r'PN\s*(\d+)', desc, re.IGNORECASE)
    if m:
        return f"PN {m.group(1)}"
    m = re.search(r'(?:CL|CLASS|#)\s*[-.\s]*(\d+)|(\d+)\s*(?:#|LB)', desc, re.IGNORECASE)
    if m:
        val = m.group(1) or m.group(2)
        if val in ('150', '300', '600', '900', '1500', '2500'):
            return f"{val}#"
    return None


def _extract_moc(desc: str) -> str | None:
    for moc_name, keywords in _MOC_KEYWORDS:
        if any(kw.upper() in desc for kw in keywords):
            return moc_name
    return None


def _extract_face(desc: str) -> str | None:
    if re.search(r'\bFF\b|FULL\s*FACE\b', desc):
        return 'FF'
    if re.search(r'\bRF\b|RAISED\s*FACE\b|FLAT\s*RING\b', desc):
        return 'RF'
    return None


_THICKNESS_REVERSE_PATTERN = re.compile(
    r'\bTHK\s*[=:]\s*(\d+(?:\.\d+)?)\s*MM\b',
    re.IGNORECASE,
)


def _extract_thickness(desc: str) -> float | None:
    # Prefer "THK= 3 MM" / "THK: 3MM" (e.g. from KAMM OD/ID descriptions)
    m = _THICKNESS_REVERSE_PATTERN.search(desc)
    if m:
        return float(m.group(1))
    m = _THICKNESS_PATTERN.search(desc)
    # Guard: reject if this "NNN MM THK" is actually an ID/OD value preceding THK=
    if m:
        val = float(m.group(1))
        # If there's a separate THK keyword not matched by the preferred pattern, trust this
        return val
    return None


def _extract_standard(desc: str) -> str | None:
    if 'B16.47' in desc:
        return 'ASME B16.47 ( SERIES B )' if 'SERIES B' in desc else 'ASME B16.47'
    if 'B16.20' in desc:
        return 'ASME B16.20'
    if 'B16.21' in desc or 'ASME' in desc or 'ANSI' in desc:
        return 'ASME B16.21'
    if re.search(r'EN\s*1514|BS\s*7531|DIN', desc):
        return 'EN 1514-1'
    return None


def _extract_special(desc: str) -> str | None:
    specials = []
    if 'FOOD GRADE' in desc:
        specials.append('FOOD GRADE')
    if 'NACE' in desc:
        specials.append('NACE MR0175')
    if 'LETHAL' in desc:
        specials.append('LETHAL SERVICE')
    if 'EIL' in desc or 'ENGINEERS INDIA' in desc:
        specials.append('EIL APPROVED')
    return ', '.join(specials) if specials else None
