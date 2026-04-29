"""
Regex guard-rail layer for Smart Parse mode.

Runs regex_extract() on each item's raw_description and overrides LLM field
values where the regex is deterministically reliable. LLM is trusted for ISK,
KAMM, and DJI component lists where surrounding context matters more than
individual keyword patterns.
"""
from __future__ import annotations

import logging
from core.regex_extractor import regex_extract

logger = logging.getLogger(__name__)

# Fields where regex wins unconditionally (deterministic numeric/keyword extraction)
_REGEX_WINS_OVER_LLM = frozenset({'od_mm', 'id_mm', 'rtj_groove_type'})

# Fields where regex only fills gaps (override only when LLM returned null)
_REGEX_FILLS_GAPS = frozenset({
    'size', 'rating', 'ring_no', 'face_type', 'standard',
    'thickness_mm', 'size_type',
    'sw_winding_material', 'sw_filler', 'sw_inner_ring', 'sw_outer_ring',
})

# Fields never overridden — LLM has better context for these
_NEVER_OVERRIDE = frozenset({
    'isk_style', 'isk_type', 'isk_fire_safety', 'isk_gasket_material',
    'isk_core_material', 'isk_sleeve_material', 'isk_washer_material',
    'isk_primary_seal', 'isk_secondary_seal', 'isk_insulating_washer',
    'kamm_core_material', 'kamm_surface_material', 'kamm_covering_layer',
    'kamm_rib', 'kamm_core_thk', 'kamm_integral_outer_ring',
    'dji_filler', 'dji_rib', 'dji_face_type', 'dji_id_first',
    'special', 'quantity', 'uom', 'line_no', 'raw_description', 'moc',
})

_ALL_OVERRIDEABLE = [
    'gasket_type',
    'od_mm', 'id_mm',
    'size', 'size_type',
    'rating',
    'face_type',
    'standard',
    'thickness_mm',
    'ring_no',
    'rtj_groove_type',
    'sw_winding_material', 'sw_filler', 'sw_inner_ring', 'sw_outer_ring',
]


def validate_with_regex(items: list[dict]) -> list[dict]:
    """
    Guard-rail pass: run regex_extract() on each item's raw_description
    and override LLM fields where regex is more reliable.

    Each item gets an '_override_log' list key for debugging.
    Returns a new list (originals are not mutated).
    """
    result = []
    for item in items:
        item = dict(item)  # shallow copy — do not mutate caller's data
        desc = item.get('raw_description') or ''

        if not desc.strip():
            item['_override_log'] = []
            result.append(item)
            continue

        try:
            rx = regex_extract(desc)
        except Exception as e:
            logger.warning(f'Regex extract failed for [{desc[:60]}]: {e}')
            item['_override_log'] = []
            result.append(item)
            continue

        override_log = []
        overrides_applied = 0

        for field in _ALL_OVERRIDEABLE:
            if field in _NEVER_OVERRIDE:
                continue

            regex_val = rx.get(field)
            llm_val = item.get(field)

            if _should_override(field, regex_val, llm_val):
                item[field] = regex_val
                override_log.append(f'{field}: {llm_val!r} → {regex_val!r}')
                overrides_applied += 1

        # Downgrade confidence if regex disagreed substantially with LLM
        if overrides_applied >= 2 and item.get('confidence') == 'HIGH':
            item['confidence'] = 'MEDIUM'
            override_log.append('confidence: HIGH → MEDIUM (≥2 field overrides by regex)')

        item['_override_log'] = override_log
        if override_log:
            logger.debug(f'Regex overrides [{desc[:50]}]: {override_log}')

        result.append(item)

    return result


def _should_override(field: str, regex_val, llm_val) -> bool:
    """Return True if the regex value should replace the LLM value."""
    if regex_val is None:
        return False  # regex found nothing — never override with None

    if field in _NEVER_OVERRIDE:
        return False

    if field == 'gasket_type':
        # Override when regex found a specific type and LLM disagrees
        # (regex keyword patterns for SPIRAL_WOUND, RTJ, KAMM, DJI, ISK are very reliable)
        if regex_val != 'SOFT_CUT' and regex_val != llm_val:
            return True
        return False

    if field in _REGEX_WINS_OVER_LLM:
        # Deterministic extraction — override if different
        return regex_val != llm_val

    if field in _REGEX_FILLS_GAPS:
        # Only fill gaps — LLM wins when it has a value
        is_null = llm_val is None or llm_val == 'UNKNOWN'
        return is_null

    return False
