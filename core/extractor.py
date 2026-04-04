from __future__ import annotations
"""
Extracts structured gasket fields from raw description strings.
Primary: LLM (OpenAI API). Fallback: regex-based extraction.
"""
import os
import re
import json
import time
import logging

logger = logging.getLogger(__name__)

_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    api_key = os.environ.get('OPENAI_API_KEY') or _get_streamlit_secret('OPENAI_API_KEY')
    if not api_key:
        return None
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=api_key, timeout=60.0)
        return _openai_client
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
  "ring_no": "e.g. R-24 | R-37 | null (RTJ only — ring number if explicitly stated in description)",
  "confidence": "HIGH | MEDIUM | LOW"
}"""

_BATCH_SIZE = 8  # descriptions per LLM call

_BATCH_SYSTEM_PROMPT = f"""You are a gasket specification extraction assistant for an oil & gas company.
Extract gasket specs from customer descriptions and return ONLY valid JSON.

Handle gasket types:
1. SOFT_CUT: flat ring (RF/FF), materials like CNAF, PTFE, NEOPRENE, EPDM, NATURAL RUBBER, GRAPHITE, EXPANDED GRAPHITE, VITON, NON ASBESTOS, SBR, NBR, NITRILE RUBBER, SILICONE RUBBER, BUTYL RUBBER, ARAMID FIBER, CERAMIC FIBER, THERMICULITE, CORK, LEATHER. "EXPANDED GRAPHITE WITH SS304/SS316 REINFORCEMENT/RENFORCEMENT" is SOFT_CUT — SS304/SS316 here is a metallic insert/tanged reinforcement, NOT a spiral wound winding; set moc="EXPANDED GRAPHITE WITH SS304 REINFORCEMENT" (or SS316 as applicable). Similarly "X WITH SS304/SS316/MS/STEEL INSERT" combinations (e.g. EPDM WITH SS304 INSERT, PTFE WITH SS316 INSERT) are SOFT_CUT with a metallic insert. "VITON GASKET" = SOFT_CUT with moc="VITON GASKET".
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
- size: If NPS/inch given (e.g. "6\\"", "1.5\\"") use as-is. If NB or DN given (metric nominal bore), output as "X NB" e.g. "25 NB", "100 NB", "450 NB" — do NOT convert to inches. DN = NB (identical). For OD×ID dimensions use "OD NNNmm x ID NNNmm". Set size_type accordingly: NPS for inch sizes, NB for NB/DN sizes, OD_ID for OD/ID dimensions.
- rating: use format "150#", "300#", "PN 10", "PN 16". Valid ASME classes: 150, 300, 600, 900, 1500, 2500, 3000.
- gasket_type: SPIRAL_WOUND if description mentions "spiral wound", "spiral seal", "spiral winding", "SPW", "SPWD", "SPRL-WND", "WND", "SW gasket", "SPIRL WOUND" (typo), or combination of winding material + filler + ring. "WND" alone means winding (e.g. "ALLOY 20 WND PTFE FILL ALLOY 20 I/R CS O/R" = SPIRAL_WOUND with ALLOY 20 winding, PTFE filler, ALLOY 20 inner ring, CS outer ring)
- gasket_type: RTJ if description mentions "ring joint", "RTJ", "R.T.J", "ring type joint", "ring type gasket", "octagonal ring", "oval ring", "JOINT TORE" (French), "JOINT TORIQUE" (French), RTJ ring number (R-nn), or API 6A ring numbers (RX-nn, BX-nn)
- For SPIRAL_WOUND: set sw_winding_material (e.g. SS304), sw_filler (GRAPHITE/PTFE/MICA/CNAF), sw_outer_ring (e.g. CS), sw_inner_ring if present; leave moc null
- For SOFT_CUT: set moc, leave sw_* and rtj_* fields null
- For RTJ: set moc (e.g. SOFTIRON, SOFTIRON GALVANISED, SS316, LOW CARBON STEEL), rtj_groove_type (OCT or OVAL), rtj_hardness_bhn (90 for soft iron, 120 for LCS, 160 for SS); set ring_no if stated (e.g. "R-24", "RX-53", "BX-152"); leave sw_* fields null; standard is ASME B16.20
- Normalize winding materials: "304 SS"/"SS 304"/"304SS"/"304 STAINLESS STEEL"/"304-SS"/"AISI 304" → "SS304"; "316 SS"/"316 STAINLESS STEEL"/"316-SS" → "SS316"; "316L SS"/"316L-SS" → "SS316L"; "SUPER DUPLEX"/"SDSS" → "SDSS (UNS S32750)"; "STAINLESS STEEL" alone (no grade) → null; "INCOLOY 825"/"INCOLOY825"/"INCOLOY" → "INCOLOY 825"; "INCONEL 625"/"INCONEL" → "INCONEL 625"
- Normalize ring materials: "CARBON STEEL"/"MS"/"C.S."/"CS OR"/"CS" → "CS"; "SS316 IR"/"316-SS IR"/"IR SS316"/"IR SS-316" → "SS316" inner ring; "SS IR" generic inner ring; "INCOLOY 825" inner/outer ring → "INCOLOY 825"; "I/R" = inner ring, "O/R" = outer ring (e.g. "ALLOY 20 I/R" = inner ring ALLOY 20, "CS O/R" = outer ring CS, "/ OR CS" = outer ring CS, "/ IR SS-316" = inner ring SS316); "LTCS" = Low Temperature Carbon Steel (pass through as LTCS)
- Normalize RTJ MOC: "SOFT IRON"/"SOFTIRON" → "SOFTIRON"; "SOFT IRON GALVANISED" → "SOFTIRON GALVANISED"; "LOW CARBON STEEL"/"LCS"/"CARBON STEEL"/"CN/ZN PLATED CARBON STEEL" → "LOW CARBON STEEL"; "316 S"/"STAINLESS STEEL 316" → "SS316"; "UNS S32205" / "UNS S32750" → keep as-is e.g. "UNS S32205"; "INCOLOY 825"/"INCOLOY825"/"INCOLOY" (in RTJ context) → "INCOLOY 825" with rtj_hardness_bhn=160; "INCONEL 625"/"INCONEL" → "INCONEL 625" with rtj_hardness_bhn=160
- For RTJ: capture ring_no including RX and BX prefixes (API 6A): "RX53" → "RX-53", "BX-152" → "BX-152", "BX 156" → "BX-156", "RX 46" → "RX-46" (space between prefix and number is same as hyphen)
- For RTJ hardness: "90 BHN MAX" → rtj_hardness_bhn=90; "22 HRC" or "MAX HARDNESS 22 HRC" → note in special; "83 HRBW" → note in special
- face_type: null for spiral wound and RTJ; RF/FF/null for soft cut
- thickness_mm: null for RTJ (rings have no thickness field); extract number for others; null if not stated
- Standard: "API 6A" or "API Specs" → standard="API 6A"; "B16/A" → "ASME B16.20"; ASME without B16 qualifier → let type determine; ASME B16.21 for soft cut NPS≤24"; ASME B16.47 for soft cut NPS≥26" (large bore); ASME B16.20 for spiral wound NPS≤24" and all RTJ; ASME B16.47 for NPS≥26" spiral wound. If customer specifies "SERIES A" or "SERIES B" in the description, include it: "ASME B16.47 ( SERIES A )" or "ASME B16.47 ( SERIES B )"
- special: capture FOOD GRADE, NACE, LETHAL, EIL APPROVED, SERIES B, API 6A, NACE MR 0175, etc. For ISK/ISK_RTJ: also capture the full material spec details in special (e.g. "GRE (G10), W/316SS CORE, GRE (G10) SLEEVES AND WASHER" or "SET:G10 GASKET CORE 4 MM THK WITH PRIMARY SEAL PTFE SPRING ENERGISED RING, G10 WASHER 3 MM THK & SLEEVES, ZINC PLATED CS WASHER 3 MM THK") — pass these through verbatim from the customer description.
- SOFT_CUT brand-name materials: trade names like "KROLLER & ZILLER", "KLINGER", "DONIT", "GARLOCK" followed by a grade code (e.g. "G-S-T-P/S") are SOFT_CUT gaskets — set moc to the full brand + grade string (e.g. "KROLLER & ZILLER (G-S-T-P/S)"). "WITH SPACER" means a spacer ring is included but does NOT change the gasket_type — it remains SOFT_CUT; capture "WITH SPACER" in the special field.
- confidence: HIGH if all key fields clear, LOW if ambiguous"""


def extract_batch(items: list[dict], progress_cb=None) -> list[dict]:
    """
    Extract structured fields for all items.
    Deduplicates by description. Regex-first: only sends ambiguous items to LLM,
    in batches to minimise API calls.
    """
    # Normalize embedded newlines (e.g. from Shift+Enter in Excel or CSV) to spaces
    for item in items:
        if item.get('description'):
            item['description'] = re.sub(r'[\r\n]+', ' ', item['description']).strip()

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
    # Keep regex results indexed so we can guard against LLM type downgrades
    regex_cache = {desc: _regex_extract(desc) for desc in needs_llm}

    _NON_DEFAULT_TYPES = {'SPIRAL_WOUND', 'RTJ', 'KAMM', 'DJI', 'ISK', 'ISK_RTJ'}

    if needs_llm:
        client = _get_openai_client()
        for batch_start in range(0, len(needs_llm), _BATCH_SIZE):
            batch = needs_llm[batch_start:batch_start + _BATCH_SIZE]
            llm_results = _llm_extract_batch(client, batch) if client else [None] * len(batch)
            for desc, llm_result in zip(batch, llm_results):
                regex_result = regex_cache[desc]
                if llm_result:
                    regex_type = regex_result.get('gasket_type', 'SOFT_CUT')
                    # Always trust regex for non-default types — prevents DJI→SPW, SPW→RTJ
                    # lateral misclassifications by LLM
                    if regex_type in _NON_DEFAULT_TYPES:
                        llm_result['gasket_type'] = regex_type
                    # Back-fill regex-extracted SW/RTJ components that LLM missed
                    _sw_fields = ('sw_winding_material', 'sw_filler', 'sw_inner_ring', 'sw_outer_ring')
                    for field in _sw_fields:
                        if regex_result.get(field) and not llm_result.get(field):
                            llm_result[field] = regex_result[field]
                    if regex_result.get('ring_no') and not llm_result.get('ring_no'):
                        llm_result['ring_no'] = regex_result['ring_no']
                    # Back-fill OD/ID dimensions for KAMM/DJI when LLM missed them
                    for dim_field in ('od_mm', 'id_mm'):
                        if regex_result.get(dim_field) and not llm_result.get(dim_field):
                            llm_result[dim_field] = regex_result[dim_field]
                    if regex_result.get('size_type') == 'OD_ID' and llm_result.get('size_type') != 'OD_ID':
                        llm_result['size_type'] = 'OD_ID'
                        if regex_result.get('size') and not llm_result.get('od_mm'):
                            llm_result['size'] = regex_result['size']
                    # Back-fill size and rating when LLM returns null but regex found them
                    for field in ('size', 'size_type', 'rating'):
                        if regex_result.get(field) and not llm_result.get(field):
                            llm_result[field] = regex_result[field]
                    # Always trust regex for NB/DN sizes — LLM may convert to NPS inches
                    if regex_result.get('size_type') == 'NB' and regex_result.get('size'):
                        llm_result['size'] = regex_result['size']
                        llm_result['size_type'] = 'NB'
                    # Always trust regex for NPS sizes — LLM may wrongly return NB for "NPS 10"/"NPS 12"
                    if regex_result.get('size_type') == 'NPS' and regex_result.get('size'):
                        llm_result['size'] = regex_result['size']
                        llm_result['size_type'] = 'NPS'
                    cache[desc] = llm_result
                else:
                    cache[desc] = regex_result
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
    """Send a batch of descriptions to OpenAI in one API call. Returns list of dicts (or None on failure)."""
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
                model='gpt-4o-mini',
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
                wait = 5.0 * (attempt + 1)
                logger.info(f'Rate limited — waiting {wait:.1f}s (attempt {attempt + 1}/3)')
                time.sleep(wait)
            else:
                logger.warning(f'LLM batch extraction failed: {e}')
                return [None] * len(descriptions)
    logger.warning('LLM batch extraction failed after 3 attempts')
    return [None] * len(descriptions)


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
    # Format 1: label before value — "OD 584MM X ID 510MM" / "O/D 584 X I/D 510"
    r'O/?D\s*[=]?\s*(\d+(?:\.\d+)?)\s*(?:MM)?\s*[Xx×,]?\s*I/?D\s*[=]?\s*(\d+(?:\.\d+)?)'
    # Format 2: value before label — "1650 mm O/D x 1550 mm I/D"
    r'|(\d+(?:\.\d+)?)\s*(?:MM)?\s*O/?D\s*[Xx×,\s]+(\d+(?:\.\d+)?)\s*(?:MM)?\s*I/?D',
    re.IGNORECASE
)


def _od_id_values(m) -> tuple[float, float]:
    """Extract (OD, ID) from an _OD_ID_PATTERN match, handling both format alternatives."""
    if m.group(1) is not None:
        return float(m.group(1)), float(m.group(2))   # Format 1: OD, ID
    return float(m.group(3)), float(m.group(4))        # Format 2: OD, ID

# ---------------------------------------------------------------------------
# Spiral wound detection & extraction helpers
# ---------------------------------------------------------------------------

_SW_DETECT_PATTERN = re.compile(
    r'\bSPIRAL[-\s]*WOUND\b'                          # "SPIRAL WOUND" or "SPIRAL-WOUND" (hyphenated)
    r'|SPIRAL-WOUND'                                  # concatenated without word boundary (e.g. "SS-GRAPHITESPIRAL-WOUND")
    r'|\bSPIRAL\s*(?:SEAL|WINDING)\b'                # "SPIRAL SEAL" / "SPIRAL WINDING"
    r'|\bSPIRL\s*WOUND\b'                             # common typo "SPIRL WOUND"
    r'|\bSPRIL\s*WOUND\b'                             # common typo "SPRIL WOUND"
    r'|\bSPRL[-\s]?WND\b'                             # "SPRL-WND" abbreviated
    r'|\bSPWD\b'                                      # "SPWD" abbreviation
    r'|\bSPW\b'                                       # abbreviation SPW
    r'|\bS\.?W\.?\s*GASKET\b'                         # "SW GASKET"
    r'|(?:SS\s*3\d{2}L?|304\s*SS|316\s*SS)\s*\+'     # "304 SS +" shorthand (metal + filler + ring)
    r'|\bWINDING\s*STRIP\b'
    r'|\bWND\b',                                      # "WND" abbreviation (e.g. "ALLOY 20 WND PTFE FILL")
    re.IGNORECASE,
)

_RTJ_DETECT_PATTERN = re.compile(
    r'\bRING\s*(?:TYPE\s*)?JOINT\b'                  # "Ring Joint" / "Ring Type Joint"
    r'|\bRING\s*TYPE\s*GASKET\b'                     # "Ring Type Gasket"
    r'|\bRTJ\b'                                       # abbreviation
    r'|\bR\.T\.J\b'
    r'|\bOCTAGONAL\s*RING\b'
    r'|\bOVAL\s*RING\b'
    r'|\bJOINT\s*TOR(?:E|IQUE)?\b'                   # French: "JOINT TORE" / "JOINT TORIQUE"
    r'|\bTOR(?:E|IQUE)\s*JOINT\b'                    # French reverse order
    r'|\b(?:RX|BX)[-\s]?\d{2,4}\b',                  # API 6A ring numbers RX-53, BX-151, BX 156
    re.IGNORECASE,
)

_KAMM_DETECT_PATTERN = re.compile(
    r'\bKAMM(?:PROFILE|PROFIL)?\b'
    r'|\bCAM\s*PROFILE\b'
    r'|\bSERRATED\s*(?:METAL\s*)?(?:CORE\s*)?GASKET\b',
    re.IGNORECASE,
)

_DJI_DETECT_PATTERN = re.compile(
    r'\bDOUBLE\s*JACKET(?:ED)?\b'                    # "DOUBLE JACKET" or "DOUBLE JACKETED"
    r'|\bDJI\b'
    r'|\bJACKET(?:ED)?\s*GASKET\b'                   # "JACKET GASKET" or "JACKETED GASKET"
    r'|\bCOPPER\s*JACKET(?:ED)?\b',
    re.IGNORECASE,
)

_ISK_DETECT_PATTERN = re.compile(
    r'\bINSULAT(?:ING|ED|ION)\s*GASKETS?(?![A-Za-z])'  # "Insulating/Insulated Gasket(s)" (allows trailing _, digit, space)
    r'|\bINSULAT(?:ING|ED)\s*(?:GASKET\s*)?KITS?\b'    # "Insulating/Insulated Kit(s)" / "Insulating Gasket Kit"
    r'|\bISK\b'
    r'|\bGSKT\s*INSUL',
    re.IGNORECASE,
)

_SW_WINDING_PATTERN = re.compile(
    r'\b(SS\s*304L?|SS\s*316L?|SS\s*321|SS\s*347|SS\s*904L?'
    r'|SS-304L?|SS-316L?|SS-321|SS-347'                # hyphen format "SS-316", "SS-316L"
    r'|304L?\s*SS|316L?\s*SS|321\s*SS|347\s*SS'
    r'|316L?-SS|304L?-SS|321-SS|347-SS'               # dash format "316-SS", "316L-SS"
    r'|AISI\s*304L?|AISI\s*316L?|AISI\s*321|AISI\s*347'  # AISI grades
    r'|304L?\s*STAINLESS\s*STEEL|316L?\s*STAINLESS\s*STEEL'  # "304 STAINLESS STEEL WINDING"
    r'|321\s*STAINLESS\s*STEEL|347\s*STAINLESS\s*STEEL'
    r'|INCONEL\s*625|INCONEL\s*600|INCONEL\s*800'
    r'|INCONEL\s*\d*'                                  # other INCONEL grades
    r'|INCOLOY\s*825|INCOLOY\s*\d*'                   # INCOLOY grades
    r'|HASTELLOY\s*C[-\s]?276|HASTELLOY\s*B[-\s]?2|HASTELLOY\s*[A-Z]\d*'
    r'|MONEL\s*400|MONEL\s*\d*'
    r'|SUPER\s*DUPLEX|SDSS|HDSS'                       # duplex grades (generic)
    r'|ALLOY\s*20|AL\s*6XN'
    r'|LTCS|LCS'                                       # Low Temp / Low Carbon Steel (ring material)
    r'|DUPLEX|TITANIUM|ZIRCONIUM|TANTALUM'
    r'|STAINLESS\s*STEEL'                              # generic — triggers grade flag
    r'|UNS\s+[A-Z]\d+)\b',                            # UNS materials e.g. UNS N06625, UNS N08825
    re.IGNORECASE,
)
_SW_FILLER_PATTERN = re.compile(
    r'\b(FLEXIBLE\s+GRAPHITE|GRAPHITE|GRH[-\s]?FILL|GRH\b'  # GRAPHITE incl. GRH-FILL abbreviation
    r'|GRAPH[-\s]?FILL|GRPH\b|GRPH[-\s]?FILL'              # GRAPH FILL / GRPH abbreviations
    r'|PTFE|TEFLON'
    r'|CNAF|NON[-\s]?ASBESTOS\s*FILLER|COMPRESSED\s*NON[-\s]?ASBESTOS'
    r'|THERMICULITE|THERMICULIT'
    r'|MICA|CERAMIC\s*(?:FIBER|FIBRE)?|MINERAL\s*WOOL'
    r'|STAINLESS\s*(?:STEEL\s*)?FILLER|STAINLESSFILLER)\b',   # "STAINLESSFILLER" concatenation
    re.IGNORECASE,
)
_SW_OUTER_RING_PATTERN = re.compile(
    r'\b(CS|CARBON\s*STEEL|M\.?S\.?|LTCS|LCS|SS\s*304L?|SS\s*316L?|SS-304L?|SS-316L?|304\s*SS|316\s*SS|316L?-SS|304L?-SS|ALLOY\s*20|INCONEL\s*\d+|INCOLOY\s*\d+)\s*(?:OUTER\s*)?(?:CENTERING\s*)?RING\b'
    r'|\bOUTER\s*RING[:\s]+\s*(CS|CARBON\s*STEEL|M\.?S\.?|LTCS|LCS|SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS|ALLOY\s*20|INCONEL\s*\d+|INCOLOY\s*\d+)'  # "Outer ring: SS316"
    r'|\b(CS|SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS|LTCS|LCS)\s+OR\b'  # "CS OR", "316-SS OR"
    r'|\bW/(?:I)?OR\s+(CS|SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS)\b'  # "W/OR 316-SS", "W/IOR SS316"
    r'|\bRING\s*=\s*(CS|SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS)\b'   # "RING=316-SS"
    r'|\b(CS|CARBON\s*STEEL|M\.?S\.?|LTCS|LCS|SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS|ALLOY\s*20|INCONEL\s*\d+|INCOLOY\s*\d+)\s+O/R\b'  # "CS O/R", "ALLOY 20 O/R"
    r'|\b(?:OR|O/R)\s+(CS|CARBON\s*STEEL|M\.?S\.?|LTCS|LCS|SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS|ALLOY\s*20|INCONEL\s*\d+|INCOLOY\s*\d+)\b',  # "OR CS", "O/R CS", "/ OR CS"
    re.IGNORECASE,
)
_SW_INNER_RING_PATTERN = re.compile(
    r'(?:\bINR\b|\bINNER\s+RING\b|\bINNER\s+CENTERING)\s*[,:]?\s*'
    r'(SS\s*\d{3}L?(?:/\d{3}L?)?|SS-\d{3}L?|CS|CARBON\s*STEEL|LTCS|LCS|304\s*SS|316\s*SS|\d{3}L?-SS|ALLOY\s*20|INCONEL\s*\d+|INCOLOY\s*\d+|UNS\s*[A-Z]\d+)'
    r'|\bINNER\s+RING\s+(\d{3}L?)\s+S\b'                     # "INNER RING 304 S" (S = stainless shorthand)
    r'|\b(SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS|CS|LTCS|LCS)\s+IR\b'  # "SS316 IR", "316-SS IR"
    r'|\bSS\s+IR\b'                                           # "SS IR" generic inner ring
    r'|\bW/IOR\s+(CS|SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS)\b'  # "W/IOR SS316"
    r'|\b(SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS|CS|CARBON\s*STEEL|LTCS|LCS|ALLOY\s*20|INCONEL\s*\d+|INCOLOY\s*\d+)\s+I/R\b'  # "ALLOY 20 I/R", "SS316 I/R"
    r'|\b(?:IR|I/R)\s+(SS\s*\d{3}L?|SS-\d{3}L?|\d{3}L?\s*SS|\d{3}L?-SS|CS|CARBON\s*STEEL|LTCS|LCS|ALLOY\s*20|INCONEL\s*\d+|INCOLOY\s*\d+)\b',  # "IR SS-316", "I/R SS316", "/ IR SS-316"
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
    # "304 STAINLESS STEEL WINDING" variants
    '304 STAINLESS STEEL': 'SS304', '304L STAINLESS STEEL': 'SS304L',
    '304STAINLESS STEEL': 'SS304',
    '316 STAINLESS STEEL': 'SS316', '316L STAINLESS STEEL': 'SS316L',
    '316STAINLESS STEEL': 'SS316',
    '321 STAINLESS STEEL': 'SS321', '347 STAINLESS STEEL': 'SS347',
    'STAINLESS STEEL': 'SS',   # no grade — will trigger flag in rules engine
    'CARBON STEEL': 'CS', 'CARBON  STEEL': 'CS', 'MS': 'CS', 'M.S.': 'CS', 'C.S.': 'CS',
    'INCONEL': 'INCONEL 625', 'HASTELLOY': 'HASTELLOY C276', 'MONEL': 'MONEL 400',
    # Dash-format "316-SS", "316L-SS" and "SS-316", "SS-316L"
    '316-SS': 'SS316', '316L-SS': 'SS316L', '304-SS': 'SS304', '304L-SS': 'SS304L',
    '321-SS': 'SS321', '347-SS': 'SS347',
    'SS-316': 'SS316', 'SS-316L': 'SS316L', 'SS-304': 'SS304', 'SS-304L': 'SS304L',
    'SS-321': 'SS321', 'SS-347': 'SS347',
    # Low temp / low carbon steel abbreviations
    'LTCS': 'LTCS', 'LCS': 'LOW CARBON STEEL',
    # INCOLOY grades
    'INCOLOY 825': 'INCOLOY 825', 'INCOLOY825': 'INCOLOY 825', 'INCOLOY': 'INCOLOY 825',
    # AISI grades
    'AISI 304': 'SS304', 'AISI 316': 'SS316', 'AISI 316L': 'SS316L',
    'AISI 304L': 'SS304L', 'AISI 321': 'SS321', 'AISI 347': 'SS347',
    'AISI304': 'SS304', 'AISI316': 'SS316', 'AISI316L': 'SS316L',
    # Duplex grades
    'SUPER DUPLEX': 'SDSS (UNS S32750)', 'SDSS': 'SDSS (UNS S32750)',
    'HDSS': 'HDSS',
    # INCONEL explicit grades
    'INCONEL 625': 'INCONEL 625', 'INCONEL 600': 'INCONEL 600', 'INCONEL 800': 'INCONEL 800',
    # Filler material that appears as winding (edge case)
    'STAINLESSFILLER': 'SS',  # concatenation artifact — treat as unknown SS grade
    'STAINLESS FILLER': 'SS',
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
    # UNS materials pass through as-is (e.g. UNS N08825)
    if key.startswith('UNS ') or key.startswith('UNS-'):
        return key
    return key


_SW_COMBINED_RING_PATTERN = re.compile(
    r'\b(SS\s*\d{3}L?|\d{3}L?\s*SS|CS|CARBON\s*STEEL|M\.?S\.?)\s+INNER\s*[&/,]\s*OUTER\s*RING\b',
    re.IGNORECASE,
)


def _extract_sw_components(desc: str) -> dict:
    """Extract spiral wound gasket components from description string (uppercase)."""
    filler = None
    m = _SW_FILLER_PATTERN.search(desc)
    if m:
        filler = re.sub(r'\s+', ' ', m.group(1).upper())  # normalize spaces, keep FLEXIBLE GRAPHITE
        # Normalize filler abbreviations
        if re.search(r'^GRH', filler) or re.search(r'^GRPH', filler) or re.search(r'^GRAPH', filler):
            filler = 'GRAPHITE'
        elif 'CNAF' in filler or 'NON-ASBESTOS' in filler or 'NON ASBESTOS' in filler:
            filler = 'CNAF'
        elif 'STAINLESS' in filler or filler == 'STAINLESSFILLER':
            filler = 'GRAPHITE'  # "STAINLESSFILLER" is a trade name for flexible graphite facing

    outer_ring = None
    inner_ring = None
    # Check for combined "MATERIAL inner & outer ring" phrasing
    m = _SW_COMBINED_RING_PATTERN.search(desc)
    if m:
        mat = _norm_sw_material(m.group(1))
        inner_ring = mat
        outer_ring = mat
    else:
        m = _SW_OUTER_RING_PATTERN.search(desc)
        if m:
            # Find first non-None group (pattern has multiple capture group alternatives)
            mat_raw = next((g for g in m.groups() if g), None)
            if mat_raw:
                outer_ring = _norm_sw_material(mat_raw)
        m = _SW_INNER_RING_PATTERN.search(desc)
        if m:
            mat_raw = next((g for g in m.groups() if g), None)
            if mat_raw and mat_raw.upper() not in ('SS', 'IR'):  # skip bare "SS IR" with no grade
                inner_ring = _norm_sw_material(mat_raw)

    # Find winding material — mask ring-label positions first to avoid false matches
    # (e.g. "Outer ring: SS316" should not be classified as winding material)
    masked = desc
    for pat in (_SW_OUTER_RING_PATTERN, _SW_INNER_RING_PATTERN):
        masked = pat.sub(' ', masked)
    winding_mat = None
    m = _SW_WINDING_PATTERN.search(masked)
    if m:
        winding_mat = _norm_sw_material(m.group(1))
    # If no explicit winding but inner ring found, infer winding = inner ring
    # (common in API 601 descriptions: "SPIRAL WOUND ... INNER RING 304 S" implies SS304 winding)
    if winding_mat is None and inner_ring is not None and inner_ring not in ('CS',):
        winding_mat = inner_ring

    return {
        'sw_winding_material': winding_mat,
        'sw_filler': filler,
        'sw_inner_ring': inner_ring,
        'sw_outer_ring': outer_ring,
    }


_MOC_KEYWORDS = [
    # --- Fibre / sheet materials ---
    ('CNAF', ['CNAF', 'COMPRESSED NON ASBESTOS FIBER', 'COMP SHEET', 'COMPRESSED SHEET',
              'COMPRESSED FIBRE', 'COMP FIBRE', 'COMP FIBER', 'COMPRESSED FIBER',
              'NON ASBESTOS COMP', 'COMPRESSED NON-ASBESTOS', 'CNAF NON GRAPHITE']),
    ('NON ASBESTOS BS7531', ['NON ASBESTOS BS7531', 'NON ASBESTOS TYPE BS 7531',
                             'NON-ASB BS7531', 'BS7531', 'NONASBESTOSBS7531']),
    ('NON ASBESTOS SYNTHETIC FIBER', ['NON ASBESTOS SYNTHETIC FIBER', 'NON-ASB SYNT FIBER',
                                      'NON-ASBESTOS SHEET NBR BINDER', 'NON-ASBESTOS SHEET']),
    ('NON ASBESTOS', ['NON ASBESTOS', 'NON-ASBESTOS', 'ASBESTOS FREE']),
    ('ARAMID FIBER WITH NBR BINDER', ['ARAMID FIBRE WITH NBR BINDER', 'ARAMID FIBER WITH NBR BINDER',
                                      'ARAMID FIBRE WITH NBRBINDER', 'ARAMID FIBER WITH NBRBINDER',
                                      'ARAMIDE FIBER WITH NBR', 'ARA']),
    ('ARAMID FIBER', ['ARAMID FIBRE', 'ARAMID FIBER', 'ARAMIDE FIBER', 'ARAMIDE FIBRE', 'ARAMID']),
    ('CERAMIC FIBER', ['CERAMIC FIBER', 'CERAMIC FIBRE', 'CERAFELT', 'CERAMIC WOOL',
                       'CERAMIC PAPER', 'CERAFIBRE', 'CER']),
    ('CORK', ['CORK']),
    ('LEATHER', ['LEATHER']),
    # --- PTFE family ---
    ('EXPANDED PTFE', ['EXPANDED PTFE', 'EPTFE', 'GORE TEX', 'GORETEK', 'EXPENDED PTFE',
                       'PTFE GORE TEX']),
    ('PTFE ENVELOPED', ['PTFE ENVELOPED', 'PTFE ENVELOPE', 'PTFE ENVELOPE FILLED']),
    ('PTFE', ['PTFE', 'TEFLON']),
    # --- Graphite family (most specific first) ---
    ('EXPANDED GRAPHITE WITH SS316 REINFORCEMENT', [
        '98% EXPANDED GRAPHITE WITH SS316 RENFORCEMENT',
        '98% EXPANDED GRAPHITE WITH SS316 REINFORCEMENT',
        'EXPANDED GRAPHITE WITH SS316 RENFORCEMENT',
        'EXPANDED GRAPHITE WITH SS316 REINFORCEMENT',
    ]),
    ('EXPANDED GRAPHITE WITH SS304 REINFORCEMENT', [
        '98% EXPANDED GRAPHITE WITH SS304 RENFORCEMENT',
        '98% EXPANDED GRAPHITE WITH SS304 REINFORCEMENT',
        'EXPANDED GRAPHITE WITH SS304 RENFORCEMENT',
        'EXPANDED GRAPHITE WITH SS304 REINFORCEMENT',
    ]),
    ('FLEXIBLE GRAPHITE WITH SS316 INSERT', ['FLEXIBLE GRAPHITE REINFORCED W/SS316',
                                              'FLEXIBLE GRAPHITE REINFORCED WITH SS316',
                                              'GRAPHITE WITH SS316L INSERT', 'GRAPHITE WITH SS316 INSERT']),
    ('FLEXIBLE GRAPHITE WITH SS304 INSERT', ['GRAPHITE WITH SS304 INSERT']),
    ('FLEXIBLE GRAPHITE WITH STEEL INSERT', ['GRAPHITE WITH MS INSERT', 'GRAPHITE WITH STEEL INSERT',
                                              'GRAPHITE WITH 2 METAL FOILS']),
    ('CORRUGATED GRAPHITE WITH SS316', ['CORRUGATED GASKET SS316 ENCAPSULATED WITH GRAPHITE',
                                        'CORRUGATED GASKET 316 ENCAPSULATED']),
    ('EXPANDED GRAPHITE', ['EXPANDED GRAPHITE', '98% EXPANDED GRAPHITE', 'EXFOLIATED GRAPHITE',
                           'EXFOLIATED EXPANDED GRAPHITE', 'FLEXIBLE/EXPANDED GRAPHITE',
                           'LEXIBLE/EXPANDED GRAPHITE']),
    ('GRAPHITE', ['GRAPHITE', 'GRAFOIL', 'FLEXIBLE GRAPHITE', 'GRAPHOIL']),
    # --- Thermiculite / high-temp ---
    ('THERMICULITE 835', ['THERMICULITE 835', 'THERMICULIT 835']),
    ('THERMICULITE 715', ['THERMICULITE 715', 'FLEXITALLIC TYPE THERMICULITE 715',
                          'THERMICULIT 715', 'THERMICULITE 715 OR EQUIVALENT',
                          'FLEXITALLIC TYPE THERMICULITE 715 OR EQUIVALENT']),
    ('THERMICULITE', ['THERMICULITE', 'THERMICULIT']),
    ('LEAKBLOK P200', ['LEAKBLOK P200', 'LEAKBOK P200', 'LEAKBLOK P 200']),
    # --- Rubber family ---
    ('VITON GASKET', ['VITON GASKET']),
    ('VITON', ['VITON', 'FKM', 'FLUOROCARBON RUBBER', 'FLUOROELASTOMER']),
    ('NEOPRENE', ['NEOPRENE', 'CHLOROPRENE', 'POLYCHLOROPRENE', 'CHLOROPRENE RUBBER',
                  'POLYCHLOROPRENE RUBBER']),
    ('EPDM', ['EPDM', 'EPDM RUBBER']),
    ('NATURAL RUBBER', ['NATURAL RUBBER', 'POLYISOPRENE RUBBER']),
    ('NITRILE BUTADIENE RUBBER', ['NBR', 'NITRILE BUTADIENE RUBBER', 'NITRILE RUBBER',
                                   'NITRILE', 'BUNA-N', 'BUNA N', 'HNBR RUBBER', 'HNBR']),
    ('SBR', ['SBR', 'STYRENE-BUTADIENE RUBBER', 'STYRENE BUTADIENE RUBBER',
             'ASBESTOS FREE (WITH SBR)', 'ASBESTOS FREE WITH SBR']),
    ('BUTYL RUBBER', ['BUTYL RUBBER', 'BUTYL', 'POLYISOBUTYLENE RUBBER']),
    ('SILICONE RUBBER', ['SILICONE RUBBER', 'SILICONE']),
    ('CHLOROSULFONATED RUBBER', ['CHLOROSULFONATED RUBBER', 'HYPALON']),
    ('POLYURETHANE RUBBER', ['POLYURETHANE RUBBER', 'THERMOPLASTIC POLYURETHANE RUBBER',
                              'POLYURETHANE']),
    ('THERMOPLASTIC RUBBER', ['THERMOPLASTIC RUBBER', 'TPR', 'STYRENE-ETHYLENE-BUTYLENE-STYRENE',
                               'SEBS', 'STYRENE-ISOPRENE-STYRENE', 'SIS',
                               'ACRYLONITRILE BUTADIENE STYRENE RUBBER', 'ABS RUBBER']),
    ('ETHYLENE VINYL ACETATE RUBBER', ['ETHYLENE-VINYL ACETATE RUBBER', 'EVA RUBBER', 'EVA']),
    ('POLYAMIDE RUBBER', ['POLYAMIDE RUBBER', 'NYLON RUBBER']),
    ('RUBBER', ['RUBBER', 'REINFORCED CHLOROPRENE RUBBER']),  # generic — will be flagged
    # --- Compressed Asbestos (obsolete, flag) ---
    ('COMPRESSED ASBESTOS', ['COMPRESSED ASBESTOS', 'CAF', 'ASBESTOS FIBER',
                              'IS 2712', 'ASBESTOS']),
]


# --- Normalise INSERT material label ---
_INSERT_MATERIAL_NORM = {
    'SS304': 'SS304', 'SS 304': 'SS304', '304': 'SS304', 'SS304L': 'SS304L',
    'SS316': 'SS316', 'SS 316': 'SS316', '316': 'SS316', 'SS316L': 'SS316L',
    'MS': 'MS', 'MILD STEEL': 'MS',
    'STEEL': 'STEEL',
}


def _normalize_insert(raw: str) -> str:
    key = re.sub(r'\s+', ' ', raw.strip().upper())
    return _INSERT_MATERIAL_NORM.get(key, key)


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
    # CN/ZN plating variants (cadmium/zinc plated = LCS base material)
    'CN/ZN PLATED CARBON STEEL': 'LOW CARBON STEEL',
    'CN/ZN PLATED': 'LOW CARBON STEEL',
    'ZINC PLATED CARBON STEEL': 'LOW CARBON STEEL',
    'ZINC PLATED': 'LOW CARBON STEEL',
    'CARBON STEEL': 'LOW CARBON STEEL',
    'SS316L': 'SS316L', 'SS 316L': 'SS316L',
    'SS316': 'SS316', 'SS 316': 'SS316', '316 SS': 'SS316', '316SS': 'SS316',
    'SS304L': 'SS304L', 'SS 304L': 'SS304L',
    'SS304': 'SS304', 'SS 304': 'SS304', '304 SS': 'SS304', '304SS': 'SS304',
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
    # UNS material (e.g. UNS S32205, UNS S32750, UNS N08825)
    m = re.search(r'\bUNS\s+([A-Z]\d{4,6})\b', desc)
    if m:
        return f"UNS {m.group(1)}"
    # AISI grade
    if re.search(r'AISI\s*316L\b', desc): return 'SS316L'
    if re.search(r'AISI\s*316\b', desc): return 'SS316'
    if re.search(r'AISI\s*304L\b', desc): return 'SS304L'
    if re.search(r'AISI\s*304\b', desc): return 'SS304'
    for raw, canon in _RTJ_MOC_MAP.items():
        if raw.upper() in desc:
            return canon
    # "STAINLESS STEEL" / "INOX" / "ACIER" (French for steel) + grade number
    if 'STAINLESS STEEL' in desc or 'INOX' in desc or 'ACIER' in desc:
        if re.search(r'\b316L\b', desc):
            return 'SS316L'
        if re.search(r'\b316\b', desc):
            return 'SS316'
        if re.search(r'\b304L\b', desc):
            return 'SS304L'
        if re.search(r'\b304\b', desc):
            return 'SS304'
    return None


def _extract_rtj_groove(desc: str) -> str:
    if re.search(r'\bOVAL\b', desc):
        return 'OVAL'
    return 'OCT'  # octagonal is default for RTJ


def _extract_rtj_hardness(desc: str) -> tuple[int | None, str | None]:
    """Extract hardness: returns (bhn_int_or_None, display_string_or_None)."""
    # "90 BHN MAX" / "90 BHN" / "90 HB"
    m = re.search(r'(\d+)\s*(?:BHN|HB)\b', desc, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        return val, f"{val} BHN HARDNESS"
    # "MAX HARDNESS OF 22 HRC" / "22 HRC MAX" / "HARDNESS 22 HRC"
    m = re.search(r'(?:MAX(?:IMUM)?\s*HARDNESS(?:\s*OF)?\s*(\d+)|(\d+)\s*HRC\b)', desc, re.IGNORECASE)
    if m:
        val = m.group(1) or m.group(2)
        return None, f"MAX HARDNESS {val} HRC"
    # "83 HRBW MAX" / "HARDNESS 83 HRBW"
    m = re.search(r'(\d+)\s*HRBW\b', desc, re.IGNORECASE)
    if m:
        return None, f"MAX HARDNESS {m.group(1)} HRBW"
    return None, None


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
        if outer_m:
            mat_raw = next((g for g in outer_m.groups() if g), None)
            outer_ring = _norm_sw_material(mat_raw) if mat_raw else None
        inner_m = _SW_INNER_RING_PATTERN.search(desc)
        if inner_m:
            mat_raw = next((g for g in inner_m.groups() if g), None)
            inner_ring = _norm_sw_material(mat_raw) if mat_raw and mat_raw.upper() not in ('SS', 'IR') else None

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
    # Explicit "OD nnn ... ID nnn" / "O/D nnn ... I/D nnn" notation
    od_m = re.search(r'\bO/?D\s*(\d+(?:[.,]\d+)?)', desc, re.IGNORECASE)
    id_m = re.search(r'\bI/?D\s*(\d+(?:[.,]\d+)?)', desc, re.IGNORECASE)
    if od_m and id_m:
        od = float(od_m.group(1).replace(',', '.'))
        id_ = float(id_m.group(1).replace(',', '.'))
        # Thickness: find a number adjacent to MM that is neither OD nor ID
        thk = None
        for m2 in re.finditer(r'\b(\d+(?:[.,]\d+)?)\s*(?:[Xx×]\s*)?MM\b', desc, re.IGNORECASE):
            val = float(m2.group(1).replace(',', '.'))
            if val != od and val != id_:
                thk = val
                break
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
    # Normalize Unicode dashes/minuses (U+2212 minus, en-dash, em-dash) to ASCII hyphen
    # so patterns like "OR−SS316" are treated the same as "OR-SS316"
    desc = desc.replace('\u2212', '-').replace('\u2013', '-').replace('\u2014', '-')

    _base_sw_none = {'sw_winding_material': None, 'sw_filler': None,
                     'sw_inner_ring': None, 'sw_outer_ring': None}
    _base_rtj_none = {'rtj_groove_type': None, 'rtj_hardness_bhn': None, 'rtj_hardness_spec': None}

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
            od_mm, id_mm = _od_id_values(od_id)
            kamm = _extract_kamm_components(desc)
            return {
                'size': f"OD {od_mm}MM x ID {id_mm}MM",
                'size_type': 'OD_ID',
                'od_mm': od_mm, 'id_mm': id_mm,
                'rating': None,
                'gasket_type': 'KAMM',
                'moc': None,  # built from sw_winding_material by rules engine
                'face_type': None,
                'thickness_mm': _extract_thickness(desc),
                'standard': None,  # no standard for custom OD/ID KAMM
                'special': _extract_special(desc),
                **kamm, **_base_rtj_none,
                'confidence': 'HIGH' if (od_mm and id_mm and kamm.get('sw_winding_material')) else 'MEDIUM',
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
        # Hardness from description text (BHN/HRC/HRBW)
        hardness_bhn, hardness_spec = _extract_rtj_hardness(desc)
        if hardness_bhn is None and hardness_spec is None:
            hardness_bhn = _RTJ_HARDNESS.get(rtj_moc) if rtj_moc else None
            hardness_spec = f"{hardness_bhn} BHN HARDNESS" if hardness_bhn else None
        # Extract ring number from description text — supports R, RX, BX prefixes (hyphen or space separator)
        m_ring = re.search(r'\b(RX|BX|R)[-\s]?(\d{2,4})\b', desc, re.IGNORECASE)
        ring_from_desc = None
        if m_ring:
            prefix = m_ring.group(1).upper()
            num = m_ring.group(2)
            ring_from_desc = f"{prefix}-{num}"
        rating = _extract_rating(desc)
        return {
            'size': size, 'size_type': size_type,
            'od_mm': None, 'id_mm': None,
            'rating': rating,
            'gasket_type': 'RTJ',
            'moc': rtj_moc,
            'face_type': None,
            'thickness_mm': None,
            'standard': _extract_standard(desc) or 'ASME B16.20',
            'special': _extract_special(desc),
            **_base_sw_none,
            'rtj_groove_type': groove,
            'rtj_hardness_bhn': hardness_bhn,
            'rtj_hardness_spec': hardness_spec,
            'ring_no': ring_from_desc,
            'confidence': 'HIGH' if (size and rating and rtj_moc) else 'MEDIUM',
        }

    # --- Priority 5: SPIRAL WOUND ---
    if _SW_DETECT_PATTERN.search(desc):
        size, size_type = _extract_size(desc)
        sw = _extract_sw_components(desc)
        rating = _extract_rating(desc)
        return {
            'size': size, 'size_type': size_type,
            'od_mm': None, 'id_mm': None,
            'rating': rating,
            'gasket_type': 'SPIRAL_WOUND',
            'moc': None,
            'face_type': None,
            'thickness_mm': _extract_thickness(desc),
            'standard': _extract_standard(desc),
            'special': _extract_special(desc),
            **sw, **_base_rtj_none,
            'confidence': 'HIGH' if (size and rating and sw['sw_winding_material']) else 'MEDIUM',
        }

    # --- Priority 6: OD × ID soft cut ---
    od_id = _OD_ID_PATTERN.search(desc)
    if od_id:
        od_mm, id_mm = _od_id_values(od_id)
        return {
            'size': f"OD {od_mm}MM x ID {id_mm}MM",
            'size_type': 'OD_ID',
            'od_mm': od_mm,
            'id_mm': id_mm,
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
    rating = _extract_rating(desc)
    face = _extract_face(desc)
    return {
        'size': size, 'size_type': size_type,
        'od_mm': None, 'id_mm': None,
        'rating': rating,
        'gasket_type': 'SOFT_CUT',
        'moc': moc,
        'face_type': face,
        'thickness_mm': _extract_thickness(desc),
        'standard': _extract_standard(desc),
        'special': _extract_special(desc),
        **_base_sw_none, **_base_rtj_none,
        'confidence': 'HIGH' if (size and rating and moc and face) else ('MEDIUM' if (size and moc) else 'LOW'),
    }


def _extract_size(desc: str) -> tuple[str | None, str]:
    from data.reference_data import NB_TO_NPS, normalize_size
    # "NB100", "NB 40", "DN15", "DN 25" — DN and NB are identical (metric nominal bore)
    m = re.search(r'\b(?:NB|DN)\s*(\d+(?:\.\d+)?)\b', desc, re.IGNORECASE)
    if m:
        return f"{int(float(m.group(1)))} NB", 'NB'
    # "100NB", "100 NB", "15DN", "25 DN"
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:NB|DN)\b', desc, re.IGNORECASE)
    if m:
        return f"{int(float(m.group(1)))} NB", 'NB'
    # "NPS 2", "NPS 1.5", "NPS: 16" — NPS prefix with optional colon
    m = re.search(r'\bNPS\s*:?\s*(\d+(?:\.\d+)?)\b', desc, re.IGNORECASE)
    if m:
        return m.group(1) + '"', 'NPS'
    # "24GASKET", "32GASKET" — bare number at start of KAMM/SPW descriptions
    m = re.match(r'^(\d+(?:\.\d+)?)\s*GASKET\b', desc, re.IGNORECASE)
    if m:
        return m.group(1) + '"', 'NPS'
    # "1-1/2\"" / "2-1/2\"" — dash used as separator between whole number and fraction
    m = re.search(r'(\d+)-(\d+/\d+)\s*["\']', desc)
    if m:
        norm = normalize_size(f"{m.group(1)} {m.group(2)}")
        if norm:
            return norm, 'NPS'
    # "1.1/2\"" / "1.1/4\"" — period used as separator instead of space (customer data quality)
    m = re.search(r'(\d+)\.(\d+/\d+)\s*["\']', desc)
    if m:
        norm = normalize_size(f"{m.group(1)} {m.group(2)}")
        if norm:
            return norm, 'NPS'
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
    # "8, GASKET (RTJ)..." or "4, GASKET (RTJ)..." — leading NPS before comma
    _VALID_NPS = {'0.5','0.75','1','1.25','1.5','2','2.5','3','3.5','4','5','6','8','10','12','14','16','18','20','24','26','28','30','32','36','42','48'}
    m = re.match(r'^(\d+(?:\.\d+)?)\s*,', desc)
    if m and m.group(1) in _VALID_NPS:
        return m.group(1) + '"', 'NPS'
    # "rating,size,description" structured CSV — e.g. "150#,0.75,Neoprene" / "300 RF,0.75,API 601..."
    m = re.search(r'[^,]+,\s*(\d+(?:\.\d+)?)\s*,', desc)
    if m and m.group(1) in _VALID_NPS:
        return m.group(1) + '"', 'NPS'
    # "4300#SPIRAL WOUND" / "2150#SPIRAL" — NPS size digit(s) mashed directly with rating+#
    # Match: (valid NPS size)(valid rating class)# at word boundary
    m = re.search(r'\b(\d+(?:\.\d+)?)(150|300|600|900|1500|2500|3000)#', desc, re.IGNORECASE)
    if m and m.group(1) in _VALID_NPS:
        return m.group(1) + '"', 'NPS'
    return None, 'UNKNOWN'


def _nb_to_nps(nb: int, nb_map: dict) -> str:
    """Convert NB (mm) to NPS inch string, or return raw value if not in map."""
    return nb_map.get(nb, f'{nb}"')


_VALID_RATINGS = frozenset(('150', '300', '600', '900', '1500', '2500', '3000', '5000', '6000', '10000', '15000'))


def _extract_rating(desc: str) -> str | None:
    m = re.search(r'PN\s*(\d+)', desc, re.IGNORECASE)
    if m:
        return f"PN {m.group(1)}"
    # API 6A pressure ratings: "API 5000", "API 10000", "API 15000"
    m = re.search(r'\bAPI[-\s]?(\d{4,5})\b', desc, re.IGNORECASE)
    if m and m.group(1) in _VALID_RATINGS:
        return f"API {m.group(1)}"
    # "#600", "#150 " — hash-prefix format (e.g. "DN25 #150", "DN450#150")
    # Must check BEFORE "NNN#" to avoid matching NB size number before the hash
    m = re.search(r'#\s*(150|300|600|900|1500|2500|3000|5000)\b', desc, re.IGNORECASE)
    if m:
        return f"{m.group(1)}#"
    # "CL150", "CLASS 300", "150#", "300LB", "150 LBS"
    # Note: trailing \b after # fails at end-of-string since # is non-word; use # as standalone delimiter
    m = re.search(r'(?:CL|CLASS)\s*[-.\s]*(\d+)|(\d+)\s*#|(\d+)\s*LBS?\b', desc, re.IGNORECASE)
    if m:
        val = m.group(1) or m.group(2) or m.group(3)
        if val in _VALID_RATINGS:
            return f"{val}#"
    # "4300#" / "2150#" — mashed size+rating; extract the trailing rating part
    m = re.search(r'\b\d+(?:\.\d+)?(150|300|600|900|1500|2500|3000)#', desc, re.IGNORECASE)
    if m:
        return f"{m.group(1)}#"
    # "16\"-600 RF" or "6\"/150" — SIZE-RATING dash/slash format
    m = re.search(r'\d+["\']\s*[-/]\s*(150|300|600|900|1500|2500|3000)', desc, re.IGNORECASE)
    if m:
        return f"{m.group(1)}#"
    # "300/600RF" / "300/600" — dual rating; use the higher (more conservative) value
    m = re.search(r'\b(150|300|600|900|1500|2500)/(300|600|900|1500|2500|3000)\b', desc, re.IGNORECASE)
    if m:
        return f"{m.group(2)}#"  # group(2) is always the higher value in this pattern
    # Standalone rating class with no suffix (e.g. "DN80-150" not handled above)
    # Negative lookahead: don't match if followed by NB/DN (that's a size, not a rating)
    m = re.search(r'(?:[-\s])(150|300|600|900|1500|2500|3000)(?=\s|$|[,;#])(?!\s*(?:NB|DN)\b)', desc)
    if m:
        return f"{m.group(1)}#"
    return None


def _extract_moc(desc: str) -> str | None:
    # 1. Generic "{base_moc} WITH {SS304|SS316|MS|STEEL} INSERT" pattern — check FIRST
    #    e.g. "EPDM RUBBER WITH SS304 INSERT", "GRAPHITE WITH SS316 INSERT"
    #    Must come before keyword scan so "EPDM" doesn't match before the full composite
    m = re.search(
        r'(.+?)\s+WITH\s+(SS304L?|SS316L?|UNS\s*\w+|MS|STEEL|MILD\s*STEEL)\s+INSERT',
        desc, re.IGNORECASE,
    )
    if m:
        base_text = m.group(1).strip()
        insert_raw = m.group(2).strip()
        insert = _normalize_insert(insert_raw)
        # Find the base MOC from the base_text portion
        base_moc = None
        for moc_name, keywords in _MOC_KEYWORDS:
            if any(kw.upper() in base_text.upper() for kw in keywords):
                base_moc = moc_name
                break
        if base_moc:
            return f"{base_moc} WITH {insert} INSERT"

    # 2. Try phrase/keyword matching (most specific entries are listed first)
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
        if 'SERIES B' in desc:
            return 'ASME B16.47 ( SERIES B )'
        if 'SERIES A' in desc:
            return 'ASME B16.47 ( SERIES A )'
        return 'ASME B16.47'
    if 'B16.20' in desc or re.search(r'B16/A\b', desc, re.IGNORECASE):
        return 'ASME B16.20'
    if 'B16.21' in desc:
        return 'ASME B16.21'
    if re.search(r'\bAPI\s*6A\b', desc):
        return 'API 6A'
    if re.search(r'\bAPI\s*6D\b', desc):
        return 'API 6D'
    if re.search(r'\bAPI\s*STD[-\s]?601\b', desc):
        return 'API STD 601'
    if re.search(r'EN\s*1514|BS\s*7531|\bDIN\b', desc):
        return 'EN 1514-1'
    # "ANSI" alone → leave as None; let type-specific rules apply correct ASME standard
    # "ASME" alone without specific B16 standard → return None for same reason
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
