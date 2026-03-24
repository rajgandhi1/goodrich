from __future__ import annotations
"""
Applies business rules: defaults, normalization, validation, and status flagging.
Each item gets a 'status' (ready/check/missing) and 'flags' list.
"""
import re
from data.reference_data import (
    normalize_size, normalize_rating, lookup_dimensions, ACCEPTED_MOC,
    lookup_rtj_ring,
)

STATUS_READY = 'ready'
STATUS_CHECK = 'check'
STATUS_MISSING = 'missing'

# Fields that cannot be defaulted — must be provided by customer
CRITICAL_FIELDS = ['size', 'rating', 'moc']

_MOC_ALIASES = {
    'COMPRESSED NON ASBESTOS FIBER': 'CNAF',
    'NON ASBESTOS': 'NON ASBESTOS',
    'CNAF': 'CNAF',
    'NEOPRENE': 'NEOPRENE',
    'CHLOROPRENE': 'NEOPRENE',
    'NATURAL RUBBER': 'NATURAL RUBBER',
    'EPDM': 'EPDM',
    'EXPANDED PTFE': 'EXPANDED PTFE',
    'EPTFE': 'EXPANDED PTFE',
    'PTFE ENVELOPED': 'NON ASBESTOS PTFE ENVELOPED',
    'PTFE': 'PTFE',
    'TEFLON': 'PTFE',
    'VITON': 'VITON',
    'FKM': 'VITON',
    'GRAPHITE': 'GRAPHITE',
    'GRAFOIL': 'GRAPHITE',
    'FLEXIBLE GRAPHITE': 'GRAPHITE',
    'BUTYL RUBBER': 'BUTYL RUBBER',
    'BUTYL': 'BUTYL RUBBER',
    'NITRILE BUTADIENE RUBBER': 'NITRILE BUTADIENE RUBBER',
    'NBR': 'NITRILE BUTADIENE RUBBER',
    'BUNA-N': 'BUNA-N',
    'NITRILE': 'NITRILE BUTADIENE RUBBER',
    'ELASTOMER': 'ELASTOMER',
    'WIRE REINFORCED NEOPRENE RUBBER': 'WIRE REINFORCED NEOPRENE RUBBER',
    'SYNTHETIC FIBRE': 'SYNTHETIC FIBRE',
    'CHLOROPRENE RUBBER': 'NEOPRENE',
    'REINFORCED PTFE': 'REINFORCED PTFE',
    'POLYVINYLIDENE FLUORIDE': 'POLYVINYLIDENE FLUORIDE',
}

# Generic "RUBBER" is ambiguous — must ask customer
_AMBIGUOUS_MOC = {'RUBBER'}

# ---------------------------------------------------------------------------
# Spiral wound helpers
# ---------------------------------------------------------------------------

_SW_RING_ALIASES = {
    'CARBON STEEL': 'CS', 'C.S.': 'CS', 'MS': 'CS', 'M.S.': 'CS',
    'CS': 'CS', 'SS304': 'SS304', 'SS316': 'SS316', 'SS316L': 'SS316L',
    '304 SS': 'SS304', '316 SS': 'SS316',
    'INCOLOY 825': 'INCOLOY 825', 'INCOLOY825': 'INCOLOY 825',
    'INCOLOY 800': 'INCOLOY 800', 'INCOLOY800': 'INCOLOY 800',
    'INCONEL 625': 'INCONEL 625', 'INCONEL625': 'INCONEL 625',
}


def _norm_ring(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().upper()
    return _SW_RING_ALIASES.get(key, key)


def _size_nps_value(size_norm: str | None) -> float | None:
    """Return numeric NPS value from normalized size string like '28"'."""
    if not size_norm:
        return None
    m = re.search(r'([\d.]+)', size_norm)
    return float(m.group(1)) if m else None


def _build_sw_moc(winding_mat: str, filler: str, inner_ring: str | None, outer_ring: str | None) -> str:
    moc = f'{winding_mat} SPIRAL WOUND GASKET WITH {filler} FILLER'
    if inner_ring and outer_ring:
        moc += f' + {inner_ring} INNER RING & {outer_ring} OUTER RING'
    elif outer_ring:
        moc += f' + {outer_ring} OUTER RING'
    return moc


def _apply_sw_rules(item: dict, flags: list, applied_defaults: list) -> None:
    """Apply spiral wound-specific defaults and validation (mutates item in place)."""
    winding_mat = item.get('sw_winding_material')
    filler = item.get('sw_filler')
    outer_ring = _norm_ring(item.get('sw_outer_ring'))
    inner_ring = _norm_ring(item.get('sw_inner_ring'))

    # Default outer ring to CS if not specified
    if not outer_ring:
        outer_ring = 'CS'
        applied_defaults.append('outer ring defaulted to CS')
    if not filler:
        filler = 'GRAPHITE'
        applied_defaults.append('filler defaulted to GRAPHITE')

    # Auto-add inner ring for large-diameter flanges (NPS ≥ 26")
    size_val = _size_nps_value(item.get('size_norm'))
    if size_val is not None and size_val >= 26 and not inner_ring:
        inner_ring = winding_mat or 'SS304'
        applied_defaults.append(f'inner ring added ({inner_ring}) for NPS≥26"')

    item['sw_outer_ring'] = outer_ring
    item['sw_inner_ring'] = inner_ring
    item['sw_filler'] = filler

    # Handle "SS" without grade — ambiguous, cannot build valid MOC
    grade_flag_fired = False
    if winding_mat == 'SS':
        flags.append('Spiral wound: winding grade not specified — confirm SS304/SS316/SS316L/etc.')
        grade_flag_fired = True
        winding_mat = None
        item['sw_winding_material'] = None

    # Build MOC string if not already set
    if not item.get('moc') and winding_mat:
        item['moc'] = _build_sw_moc(winding_mat, filler, inner_ring, outer_ring)
    elif not item.get('moc') and not grade_flag_fired:
        flags.append('Spiral wound: winding material not identified — verify SS304/SS316/etc.')

    # Default thickness to 4.5mm
    if not item.get('thickness_mm'):
        item['thickness_mm'] = 4.5
        applied_defaults.append('thickness defaulted to 4.5mm (spiral wound)')

    # No face type for spiral wound
    item['face_type'] = None

    # Standard based on size
    if not item.get('standard'):
        if size_val is not None and size_val >= 26:
            item['standard'] = 'ASME B16.47 ( SERIES B )'
        else:
            item['standard'] = 'ASME B16.20'
        applied_defaults.append('standard defaulted to ' + item['standard'])


# ---------------------------------------------------------------------------
# RTJ helpers
# ---------------------------------------------------------------------------

_RTJ_HARDNESS_DEFAULTS = {
    'SOFTIRON': 90,
    'SOFTIRON GALVANISED': 90,
    'LOW CARBON STEEL': 120,
    'SS304': 160, 'SS304L': 160, 'F304': 160,
    'SS316': 160, 'SS316L': 160, 'F316': 160, 'F316L': 160,
    'MONEL 400': 130,
    'INCONEL 625': 160,
    'INCOLOY 825': 160,   # Incoloy 825 (UNS N08825) — max ~160 BHN
    'INCOLOY 800': 160,   # Incoloy 800 (UNS N08800) — similar hardness
    'UNS N08825': 160,
    'UNS N08800': 160,
    'UNS S31600': 160,  # SS316
    'UNS S31603': 160,  # SS316L
    'UNS S30400': 160,  # SS304
    # UNS S32205 (Duplex 2205) max 22 HRC — don't default BHN, let hardness_spec cover it
    # UNS S32750 (Super Duplex) — same
}

_RTJ_MOC_ALIASES = {
    'SOFT IRON': 'SOFTIRON',
    'SOFTIRON': 'SOFTIRON',
    'SOFT IRON GALVANISED': 'SOFTIRON GALVANISED',
    'SOFT IRON GALVANIZED': 'SOFTIRON GALVANISED',
    'GALVANISED SOFT IRON': 'SOFTIRON GALVANISED',
    'GALVANIZED SOFT IRON': 'SOFTIRON GALVANISED',
    'LOW CARBON STEEL': 'LOW CARBON STEEL',
    'LCS': 'LOW CARBON STEEL',
    'CARBON STEEL': 'LOW CARBON STEEL',
    'SS316': 'SS316', 'SS 316': 'SS316', '316SS': 'SS316', '316 SS': 'SS316',
    'SS304': 'SS304', 'SS 304': 'SS304', '304SS': 'SS304', '304 SS': 'SS304',
    'SS316L': 'SS316L', 'SS 316L': 'SS316L',
    'F304': 'F304', 'F316': 'F316', 'F316L': 'F316L',
    'MONEL': 'MONEL 400', 'MONEL 400': 'MONEL 400',
    'INCONEL': 'INCONEL 625', 'INCONEL 625': 'INCONEL 625',
    'INCOLOY 825': 'INCOLOY 825', 'INCOLOY825': 'INCOLOY 825',
    'INCOLOY': 'INCOLOY 825',  # "Incoloy" alone most commonly means 825 in RTJ context
    'INCOLOY 800': 'INCOLOY 800', 'INCOLOY800': 'INCOLOY 800',
}


def _apply_rtj_rules(item: dict, flags: list, applied_defaults: list) -> None:
    # Normalize MOC
    raw_moc = (item.get('moc') or '').strip().upper()
    # UNS materials pass through as-is
    if raw_moc.startswith('UNS '):
        norm_moc = raw_moc
    else:
        norm_moc = _RTJ_MOC_ALIASES.get(raw_moc, raw_moc) if raw_moc else None
    item['moc'] = norm_moc

    # Groove type — default OCT
    if not item.get('rtj_groove_type'):
        item['rtj_groove_type'] = 'OCT'
        applied_defaults.append('groove type defaulted to OCT')

    # BHN hardness — default from MOC
    if not item.get('rtj_hardness_bhn') and not item.get('rtj_hardness_spec') and norm_moc:
        bhn = _RTJ_HARDNESS_DEFAULTS.get(norm_moc)
        if bhn:
            item['rtj_hardness_bhn'] = bhn
            item['rtj_hardness_spec'] = f"{bhn} BHN HARDNESS"
            applied_defaults.append(f'BHN hardness defaulted to {bhn} for {norm_moc}')
    elif item.get('rtj_hardness_bhn') and not item.get('rtj_hardness_spec'):
        item['rtj_hardness_spec'] = f"{int(item['rtj_hardness_bhn'])} BHN HARDNESS"

    # Ring number lookup
    if not item.get('ring_no'):
        ring = lookup_rtj_ring(item.get('size_norm'), item.get('rating'))
        if ring:
            item['ring_no'] = ring
            applied_defaults.append(f'ring number looked up: {ring}')
        else:
            flags.append('Ring number not in lookup table — enter manually (check ASME B16.20)')
            item['ring_no'] = None

    # API pressure class rating (API 5000, API 10000, etc.) → API 6A standard
    rating = item.get('rating') or ''
    if rating.startswith('API ') and item.get('standard') != 'API 6A':
        item['standard'] = 'API 6A'
    elif not item.get('standard'):
        item['standard'] = 'ASME B16.20'
    item['face_type'] = None
    item['thickness_mm'] = None


# ---------------------------------------------------------------------------
# KAMM helpers
# ---------------------------------------------------------------------------

def _apply_kamm_rules(item: dict, flags: list, applied_defaults: list) -> None:
    winding_mat = item.get('sw_winding_material')
    filler = item.get('sw_filler') or 'GRAPHITE'
    outer_ring = _norm_ring(item.get('sw_outer_ring'))
    inner_ring = _norm_ring(item.get('sw_inner_ring'))

    if not filler:
        applied_defaults.append('filler defaulted to GRAPHITE')
    # Default outer ring to CS only for NPS-rated KAMM (not custom OD/ID)
    is_od_id = item.get('size_type') == 'OD_ID'
    if not outer_ring and not is_od_id:
        outer_ring = 'CS'
        applied_defaults.append('outer ring defaulted to CS')

    item['sw_filler'] = filler
    item['sw_outer_ring'] = outer_ring
    item['sw_inner_ring'] = inner_ring

    if not item.get('moc') and winding_mat:
        if inner_ring and outer_ring:
            item['moc'] = f'{winding_mat} KAMMPROFILE GASKET WITH {filler} FILLER + {inner_ring} INNER RING & {outer_ring} OUTER RING'
        elif outer_ring:
            item['moc'] = f'{winding_mat} KAMMPROFILE GASKET WITH {filler} FILLER + {outer_ring} OUTER RING'
        else:
            item['moc'] = f'{winding_mat} KAMMPROFILE WITH {filler} COATED ON BOTH SIDES'
    elif not item.get('moc'):
        flags.append('KAMM: winding material not identified — verify SS316/SS304/etc.')

    if not item.get('thickness_mm'):
        item['thickness_mm'] = 4.5
        applied_defaults.append('thickness defaulted to 4.5mm (KAMM)')

    # No standard for custom OD/ID KAMM; only for NPS-rated KAMM
    if item.get('size_type') != 'OD_ID' and not item.get('standard'):
        size_val = _size_nps_value(item.get('size_norm'))
        if size_val is not None and size_val >= 26:
            item['standard'] = 'ASME B16.47 (SERIES - B)'
        else:
            item['standard'] = 'ASME B16.20'
        applied_defaults.append('standard defaulted to ' + item['standard'])

    item['face_type'] = None


# ---------------------------------------------------------------------------
# DJI helpers
# ---------------------------------------------------------------------------

def _apply_dji_rules(item: dict, flags: list, applied_defaults: list) -> None:
    if not item.get('moc'):
        flags.append('DJI: jacket material not identified')
    if not item.get('od_mm') or not item.get('id_mm'):
        flags.append('DJI: OD and ID dimensions required')
    item['face_type'] = None
    item['standard'] = None
    item['rating'] = None  # DJI has no class


# ---------------------------------------------------------------------------
# ISK helpers
# ---------------------------------------------------------------------------

def _apply_isk_rules(item: dict, flags: list, applied_defaults: list) -> None:
    # ISK/ISK-RTJ: size + class are key; rest of spec is passed through as-is
    item['face_type'] = None
    item['thickness_mm'] = None
    item['standard'] = item.get('standard') or 'ASME B16.5'


def apply_rules(item: dict) -> dict:
    """
    Normalize, apply defaults, validate, and assign status + flags.
    Returns updated item dict.
    """
    flags = []
    applied_defaults = []

    # --- Normalize size ---
    raw_size = item.get('size')
    size_norm = normalize_size(raw_size) if raw_size else None
    item['size_norm'] = size_norm

    # --- Normalize rating ---
    raw_rating = item.get('rating')
    rating_norm = normalize_rating(raw_rating) if raw_rating else None
    item['rating_norm'] = rating_norm

    is_pn = raw_rating and str(raw_rating).upper().startswith('PN')
    is_asme = raw_rating and '#' in str(raw_rating)

    gasket_type = item.get('gasket_type', 'SOFT_CUT')

    if gasket_type == 'SPIRAL_WOUND':
        _apply_sw_rules(item, flags, applied_defaults)
        item['dimensions'] = None
    elif gasket_type == 'RTJ':
        _apply_rtj_rules(item, flags, applied_defaults)
        item['dimensions'] = None
    elif gasket_type == 'KAMM':
        _apply_kamm_rules(item, flags, applied_defaults)
        item['dimensions'] = None
    elif gasket_type == 'DJI':
        _apply_dji_rules(item, flags, applied_defaults)
        item['dimensions'] = None
    elif gasket_type in ('ISK', 'ISK_RTJ'):
        _apply_isk_rules(item, flags, applied_defaults)
        item['dimensions'] = None
    else:
        # --- Normalize MOC (soft cut) ---
        raw_moc = (item.get('moc') or '').strip().upper()
        if raw_moc in _AMBIGUOUS_MOC:
            flags.append('MOC "RUBBER" is ambiguous — confirm: Natural Rubber / EPDM / Neoprene / Chloroprene?')
            item['moc'] = raw_moc
        elif raw_moc in _MOC_ALIASES:
            item['moc'] = _MOC_ALIASES[raw_moc]
        elif raw_moc:
            item['moc'] = raw_moc
            if raw_moc not in ACCEPTED_MOC and raw_moc not in _MOC_ALIASES:
                flags.append(f'MOC "{raw_moc}" not in standard list — verify spelling')

        # --- Default: face_type ---
        if not item.get('face_type'):
            if is_pn:
                item['face_type'] = 'FF'
            else:
                item['face_type'] = 'RF'
            applied_defaults.append('face type defaulted to ' + item['face_type'])

        # --- Default: thickness ---
        if not item.get('thickness_mm'):
            item['thickness_mm'] = 3
            applied_defaults.append('thickness defaulted to 3mm')

        # --- Default: standard ---
        if not item.get('standard'):
            item['standard'] = 'EN 1514-1' if is_pn else 'ASME B16.21'
            applied_defaults.append('standard defaulted to ' + item['standard'])

        # --- Dimension lookup ---
        dims = None
        if size_norm and rating_norm:
            dims = lookup_dimensions(size_norm, rating_norm, item['face_type'])
        item['dimensions'] = dims
        if not dims and size_norm:
            flags.append('Size/rating not found in standard dimension table — may be non-standard')

    # Business rule: NPS inch size + ASME # pressure class → standard must be ASME (not EN/DIN/BS)
    if size_norm and '"' in str(size_norm) and is_asme:
        current_std = item.get('standard') or ''
        if current_std.startswith('EN') or current_std.startswith('DIN') or current_std.startswith('BS'):
            if gasket_type in ('SPIRAL_WOUND', 'RTJ', 'KAMM'):
                item['standard'] = 'ASME B16.20'
            else:
                item['standard'] = 'ASME B16.21'

    # --- Default: UoM ---
    if item.get('uom') == 'M':
        flags.append('UoM is meters (sheet supply) — confirm if individual gaskets or sheet supply')

    # --- Critical field validation — varies by type ---
    if gasket_type == 'RTJ':
        crit = ['size', 'rating', 'moc', 'ring_no']
    elif gasket_type == 'KAMM':
        crit = ['size', 'rating', 'sw_winding_material']
    elif gasket_type == 'DJI':
        crit = ['od_mm', 'id_mm', 'thickness_mm', 'moc']
    elif gasket_type in ('ISK', 'ISK_RTJ'):
        crit = ['size', 'rating']
    else:
        crit = CRITICAL_FIELDS  # ['size', 'rating', 'moc']

    missing_critical = []
    for field in crit:
        val = item.get(field)
        if not val:
            missing_critical.append(field)

    if missing_critical:
        flags.extend([f'Missing critical field: {f}' for f in missing_critical])

    if not item.get('quantity'):
        flags.append('Quantity not provided')

    # --- Assign status ---
    if missing_critical or any('ambiguous' in f.lower() or 'missing critical' in f.lower() for f in flags):
        item['status'] = STATUS_MISSING
    elif applied_defaults:
        item['status'] = STATUS_CHECK
        item['applied_defaults'] = applied_defaults
    else:
        item['status'] = STATUS_READY

    item['flags'] = flags
    return item
