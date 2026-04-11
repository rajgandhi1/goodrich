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
  "isk_style": "e.g. STYLE-CS | STYLE-N | null (ISK/ISK_RTJ only — style identifier)",
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
6. ISK: Insulating Gasket Kit (RF/FF flanges). 7. ISK_RTJ: ISK for RTJ flanges.

Schema per item:
{_FIELD_SCHEMA}

Rules:
- size: NPS/inch → as-is (e.g. "6\\""). NB/DN → "X NB" (e.g. "100 NB") — do NOT convert to inches; DN=NB. OD×ID → "OD NNNmm x ID NNNmm". size_type: NPS/NB/OD_ID. Bare trailing number after "INCH" keyword = NPS size in inches.
- rating: "150#"/"300#"/"PN 10"/"PN 16". Valid ASME classes: 150/300/600/900/1500/2500/3000.
- Normalize winding materials (sw_winding_material): 304SS/SS 304/AISI 304→SS304; 316SS/316-SS→SS316; 316L→SS316L; SUPER DUPLEX/SDSS→SDSS (UNS S32750); INCOLOY/INCOLOY 825→INCOLOY 825; INCONEL/INCONEL 625→INCONEL 625; "STAINLESS STEEL" alone (no grade)→null.
- Normalize ring materials: CARBON STEEL/MS/C.S./CS→CS; I/R=inner ring, O/R=outer ring (e.g. "ALLOY 20 I/R"=sw_inner_ring=ALLOY 20, "CS O/R"=sw_outer_ring=CS); LTCS→pass through as LTCS. INCOLOY 825/INCONEL 625 rings→keep as-is.
- Normalize RTJ MOC: SOFT IRON/SOFTIRON→SOFTIRON; SOFT IRON GALVANISED→SOFTIRON GALVANISED; LOW CARBON STEEL/LCS/CARBON STEEL/CN+ZN PLATED CS→LOW CARBON STEEL; 316 S/STAINLESS STEEL 316→SS316; UNS S32205/UNS S32750→keep as-is. Ring nos: RX53→RX-53, BX 156→BX-156 (space=hyphen). BHN: soft iron=90, LCS=120, SS316=160, INCOLOY 825/INCONEL 625=160.
- SPIRAL_WOUND: sw_winding_material/sw_filler/sw_inner_ring/sw_outer_ring; moc=null. RTJ: moc/rtj_groove_type/rtj_hardness_bhn/ring_no; sw_*=null; standard=ASME B16.20. SOFT_CUT: moc; sw_*/rtj_*=null.
- face_type: RF/FF for SOFT_CUT/ISK/ISK_RTJ; null for SPIRAL_WOUND/RTJ/KAMM/DJI.
- thickness_mm: null for RTJ; extract number or null for others.
- standard: API 6A/API Specs→"API 6A"; B16/A→"ASME B16.20"; ASME B16.21 (soft cut ≤24"); ASME B16.47 (soft cut ≥26"); ASME B16.20 (SW/RTJ ≤24"); ASME B16.47 (SW ≥26"). ISK/ISK_RTJ: extract customer-stated standard verbatim incl. SERIES A/B (e.g. "ASME B16.47 ( SERIES A )").
- special: FOOD GRADE/NACE/LETHAL/EIL APPROVED/NACE MR 0175/API 6A/SERIES B. ISK/ISK_RTJ: prefix "SET:" + component details verbatim. DJI: set "AS PER DRAWING" when drawing referenced.
- isk_style: STYLE-CS (G10 laminate+metallic core); STYLE-N (ISK_RTJ). Null if not explicitly stated.
- dji_filler: GRAPHITE/ASBESTOS FREE/ARMCO IRON/other. Null = rules engine defaults GRAPHITE.
- Brand name SOFT_CUT (KROLLER & ZILLER/KLINGER/DONIT/GARLOCK + grade code) → moc=full brand+grade. "WITH SPACER"=SOFT_CUT, capture in special.
- confidence: HIGH if all key fields clear; LOW if ambiguous."""


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
        'isk_style': None, 'dji_filler': None,
        'sw_winding_material': None, 'sw_filler': None,
        'sw_inner_ring': None, 'sw_outer_ring': None,
        'rtj_groove_type': None, 'rtj_hardness_bhn': None,
        'ring_no': None, 'confidence': 'LOW',
    }
