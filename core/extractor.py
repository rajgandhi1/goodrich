from __future__ import annotations
"""
Extracts structured gasket fields from raw description strings.
Primary: LLM (OpenAI API). Fallback: returns all-null stub (flagged for manual review).
"""
import os
import re
import json
import time
import hashlib
import asyncio
import logging
import threading
import queue as _stdlib_queue

logger = logging.getLogger(__name__)

# Retained for backwards-compat with app.py which resets this on key change
_openai_client = None

# ---------------------------------------------------------------------------
# Regex-based gasket type detector — overrides LLM to prevent misclassification
# ---------------------------------------------------------------------------

_SW_RE = re.compile(
    r'\bSPIRAL[\s\-]?WOUND\b|\bSPRL[\s\-]?WND\b|\bSPWD?\b|'
    r'\bS\.?W\.\s*GASKET|\bWND\b',
    re.IGNORECASE,
)
_RTJ_RE = re.compile(
    r'\bRTJ\b|\bR\.T\.J\b|\bRING[\s\-]TYPE\s+JOINT\b|'
    r'\bOCTAGONAL\s+RTJ\b|\bOCTAGONAL\s+RING\b|\bOVAL\s+RING\b|'
    r'\bJOINT\s+TOR[EI]\b|\bJOINT\s+TORIQUE\b',
    re.IGNORECASE,
)
_KAMM_RE = re.compile(r'\bKAMM(?:PROFILE)?\b|\bCAM[\s\-]?PROFILE\b', re.IGNORECASE)
_DJI_RE = re.compile(r'\bDOUBLE[\s\-]JACKET(?:ED)?\b', re.IGNORECASE)
_ISK_RE = re.compile(
    r'\bINSULATING\s+GASKET\b|\bINSULATION\s+GASKET\b|'
    r'\bISK\b|\bINSULATION\s+KITS?\b|\bINSULATING\s+KITS?\b|'
    r'\bFLANGE\s+ISOLATION\b|\bISOLATION\s+GASKET\b|'
    r'\bINST\.?\s+KIT\b',
    re.IGNORECASE,
)


def _regex_detect_type(desc: str) -> str | None:
    """Return gasket_type if clearly detectable from keywords, else None."""
    if _SW_RE.search(desc):
        return 'SPIRAL_WOUND'
    if _KAMM_RE.search(desc):
        return 'KAMM'
    if _DJI_RE.search(desc):
        return 'DJI'
    # Check ISK before RTJ: "RTJ" in ISK descriptions often refers to the mating flange,
    # not the gasket itself (e.g. "ISK for RTJ flanges", "WAFER 1500 RTJ")
    if _ISK_RE.search(desc):
        return 'ISK'
    if _RTJ_RE.search(desc):
        return 'RTJ'
    return None

_CACHE_TTL = 30 * 24 * 3600  # 30 days — gasket specs are stable


def _get_redis():
    """Return a Redis client if REDIS_URL is set, else None."""
    url = os.environ.get('REDIS_URL')
    if not url:
        return None
    try:
        import redis
        return redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    except Exception:
        return None


def _cache_key(desc: str) -> str:
    digest = hashlib.sha256(desc.upper().strip().encode()).hexdigest()[:20]
    return f'gq:{digest}'

_FIELD_SCHEMA = """{
  "size": "e.g. 2\\" or OD 584MM or null",
  "size_type": "NPS | NB | DN | OD_ID | UNKNOWN",
  "od_mm": null,
  "id_mm": null,
  "rating": "e.g. 150# or PN 10 or null",
  "gasket_type": "SOFT_CUT | SPIRAL_WOUND | RTJ | KAMM | DJI | ISK | ISK_RTJ",
  "moc": "normalized material name or null (leave null for spiral wound — built from sw_* fields)",
  "face_type": "RF | FF | null",
  "thickness_mm": 3,
  "standard": "ASME B16.21 | ASME B16.20 | EN 1514-1 | other | null",
  "special": "any special requirements e.g. FOOD GRADE or null",
  "isk_style": "e.g. STYLE-CS | STYLE-N | TYPE-E | TYPE-F | null (ISK/ISK_RTJ only — style identifier)",
  "isk_fire_safety": "FIRE SAFE | NON FIRE SAFE | null (ISK/ISK_RTJ only)",
  "dji_filler": "e.g. GRAPHITE | ASBESTOS FREE | CERAMIC | null (DJI only — fill material)",
  "sw_winding_material": "e.g. SS304 | SS316 | null (spiral wound only)",
  "sw_filler": "e.g. GRAPHITE | PTFE | MICA | null (spiral wound only)",
  "sw_inner_ring": "e.g. SS304 | CS | null (spiral wound only)",
  "sw_outer_ring": "e.g. CS | SS304 | null (spiral wound only)",
  "rtj_groove_type": "OCT | OVAL | null (RTJ only)",
  "rtj_hardness_bhn": "e.g. 90 | 130 | 160 | null (RTJ only — BHN hardness number)",
  "ring_no": "e.g. R-24 | R-37 | null (RTJ only — ring number if explicitly stated in description)",
  "confidence": "HIGH | MEDIUM | LOW"
}"""

_BATCH_SIZE = 20  # descriptions per LLM call

_BATCH_SYSTEM_PROMPT = f"""You are a gasket spec extraction assistant. Extract fields from customer descriptions and return ONLY valid JSON with key "results" (array, same order as input).

Gasket types:
1. SOFT_CUT: flat ring (RF/FF) — CNAF, PTFE, NEOPRENE, EPDM, RUBBER, GRAPHITE, EXPANDED GRAPHITE, VITON, NON ASBESTOS, NBR, SBR, SILICONE, BUTYL, ARAMID, CERAMIC, THERMICULITE, CORK, LEATHER. "EXPANDED GRAPHITE WITH SS304/SS316 REINFORCEMENT" = SOFT_CUT (metallic insert/tanged, NOT spiral wound); set moc accordingly. Any "{{MOC}} WITH SS304/SS316/MS/STEEL INSERT" = SOFT_CUT. "NON-METALLIC/NON METALLIC" = always SOFT_CUT.
2. SPIRAL_WOUND: wound metallic gasket — keywords: spiral wound/SPW/SPWD/SPRL-WND/WND/GASKETSPIRAL(trailing digit=NPS)/SW gasket; or winding material + filler + ring combo. "WND" alone = SPIRAL_WOUND (e.g. "ALLOY 20 WND PTFE FILL ALLOY 20 I/R CS O/R").
3. RTJ: ring type joint — RTJ/R.T.J/ring joint/ring type gasket/octagonal ring/oval ring/JOINT TORE/JOINT TORIQUE/ring no R-nn/RX-nn/BX-nn/API 6A rings.
4. KAMM: Kammprofile/CAMPROFILE/CAM PROFILE — serrated metal core with graphite facing.
5. DJI: Double Jacket — metallic jacket (COPPER/SS316L/SOFT IRON/ARMCO IRON) with filler; dims always OD×ID×THK.
6. ISK: Insulating Gasket Kit (RF/FF flanges) — keywords: Insulating Gasket Kit/Set, Insulation Gasket Kit, ISK, Flange Isolation Gasket (PGS COMMANDER EXTREME), INST. KIT, GSKT INSULATION. GRE G-10/G-11/G10/G11 laminate description = ISK. NOTE: "RTJ" in description may refer to the mating flange, not gasket type — if description says TYPE-F RF or ISK TYPE-F, use ISK not ISK_RTJ.
7. ISK_RTJ: ISK replacing an RTJ groove — keywords: ISK RTJ, ISK TYPE-RTJ, insulating ring type joint.

Schema per item:
{_FIELD_SCHEMA}

Rules:
- size: NPS/inch → as-is (e.g. "6\\""). NB → "X NB" (e.g. "25 NB"), size_type=NB. DN → "DN X" (e.g. "DN 25"), size_type=DN. Do NOT convert NB↔DN or to inches. OD×ID → "OD NNNmm x ID NNNmm". size_type: NPS/NB/DN/OD_ID. Bare trailing number after "INCH" keyword = NPS size in inches. "OD - 35, ID - 12" or "OD-35 ID-12" or "OD: 35" format → od_mm=35, id_mm=12, size_type=OD_ID.
- rating: "150#"/"300#"/"PN 10"/"PN 16". Valid ASME classes: 150/300/600/900/1500/2500/3000.
- thickness_mm: null for RTJ; extract number or null for others. Patterns: "3MM THK", "THK-1.5", "THK 3", "3T" or "T-3" prefix/suffix (e.g. "3T X 1285 OD" or "(Without Rib)3T" → thickness_mm=3), "Ø67 x Ø27 x 3MM" (last dim = thickness).
- Normalize winding materials (sw_winding_material): 304SS/SS 304/AISI 304→SS304; 316SS/316-SS→SS316; 316L→SS316L; SUPER DUPLEX/SDSS→SDSS (UNS S32750); INCOLOY/INCOLOY 825→INCOLOY 825; INCONEL/INCONEL 625→INCONEL 625; "STAINLESS STEEL" alone (no grade)→null.
- Normalize ring materials: CARBON STEEL/MS/C.S./CS→CS; I/R=inner ring, O/R=outer ring (e.g. "ALLOY 20 I/R"=sw_inner_ring=ALLOY 20, "CS O/R"=sw_outer_ring=CS); LTCS→pass through as LTCS. INCOLOY 825/INCONEL 625 rings→keep as-is. "CENTERING RING"/"CENTERING"/"C.R." = outer ring (sw_outer_ring) — e.g. "CS CENTERING RING" → sw_outer_ring=CS; "W/SS CENTERING RING & SS INNER RING" → sw_outer_ring=SS (grade from winding), sw_inner_ring=SS (grade from winding).
- Normalize RTJ MOC: SOFT IRON/SOFTIRON→SOFTIRON; SOFT IRON GALVANISED→SOFTIRON GALVANISED; LOW CARBON STEEL/LCS/CARBON STEEL/CN+ZN PLATED CS→LOW CARBON STEEL; 316 S/STAINLESS STEEL 316→SS316; UNS S32205/UNS S32750→keep as-is. Ring nos: RX53→RX-53, BX 156→BX-156 (space=hyphen). BHN: soft iron=90, LCS=120, SS316=160, INCOLOY 825/INCONEL 625=160. HRBW→BHN conversion: "HARDNESS 83 HRBW" or "83 HRB"→rtj_hardness_bhn=160; "HARDNESS 68 HRBW" or "68 HRB"→rtj_hardness_bhn=120. Always store BHN value (not HRB) in rtj_hardness_bhn.
- Normalize SOFT_CUT moc: EPTFE/E-PTFE/EXPANDED PTFE→"EXPANDED PTFE"; SUPERLITE GF 300/SUPERLITE→"SUPERLITE GF 300"; GYLON→"GYLON".
- SPIRAL_WOUND: sw_winding_material/sw_filler/sw_inner_ring/sw_outer_ring; moc=null. RTJ: moc/rtj_groove_type/rtj_hardness_bhn/ring_no; sw_*=null; standard=ASME B16.20. SOFT_CUT: moc; sw_*/rtj_*=null.
- face_type: RF/FF for SOFT_CUT/ISK/ISK_RTJ; null for SPIRAL_WOUND/RTJ/KAMM/DJI.
- standard: API 6A/API Specs→"API 6A"; B16/A→"ASME B16.20"; ASME B16.21 (soft cut ≤24"); ASME B16.47 (soft cut ≥26"); ASME B16.20 (SW/RTJ ≤24"); ASME B16.47 (SW ≥26"). ISK/ISK_RTJ: extract customer-stated standard verbatim incl. SERIES A/B (e.g. "ASME B16.47 ( SERIES A )").
- special: FOOD GRADE/NACE/LETHAL/EIL APPROVED/NACE MR 0175/API 6A/SERIES B. ISK/ISK_RTJ: capture component material details starting from the material description — include GRE/GLASS REINFORCED EPOXY/NEMA G10/G11 laminate, primary seal, secondary seal, sleeve, insulating washer, metallic washer, core material, PTFE seals. EXCLUDE only these exact boilerplate phrases: "MANUFACTURE STD", "PGS COMMANDER EXTREME", "(125-250 AARH)", "to suit flange", "Standard MANUFACTURE STD WAFER". Do NOT exclude "GLASS REINFORCED EPOXY (NEMA G10)", "GRE G-10", "TEFLON SEALS". DJI: set "AS PER DRAWING" when drawing referenced or when "(WITHOUT RIB)"/"(WITH RIB)" appears.
- isk_style: STYLE-CS = G10/G11 laminate WITH metallic core (SS316/UNS S32760/Inconel/duplex etc) — e.g. "GRE G10 laminate, Super Duplex UNS S32760 Steel core". STYLE-N = only when explicitly stated "STYLE-N"/"STYLE N" in description. TYPE-E = only when "Type E" or "(type E)" explicitly stated. TYPE-F = only when "Type F" or "(type F)" explicitly stated. NULL if none explicitly stated (do NOT default to STYLE-N). "Type F" + G10/G11 laminate + metallic core → use STYLE-CS (not TYPE-F).
- isk_fire_safety: Extract from description. "FIRE SAFE"/"(FIRE SAFE)"/"FS" → "FIRE SAFE". "NON FIRE SAFE"/"NON-FIRE SAFE"/"(NON FIRE SAFE)"/"NFS"/"(NON-FIRE SAFE)" → "NON FIRE SAFE". Domain rule: PTFE spring-energised/pressure-energised seal (PTFE SS PRES ENRG, SPRING ENERGISED SEAL, SPIRAL SPRING) → "NON FIRE SAFE"; TEFLON/PTFE flat seal (W/TEFLON SEALS, PTFE SEAL without spring) → "FIRE SAFE". Null if not determinable.
- ISK size parsing: packed formats like "10150#INSULATING GASKET" → size="10\\"", rating="150#"; "32INST. KIT GASKET RF 600#" → size="32\\"", rating="600#"; "2INSULATING GASKET KIT 600#" → size="2\\"", rating="600#". "NPS: 1 Th: 9,09" → size="1\\"", thickness_mm=9.09 (European decimal comma). "1+1/2" → size="1-1/2\\"". EN packed sizes: "EN 1514-1 25 PN16" or "EN 151425PN16" → size="DN 25", rating="PN 16". face_type: FF for EN/PN-rated ISK (unless stated otherwise).
- dji_filler: GRAPHITE/ASBESTOS FREE/ARMCO IRON/other. Null = rules engine defaults GRAPHITE.
- Brand name SOFT_CUT (KROLLER & ZILLER/KLINGER/DONIT/GARLOCK/SUPERLITE + grade code) → moc=full brand+grade. "WITH SPACER"=SOFT_CUT, capture in special.
- confidence: HIGH if all key fields clear; LOW if ambiguous."""

_ASME_CLASSES = r'150|300|600|900|1500|2500|3000'

_PACKED_ISK_RE1 = re.compile(
    rf'^(\d{{1,4}})({_ASME_CLASSES})#(\s*(?:INST|INSUL))',
    re.IGNORECASE,
)
_PACKED_ISK_RE2 = re.compile(
    r'^(\d{1,4})(INST(?:ULATING|\.?\s)|INSULATING)',
    re.IGNORECASE,
)


def _preprocess_isk_packed(desc: str) -> str:
    """Expand compact ISK size+rating formats to help LLM parse them correctly.
    Examples:
      '10150#INSULATING GASKET KIT' → '10" 150# INSULATING GASKET KIT'
      '32INST. KIT GASKET RF 600#'  → '32" INST. KIT GASKET RF 600#'
      '2INSULATING GASKET KIT 600#' → '2" INSULATING GASKET KIT 600#'
    """
    # Pattern 1: size+class# packed e.g. "10150#INSULATING"
    m = _PACKED_ISK_RE1.match(desc)
    if m:
        return _PACKED_ISK_RE1.sub(r'\1" \2#\3', desc, count=1)
    # Pattern 2: size directly glued to ISK keyword e.g. "32INST." or "2INSULATING"
    m = _PACKED_ISK_RE2.match(desc)
    if m:
        return _PACKED_ISK_RE2.sub(r'\1" \2', desc, count=1)
    return desc


def extract_batch(items: list[dict], progress_cb=None) -> list[dict]:
    """
    Extract structured fields for all items.
    1. Checks Redis cache first — cached descriptions skip the LLM entirely.
    2. Remaining descriptions are batched and sent to AsyncOpenAI concurrently.
    3. New LLM results are stored back to Redis (TTL 30 days).
    progress_cb(done, total) is called from the main thread.
    """
    for item in items:
        if item.get('description'):
            item['description'] = re.sub(r'[\r\n]+', ' ', item['description']).strip()
            item['description'] = _preprocess_isk_packed(item['description'])

    unique_descs_list = list({item['description'] for item in items})
    total = len(unique_descs_list)
    cache: dict = {}

    # --- Redis cache lookup ---
    r = _get_redis()
    uncached: list[str] = []
    if r:
        for desc in unique_descs_list:
            try:
                hit = r.get(_cache_key(desc))
                if hit:
                    cache[desc] = json.loads(hit)
                else:
                    uncached.append(desc)
            except Exception:
                uncached.append(desc)
        if len(cache) > 0:
            logger.info(f'Redis cache: {len(cache)}/{total} hits, {len(uncached)} need LLM')
    else:
        uncached = unique_descs_list

    # Signal progress for cache hits immediately
    if progress_cb and len(cache) > 0:
        progress_cb(len(cache), total)

    # --- LLM extraction for uncached descriptions ---
    api_key = os.environ.get('OPENAI_API_KEY') or _get_streamlit_secret('OPENAI_API_KEY')

    if not uncached:
        pass  # all served from cache
    elif not api_key:
        for desc in uncached:
            cache[desc] = _null_extract()
    else:
        batches = [uncached[i:i + _BATCH_SIZE] for i in range(0, len(uncached), _BATCH_SIZE)]
        progress_q: _stdlib_queue.SimpleQueue = _stdlib_queue.SimpleQueue()
        batch_results: list = []

        async def _do_batch_async(async_client, batch: list[str]):
            result = await _llm_extract_batch_async(async_client, batch)
            progress_q.put(len(batch))
            return batch, result

        async def _run_all(key: str):
            from openai import AsyncOpenAI
            async_client = AsyncOpenAI(api_key=key, timeout=60.0)
            return await asyncio.gather(*[_do_batch_async(async_client, b) for b in batches])

        def _bg():
            batch_results.extend(asyncio.run(_run_all(api_key)))

        t = threading.Thread(target=_bg, daemon=True)
        t.start()

        done = len(cache)  # start from cache hits already reported
        while t.is_alive():
            try:
                n = progress_q.get(block=False)
                done += n
                if progress_cb:
                    progress_cb(done, total)
            except _stdlib_queue.Empty:
                time.sleep(0.05)
        t.join()

        while True:
            try:
                n = progress_q.get(block=False)
                done += n
                if progress_cb:
                    progress_cb(done, total)
            except _stdlib_queue.Empty:
                break

        for batch, results in batch_results:
            for desc, result in zip(batch, results):
                extracted = result if result else _null_extract()
                # Override gasket_type if regex detects a non-SOFT_CUT type with certainty.
                # This prevents LLM from misclassifying e.g. SPIRAL_WOUND as SOFT_CUT when
                # batched alongside many soft-cut items.
                forced_type = _regex_detect_type(desc)
                if forced_type and forced_type != 'SOFT_CUT':
                    if extracted.get('gasket_type') != forced_type:
                        logger.info(
                            f'Regex overriding LLM type '
                            f'{extracted.get("gasket_type")} → {forced_type}: {desc[:60]}'
                        )
                    extracted['gasket_type'] = forced_type
                cache[desc] = extracted
                # Store in Redis — skip null stubs (LLM was unavailable)
                if r and result:
                    try:
                        r.setex(_cache_key(desc), _CACHE_TTL, json.dumps(extracted))
                    except Exception:
                        pass

    output = []
    for item in items:
        extracted = cache[item['description']].copy()
        extracted['quantity'] = item.get('quantity')
        extracted['uom'] = item.get('uom', 'NOS')
        extracted['line_no'] = item.get('line_no')
        extracted['raw_description'] = item['description']
        output.append(extracted)
    return output


async def _llm_extract_batch_async(async_client, descriptions: list[str]) -> list[dict | None]:
    """Async version of _llm_extract_batch — used by extract_batch via asyncio.gather."""
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
            resp = await async_client.chat.completions.create(
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
            while len(results) < len(descriptions):
                results.append(None)
            return results[:len(descriptions)]
        except Exception as e:
            msg = str(e)
            if '429' in msg or 'rate_limit' in msg.lower():
                wait = 5.0 * (attempt + 1)
                logger.info(f'Rate limited — waiting {wait:.1f}s (attempt {attempt + 1}/3)')
                await asyncio.sleep(wait)
            else:
                logger.warning(f'LLM async batch failed: {e}')
                return [None] * len(descriptions)
    logger.warning('LLM async batch failed after 3 attempts')
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
        'isk_style': None, 'isk_fire_safety': None, 'dji_filler': None,
        'sw_winding_material': None, 'sw_filler': None,
        'sw_inner_ring': None, 'sw_outer_ring': None,
        'rtj_groove_type': None, 'rtj_hardness_bhn': None,
        'ring_no': None, 'confidence': 'LOW',
    }
