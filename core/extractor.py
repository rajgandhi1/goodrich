from __future__ import annotations
"""
Extracts structured gasket fields from raw description strings.
Primary: LLM (OpenAI API). Fallback: returns all-null stub (flagged for manual review).
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
- size: If NPS/inch given (e.g. "6\\"", "1.5\\"") use as-is. If NB or DN given (metric nominal bore), output as "X NB" e.g. "25 NB", "100 NB", "450 NB" — do NOT convert to inches. DN = NB (identical). For OD×ID dimensions use "OD NNNmm x ID NNNmm". Set size_type accordingly: NPS for inch sizes, NB for NB/DN sizes, OD_ID for OD/ID dimensions. If the description starts with or contains the word "INCH" as a unit indicator and a bare number appears elsewhere (especially at the end after a comma, e.g. "INCH GASKET, PTFE, FULL FACE ASME B16.21, 1.5 MM THK, ASME CLASS 150,1"), treat that bare trailing number as the NPS size in inches (output "1\\"" for 1). Never convert an NPS inch size to NB/DN format.
- rating: use format "150#", "300#", "PN 10", "PN 16". Valid ASME classes: 150, 300, 600, 900, 1500, 2500, 3000.
- gasket_type: SPIRAL_WOUND if description mentions "spiral wound", "spiral seal", "spiral winding", "SPW", "SPWD", "SPRL-WND", "WND", "SW gasket", "SPIRL WOUND" (typo), "GASKET SPIRAL" / "GASKETSPIRAL" / "GASKETSSPIRAL" (shorthand where trailing number is NPS size e.g. "GASKETSPIRAL4" = 4" spiral wound), or combination of winding material + filler + ring. "WND" alone means winding (e.g. "ALLOY 20 WND PTFE FILL ALLOY 20 I/R CS O/R" = SPIRAL_WOUND with ALLOY 20 winding, PTFE filler, ALLOY 20 inner ring, CS outer ring)
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
- "NON-METALLIC GASKET", "NON METALLIC GASKET", or any description containing "non-metallic" / "non metallic" always means SOFT_CUT — never SPIRAL_WOUND, RTJ, KAMM, or DJI.
- confidence: HIGH if all key fields clear, LOW if ambiguous"""


def extract_batch(items: list[dict], progress_cb=None) -> list[dict]:
    """
    Extract structured fields for all items.
    LLM is primary — every description goes to gpt-4o-mini.
    Regex is a silent fallback only when LLM is unavailable or fails.
    Deduplicates identical descriptions before batching.
    """
    # Normalize embedded newlines (e.g. from Shift+Enter in Excel or CSV) to spaces
    for item in items:
        if item.get('description'):
            item['description'] = re.sub(r'[\r\n]+', ' ', item['description']).strip()

    unique_descs_list = list({item['description'] for item in items})
    total = len(unique_descs_list)
    cache = {}
    done = 0

    client = _get_openai_client()
    for batch_start in range(0, len(unique_descs_list), _BATCH_SIZE):
        batch = unique_descs_list[batch_start:batch_start + _BATCH_SIZE]
        llm_results = _llm_extract_batch(client, batch) if client else [None] * len(batch)
        for desc, llm_result in zip(batch, llm_results):
            cache[desc] = llm_result if llm_result else _null_extract()
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
# Fallback stub — used when LLM is unavailable or fails
# ---------------------------------------------------------------------------

def _null_extract() -> dict:
    """Return an all-null extraction so rules.py flags everything as missing."""
    return {
        'size': None, 'size_type': 'UNKNOWN', 'od_mm': None, 'id_mm': None,
        'rating': None, 'gasket_type': 'SOFT_CUT', 'moc': None,
        'face_type': None, 'thickness_mm': None, 'standard': None,
        'special': 'LLM unavailable — review manually',
        'sw_winding_material': None, 'sw_filler': None,
        'sw_inner_ring': None, 'sw_outer_ring': None,
        'rtj_groove_type': None, 'rtj_hardness_bhn': None,
        'ring_no': None, 'confidence': 'LOW',
    }
