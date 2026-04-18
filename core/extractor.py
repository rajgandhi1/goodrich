from __future__ import annotations
"""
Extracts structured gasket fields from raw description strings.

Architecture (regex-first, per-item LLM):
  1. regex_extract() every description → HIGH confidence items are done
  2. MEDIUM/LOW items → per-item async LLM with simplified prompt
  3. Merge: regex values always win for non-null fields; LLM fills gaps
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

from core.regex_extractor import regex_extract

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis cache (unchanged)
# ---------------------------------------------------------------------------

_CACHE_TTL = 30 * 24 * 3600  # 30 days

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

# ---------------------------------------------------------------------------
# ISK packed format preprocessor (unchanged)
# ---------------------------------------------------------------------------

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
    """Expand compact ISK size+rating formats."""
    m = _PACKED_ISK_RE1.match(desc)
    if m:
        return _PACKED_ISK_RE1.sub(r'\1" \2#\3', desc, count=1)
    m = _PACKED_ISK_RE2.match(desc)
    if m:
        return _PACKED_ISK_RE2.sub(r'\1" \2', desc, count=1)
    return desc

# ---------------------------------------------------------------------------
# Simplified single-item LLM prompt
# ---------------------------------------------------------------------------

_FIELD_SCHEMA = """{
  "size": "e.g. 2\\" or OD 584MM or null",
  "size_type": "NPS | NB | DN | OD_ID | UNKNOWN",
  "od_mm": null, "id_mm": null,
  "rating": "e.g. 150# or PN 10 or null",
  "gasket_type": "SOFT_CUT | SPIRAL_WOUND | RTJ | KAMM | DJI | ISK | ISK_RTJ",
  "moc": "material or null",
  "face_type": "RF | FF | null",
  "thickness_mm": "number or null",
  "standard": "ASME B16.21 | ASME B16.20 | EN 1514-1 | other | null",
  "special": "special requirements or null",
  "isk_style": "STYLE-CS | STYLE-N | TYPE-A | TYPE-E | TYPE-F | null",
  "isk_fire_safety": "FIRE SAFE | NON FIRE SAFE | null",
  "isk_gasket_material": "GRE G10 | GRE G11 | PTFE | PEEK | null",
  "isk_core_material": "metal core e.g. SS316 | CS | DUPLEX | null",
  "isk_sleeve_material": "sleeve material e.g. GRE G10 | PTFE | null",
  "isk_washer_material": "washer material e.g. CS | SS316 | null",
  "dji_filler": "filler material or null",
  "kamm_core_material": "KAMM metal core e.g. SS316 | CS | ALLOY 625 | null",
  "kamm_surface_material": "KAMM surface e.g. GRAPHITE | PTFE | null",
  "sw_winding_material": "e.g. SS304 | SS316 | null",
  "sw_filler": "e.g. GRAPHITE | PTFE | null",
  "sw_inner_ring": "e.g. SS304 | CS | null",
  "sw_outer_ring": "e.g. CS | SS304 | null",
  "rtj_groove_type": "OCT | OVAL | null",
  "rtj_hardness_bhn": "BHN number or null",
  "ring_no": "e.g. R-24 | null",
  "confidence": "HIGH | MEDIUM | LOW"
}"""

_SINGLE_ITEM_SYSTEM_PROMPT = f"""You are a gasket specification extraction assistant. Extract fields from the customer description and return ONLY valid JSON matching this schema:
{_FIELD_SCHEMA}

Rules:
- size: NPS/inch as-is (e.g. "6\\""). NB → "X NB". DN → "DN X". OD×ID → "OD NNNmm x ID NNNmm".
- rating: "150#"/"300#"/"PN 10"/"PN 16". Valid ASME: 150/300/600/900/1500/2500/3000.
- Normalize materials: 304SS→SS304, 316SS→SS316, CARBON STEEL/CS/MS→CS, SOFT IRON→SOFTIRON.
- SPIRAL_WOUND: use sw_* fields, moc=null. RTJ: use moc+rtj_* fields, standard=ASME B16.20.
- face_type: RF/FF for SOFT_CUT/ISK only; null for SW/RTJ/KAMM/DJI.
- ISK: capture component details (GRE G10, seals, sleeves) in special field.
- thickness_mm: null for RTJ. Patterns: "3MM THK", "THK-1.5", "3T" suffix.
- confidence: HIGH if all key fields clear, MEDIUM if 1 missing, LOW if 2+ missing.

Pre-extracted regex values are provided as hints. Trust them unless clearly wrong — they handle size/rating/type detection reliably. Focus on filling gaps the regex missed."""

# ---------------------------------------------------------------------------
# Concurrency limit for async LLM calls
# ---------------------------------------------------------------------------

_LLM_CONCURRENCY = 10

# ---------------------------------------------------------------------------
# Per-item async LLM extraction
# ---------------------------------------------------------------------------

async def _llm_extract_single_async(
    async_client,
    desc: str,
    regex_hint: dict,
    sem: asyncio.Semaphore,
) -> dict | None:
    """Extract fields for a single description via LLM. Returns dict or None on failure."""
    from data.reference_data import select_few_shot_examples

    # Build hint string from non-null regex fields
    hint_parts = []
    for k, v in regex_hint.items():
        if v is not None and k != 'confidence' and v != 'UNKNOWN':
            hint_parts.append(f'{k}={v}')
    hint_str = ', '.join(hint_parts) if hint_parts else 'none'

    # Select 4 few-shot examples relevant to THIS item
    examples = select_few_shot_examples(desc, n=4)
    examples_text = '\n'.join(
        f'Input: "{e["input"]}"\nOutput: "{e["output"]}"'
        for e in examples
    )

    user_msg = (
        f"Examples:\n{examples_text}\n\n"
        f"Pre-extracted (trust unless wrong): {hint_str}\n\n"
        f"Extract fields from:\n\"{desc}\""
    )

    async with sem:
        for attempt in range(2):
            try:
                resp = await async_client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[
                        {'role': 'system', 'content': _SINGLE_ITEM_SYSTEM_PROMPT},
                        {'role': 'user', 'content': user_msg},
                    ],
                    temperature=0.1,
                    response_format={'type': 'json_object'},
                    max_tokens=500,
                )
                data = json.loads(resp.choices[0].message.content)
                # Validate minimal structure
                if 'gasket_type' in data or 'size' in data:
                    return data
                # If LLM returned a wrapper like {"results": [...]}, unwrap
                if 'results' in data and isinstance(data['results'], list) and data['results']:
                    return data['results'][0]
                return data
            except Exception as e:
                msg = str(e).lower()
                if '429' in str(e) or 'rate_limit' in msg:
                    wait = 5.0 * (attempt + 1)
                    logger.info(f'Rate limited — waiting {wait:.1f}s (attempt {attempt + 1}/2)')
                    await asyncio.sleep(wait)
                elif 'timeout' in msg or 'timed out' in msg:
                    wait = 8.0 * (attempt + 1)
                    logger.warning(f'LLM timeout — retrying in {wait:.1f}s (attempt {attempt + 1}/2)')
                    await asyncio.sleep(wait)
                else:
                    logger.warning(f'LLM single-item failed: {e}')
                    return None
    logger.warning(f'LLM failed after 2 attempts: {desc[:60]}')
    return None

# ---------------------------------------------------------------------------
# Merge: regex always wins for non-null fields, LLM fills gaps
# ---------------------------------------------------------------------------

_ALL_FIELDS = [
    'size', 'size_type', 'od_mm', 'id_mm', 'rating', 'gasket_type', 'moc',
    'face_type', 'thickness_mm', 'standard', 'special',
    'isk_style', 'isk_fire_safety',
    'isk_gasket_material', 'isk_core_material', 'isk_sleeve_material', 'isk_washer_material',
    'dji_filler',
    'kamm_core_material', 'kamm_surface_material',
    'sw_winding_material', 'sw_filler', 'sw_inner_ring', 'sw_outer_ring',
    'rtj_groove_type', 'rtj_hardness_bhn', 'ring_no', 'confidence',
]

def _merge_results(regex_result: dict, llm_result: dict | None) -> dict:
    """Merge regex and LLM results. Regex values always win for non-null fields."""
    if llm_result is None:
        return regex_result

    merged = {}
    for field in _ALL_FIELDS:
        regex_val = regex_result.get(field)
        llm_val = llm_result.get(field)

        if field == 'gasket_type':
            # Regex type detection is more reliable — always prefer it
            # unless it defaulted to SOFT_CUT and LLM found something specific
            if regex_val and regex_val != 'SOFT_CUT':
                merged[field] = regex_val
            elif llm_val and llm_val != 'SOFT_CUT':
                merged[field] = llm_val
            else:
                merged[field] = regex_val or 'SOFT_CUT'
            # Inner/outer ring always means spiral wound — override any misclassification
            llm_ir = llm_result.get('sw_inner_ring') if llm_result else None
            llm_or = llm_result.get('sw_outer_ring') if llm_result else None
            if (regex_result.get('sw_inner_ring') or llm_ir or
                    regex_result.get('sw_outer_ring') or llm_or):
                merged[field] = 'SPIRAL_WOUND'
        elif field == 'size_type':
            # Prefer regex unless it's UNKNOWN and LLM has something
            if regex_val and regex_val != 'UNKNOWN':
                merged[field] = regex_val
            elif llm_val and llm_val != 'UNKNOWN':
                merged[field] = llm_val
            else:
                merged[field] = 'UNKNOWN'
        elif field == 'confidence':
            # Keep regex confidence (it was scored based on what regex found)
            merged[field] = regex_val or 'LOW'
        else:
            # Regex wins if non-null, otherwise LLM fills the gap
            if regex_val is not None:
                merged[field] = regex_val
            else:
                merged[field] = llm_val

    return merged

# ---------------------------------------------------------------------------
# Null extraction stub (unchanged)
# ---------------------------------------------------------------------------

def _null_extract() -> dict:
    """Return an all-null extraction so rules.py flags everything as missing."""
    return {
        'size': None, 'size_type': 'UNKNOWN', 'od_mm': None, 'id_mm': None,
        'rating': None, 'gasket_type': 'SOFT_CUT', 'moc': None,
        'face_type': None, 'thickness_mm': None, 'standard': None,
        'special': 'LLM unavailable — review manually',
        'isk_style': None, 'isk_fire_safety': None,
        'isk_gasket_material': None, 'isk_core_material': None,
        'isk_sleeve_material': None, 'isk_washer_material': None,
        'dji_filler': None,
        'kamm_core_material': None, 'kamm_surface_material': None,
        'sw_winding_material': None, 'sw_filler': None,
        'sw_inner_ring': None, 'sw_outer_ring': None,
        'rtj_groove_type': None, 'rtj_hardness_bhn': None,
        'ring_no': None, 'confidence': 'LOW',
    }

# ---------------------------------------------------------------------------
# Streamlit secret helper (unchanged)
# ---------------------------------------------------------------------------

def _get_streamlit_secret(key: str) -> str | None:
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Main entry point — interface preserved exactly
# ---------------------------------------------------------------------------

def extract_batch(items: list[dict], progress_cb=None) -> list[dict]:
    """
    Extract structured fields for all items.

    Flow:
      1. Preprocess (clean newlines, ISK packed)
      2. Dedup descriptions
      3. Redis cache lookup
      4. regex_extract() each uncached description
      5. Split HIGH (done) vs MEDIUM/LOW (need LLM)
      6. Per-item async LLM with Semaphore(10) for MEDIUM/LOW
      7. Merge regex + LLM results
      8. Cache new results in Redis
      9. Assemble output with passthrough fields

    progress_cb(done, total) is called from the main thread.
    """
    # 1. Preprocess
    for item in items:
        if item.get('description'):
            item['description'] = re.sub(r'[\r\n]+', ' ', item['description']).strip()
            item['description'] = _preprocess_isk_packed(item['description'])

    # 2. Dedup
    unique_descs_list = list({item['description'] for item in items})
    total = len(unique_descs_list)
    cache: dict = {}

    # 3. Redis cache lookup
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
        if cache:
            logger.info(f'Redis cache: {len(cache)}/{total} hits, {len(uncached)} need extraction')
    else:
        uncached = unique_descs_list

    if progress_cb and cache:
        progress_cb(len(cache), total)

    # 4. regex_extract() each uncached description
    regex_results: dict[str, dict] = {}
    need_llm: list[str] = []

    for desc in uncached:
        rx = regex_extract(desc)
        regex_results[desc] = rx
        if rx['confidence'] == 'HIGH':
            # Done — no LLM needed
            cache[desc] = rx
        else:
            need_llm.append(desc)

    # Report progress for regex HIGH items
    high_count = len(uncached) - len(need_llm)
    if progress_cb and high_count > 0:
        progress_cb(len(cache), total)

    logger.info(
        f'Regex: {high_count} HIGH (skip LLM), '
        f'{len(need_llm)} MEDIUM/LOW (need LLM)'
    )

    # 5. Per-item async LLM for MEDIUM/LOW items
    api_key = os.environ.get('OPENAI_API_KEY') or _get_streamlit_secret('OPENAI_API_KEY')

    if not need_llm:
        pass  # all done via cache + regex
    elif not api_key:
        # No API key — use regex-only results (better than null stubs)
        for desc in need_llm:
            cache[desc] = regex_results[desc]
    else:
        progress_q: _stdlib_queue.SimpleQueue = _stdlib_queue.SimpleQueue()
        llm_results: dict[str, dict | None] = {}

        async def _do_single(async_client, desc: str, sem: asyncio.Semaphore):
            llm_out = await _llm_extract_single_async(
                async_client, desc, regex_results[desc], sem,
            )
            progress_q.put(1)
            return desc, llm_out

        async def _run_all(key: str):
            from openai import AsyncOpenAI
            async_client = AsyncOpenAI(api_key=key, timeout=120.0)
            sem = asyncio.Semaphore(_LLM_CONCURRENCY)
            results = await asyncio.gather(
                *[_do_single(async_client, d, sem) for d in need_llm]
            )
            return results

        def _bg():
            results = asyncio.run(_run_all(api_key))
            for desc, llm_out in results:
                llm_results[desc] = llm_out

        t = threading.Thread(target=_bg, daemon=True)
        t.start()

        # Drain progress queue while LLM thread runs
        done_count = len(cache)
        while t.is_alive():
            try:
                n = progress_q.get(block=False)
                done_count += n
                if progress_cb:
                    progress_cb(done_count, total)
            except _stdlib_queue.Empty:
                time.sleep(0.05)
        t.join()

        # Drain remaining progress
        while True:
            try:
                n = progress_q.get(block=False)
                done_count += n
                if progress_cb:
                    progress_cb(done_count, total)
            except _stdlib_queue.Empty:
                break

        # 6. Merge regex + LLM results
        for desc in need_llm:
            merged = _merge_results(regex_results[desc], llm_results.get(desc))
            cache[desc] = merged
            # Store in Redis (skip if LLM returned None — regex-only result)
            if r and llm_results.get(desc):
                try:
                    r.setex(_cache_key(desc), _CACHE_TTL, json.dumps(merged))
                except Exception:
                    pass

    # Also cache regex HIGH results in Redis
    if r:
        for desc in uncached:
            if desc not in need_llm and desc in regex_results:
                try:
                    r.setex(_cache_key(desc), _CACHE_TTL, json.dumps(regex_results[desc]))
                except Exception:
                    pass

    # 7. Assemble output with passthrough fields
    output = []
    for item in items:
        extracted = cache[item['description']].copy()
        extracted['quantity'] = item.get('quantity')
        extracted['uom'] = item.get('uom', 'NOS')
        extracted['line_no'] = item.get('line_no')
        extracted['raw_description'] = item['description']
        output.append(extracted)
    return output
