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
    # --- Non-asbestos fiber ---
    'COMPRESSED NON ASBESTOS FIBER': 'CNAF',
    'COMPRESSED NON-ASBESTOS FIBER': 'CNAF',
    'NON ASBESTOS FIBER': 'CNAF',
    'NON-ASBESTOS FIBER': 'CNAF',
    'NON ASBESTOS FIBRE': 'CNAF',
    'NON ASB': 'CNAF',
    'NAF': 'CNAF',
    'NON ASBESTOS': 'NON ASBESTOS',
    'CNAF': 'CNAF',
    # --- Rubber types ---
    'NEOPRENE': 'NEOPRENE',
    'CHLOROPRENE': 'NEOPRENE',
    'CHLOROPRENE RUBBER': 'NEOPRENE',
    'POLYCHLOROPRENE': 'NEOPRENE',
    'POLYCHLOROPRENE RUBBER': 'NEOPRENE',
    'NATURAL RUBBER': 'NATURAL RUBBER',
    'NR': 'NATURAL RUBBER',
    'EPDM': 'EPDM',
    'EPDM RUBBER': 'EPDM',
    'ETHYLENE PROPYLENE': 'EPDM',
    'BUTYL RUBBER': 'BUTYL RUBBER',
    'BUTYL': 'BUTYL RUBBER',
    'IIR': 'BUTYL RUBBER',
    'NITRILE BUTADIENE RUBBER': 'NITRILE BUTADIENE RUBBER',
    'NITRILE RUBBER': 'NITRILE BUTADIENE RUBBER',
    'NBR': 'NITRILE BUTADIENE RUBBER',
    'BUNA-N': 'BUNA-N',
    'NITRILE': 'NITRILE BUTADIENE RUBBER',
    'HNBR': 'HNBR RUBBER',
    'HNBR RUBBER': 'HNBR RUBBER',
    'HYDROGENATED NITRILE': 'HNBR RUBBER',
    'HYDROGENATED NBR': 'HNBR RUBBER',
    'SILICONE': 'SILICONE RUBBER',
    'SILICONE RUBBER': 'SILICONE RUBBER',
    'VMQ': 'SILICONE RUBBER',
    'VITON': 'VITON',
    'FKM': 'VITON',
    'FLUOROCARBON RUBBER': 'VITON',
    'FLUOROELASTOMER': 'VITON',
    'SBR': 'STYRENE-BUTADIENE RUBBER',
    'STYRENE BUTADIENE RUBBER': 'STYRENE-BUTADIENE RUBBER',
    'STYRENE-BUTADIENE RUBBER': 'STYRENE-BUTADIENE RUBBER',
    'CHLOROSULFONATED RUBBER': 'CHLOROSULFONATED POLYETHYLENE RUBBER',
    'CHLOROSULFONATED POLYETHYLENE RUBBER': 'CHLOROSULFONATED POLYETHYLENE RUBBER',
    'CSM': 'CHLOROSULFONATED POLYETHYLENE RUBBER',
    'HYPALON': 'CHLOROSULFONATED POLYETHYLENE RUBBER',
    'POLYURETHANE': 'POLYURETHANE RUBBER',
    'POLYURETHANE RUBBER': 'POLYURETHANE RUBBER',
    'PU': 'POLYURETHANE RUBBER',
    'THERMOPLASTIC POLYURETHANE RUBBER': 'THERMOPLASTIC POLYURETHANE RUBBER',
    'TPU': 'THERMOPLASTIC POLYURETHANE RUBBER',
    'THERMOPLASTIC RUBBER': 'THERMOPLASTIC RUBBER',
    'TPR': 'THERMOPLASTIC RUBBER',
    'POLYISOPRENE RUBBER': 'POLYISOPRENE RUBBER',
    'POLYISOPRENE': 'POLYISOPRENE RUBBER',
    'POLYISOBUTYLENE RUBBER': 'POLYISOBUTYLENE RUBBER',
    'PIB': 'POLYISOBUTYLENE RUBBER',
    'ETHYLENE-VINYL ACETATE RUBBER': 'ETHYLENE-VINYL ACETATE RUBBER',
    'ETHYLENE VINYL ACETATE': 'ETHYLENE-VINYL ACETATE RUBBER',
    'EVA': 'ETHYLENE-VINYL ACETATE RUBBER',
    'ACRYLONITRILE BUTADIENE STYRENE RUBBER': 'ACRYLONITRILE BUTADIENE STYRENE RUBBER',
    'ABS RUBBER': 'ACRYLONITRILE BUTADIENE STYRENE RUBBER',
    'STYRENE-ETHYLENE-BUTYLENE-STYRENE RUBBER': 'STYRENE-ETHYLENE-BUTYLENE-STYRENE RUBBER',
    'SEBS': 'STYRENE-ETHYLENE-BUTYLENE-STYRENE RUBBER',
    'STYRENE-ISOPRENE-STYRENE RUBBER': 'STYRENE-ISOPRENE-STYRENE RUBBER',
    'SIS': 'STYRENE-ISOPRENE-STYRENE RUBBER',
    'POLYAMIDE RUBBER': 'POLYAMIDE RUBBER',
    'NYLON RUBBER': 'NYLON RUBBER',
    'NYLON': 'NYLON RUBBER',
    'WIRE REINFORCED NEOPRENE RUBBER': 'WIRE REINFORCED NEOPRENE RUBBER',
    'ELASTOMER': 'ELASTOMER',
    # --- PTFE / Fluoropolymer ---
    'PTFE': 'PTFE',
    'TEFLON': 'PTFE',
    'VIRGIN PTFE': 'PTFE',
    'PURE PTFE': 'PTFE',
    'EXPANDED PTFE': 'EXPANDED PTFE',
    'EPTFE': 'EXPANDED PTFE',
    'E-PTFE': 'EXPANDED PTFE',
    'EXPENDED PTFE': 'EXPANDED PTFE',
    'REINFORCED PTFE': 'REINFORCED PTFE',
    'PTFE ENVELOPED': 'NON ASBESTOS PTFE ENVELOPED',
    'POLYVINYLIDENE FLUORIDE': 'POLYVINYLIDENE FLUORIDE',
    'PVDF': 'POLYVINYLIDENE FLUORIDE',
    # --- Graphite family ---
    'GRAPHITE': 'GRAPHITE',
    'GRAFOIL': 'GRAPHITE',
    'GRAPHOIL': 'GRAPHITE',
    'FLEXIBLE GRAPHITE': 'GRAPHITE',
    'EXFOLIATED GRAPHITE': 'EXPANDED GRAPHITE',
    'EXFOLIATED EXPANDED GRAPHITE': 'EXPANDED GRAPHITE',
    'EXPANDED GRAPHITE': 'EXPANDED GRAPHITE',
    '98% EXPANDED GRAPHITE': 'EXPANDED GRAPHITE',
    'FLEXIBLE/EXPANDED GRAPHITE': 'EXPANDED GRAPHITE',
    'EXPANDED GRAPHITE WITH SS304 REINFORCEMENT': 'EXPANDED GRAPHITE WITH SS304 REINFORCEMENT',
    'EXPANDED GRAPHITE WITH SS304 RENFORCEMENT': 'EXPANDED GRAPHITE WITH SS304 REINFORCEMENT',
    '98% EXPANDED GRAPHITE WITH SS304 RENFORCEMENT': 'EXPANDED GRAPHITE WITH SS304 REINFORCEMENT',
    '98% EXPANDED GRAPHITE WITH SS304 REINFORCEMENT': 'EXPANDED GRAPHITE WITH SS304 REINFORCEMENT',
    'EXPANDED GRAPHITE WITH SS316 REINFORCEMENT': 'EXPANDED GRAPHITE WITH SS316 REINFORCEMENT',
    'EXPANDED GRAPHITE WITH SS316 RENFORCEMENT': 'EXPANDED GRAPHITE WITH SS316 REINFORCEMENT',
    '98% EXPANDED GRAPHITE WITH SS316 RENFORCEMENT': 'EXPANDED GRAPHITE WITH SS316 REINFORCEMENT',
    '98% EXPANDED GRAPHITE WITH SS316 REINFORCEMENT': 'EXPANDED GRAPHITE WITH SS316 REINFORCEMENT',
    'GRAPHITE WITH SS304 INSERT': 'FLEXIBLE GRAPHITE WITH SS304 INSERT',
    'GRAPHITE WITH SS316 INSERT': 'FLEXIBLE GRAPHITE WITH SS316 INSERT',
    'GRAPHITE WITH SS316L INSERT': 'FLEXIBLE GRAPHITE WITH SS316 INSERT',
    'FLEXIBLE GRAPHITE WITH SS304 INSERT': 'FLEXIBLE GRAPHITE WITH SS304 INSERT',
    'FLEXIBLE GRAPHITE WITH SS316 INSERT': 'FLEXIBLE GRAPHITE WITH SS316 INSERT',
    'FLEXIBLE GRAPHITE REINFORCED W/SS316': 'FLEXIBLE GRAPHITE WITH SS316 INSERT',
    'GRAPHITE WITH MS INSERT': 'FLEXIBLE GRAPHITE WITH MS INSERT',
    'GRAPHITE WITH STEEL INSERT': 'FLEXIBLE GRAPHITE WITH STEEL INSERT',
    'GRAPHITE WITH 2 METAL FOILS': 'GRAPHITE WITH 2 METAL FOILS',
    'CORRUGATED GRAPHITE WITH SS316': 'CORRUGATED GRAPHITE WITH SS316',
    'CORRUGATED GASKET SS316 ENCAPSULATED WITH GRAPHITE': 'CORRUGATED GRAPHITE WITH SS316',
    # --- Fiber / specialty ---
    'ARAMID FIBER': 'ARAMID FIBER',
    'ARAMID FIBRE': 'ARAMID FIBER',
    'ARAMIDE FIBER': 'ARAMID FIBER',
    'ARAMIDE FIBRE': 'ARAMID FIBER',
    'ARAMID': 'ARAMID FIBER',
    'KEVLAR': 'ARAMID FIBER',
    'ARAMID FIBER WITH NBR BINDER': 'ARAMID FIBER WITH NBR BINDER',
    'ARAMID FIBRE WITH NBR BINDER': 'ARAMID FIBER WITH NBR BINDER',
    'ARAMID W/ NITRILE BINDER': 'ARAMID FIBER WITH NITRILE BINDER',
    'ARAMID FIBER WITH NITRILE BINDER': 'ARAMID FIBER WITH NITRILE BINDER',
    'NON-ASB SYNTHETIC FIBER WITH NITRILE BINDER': 'CNAF',
    'NON ASBESTOS SYNTHETIC FIBER': 'NON ASBESTOS SYNTHETIC FIBER',
    'NON-ASBESTOS SHEET NBR BINDER': 'NON ASBESTOS SYNTHETIC FIBER',
    'SYNTHETIC FIBRE': 'SYNTHETIC FIBRE',
    'CERAMIC FIBER': 'CERAMIC FIBER',
    'CERAMIC FIBRE': 'CERAMIC FIBER',
    'CERAMIC': 'CERAMIC FIBER',
    'CERAFELT': 'CERAMIC FIBER',
    'NON ASBESTOS BS7531': 'NON ASBESTOS BS7531',
    'NON ASBESTOS TYPE BS 7531': 'NON ASBESTOS BS7531',
    'NONASBESTOSBS7531': 'NON ASBESTOS BS7531',
    'CORK': 'CORK',
    'LEATHER': 'LEATHER',
    'ASBESTOS FREE': 'NON ASBESTOS',
    'ASBESTOS FREE (WITH SBR)': 'SBR',
    'ASBESTOS FREE WITH SBR': 'SBR',
    'THERMICULITE 715': 'THERMICULITE 715',
    'THERMICULITE 715 OR EQUIVALENT': 'THERMICULITE 715',
    'FLEXITALLIC TYPE THERMICULITE 715 OR EQUIVALENT': 'THERMICULITE 715',
    'THERMICULITE 835': 'THERMICULITE 835',
    'THERMICULITE': 'THERMICULITE',
    'LEAKBLOK P200': 'LEAKBLOK P200',
    'LEAKBOK P200': 'LEAKBLOK P200',
    'LEAKBOK P200 OR EQUIVALENT': 'LEAKBLOK P200',
    'LEAKBLOK P200 OR EQUIVALENT': 'LEAKBLOK P200',
    'ASBESTOS': 'CAF',
    'COMPRESSED ASBESTOS FIBER': 'CAF',
    'COMPRESSED ASBESTOS': 'CAF',
    'IS 2712': 'CAF',
    'CAF': 'CAF',
    # --- Rubber WITH INSERT pass-throughs (common combinations) ---
    'EPDM WITH STEEL INSERT': 'EPDM WITH STEEL INSERT',
    'EPDM RUBBER WITH STEEL INSERT': 'EPDM WITH STEEL INSERT',
    'EPDM WITH SS304 INSERT': 'EPDM WITH SS304 INSERT',
    'EPDM RUBBER WITH SS304 INSERT': 'EPDM WITH SS304 INSERT',
    'EPDM WITH SS316 INSERT': 'EPDM WITH SS316 INSERT',
    'EPDM RUBBER WITH SS316 INSERT': 'EPDM WITH SS316 INSERT',
    'EPDM WITH MS INSERT': 'EPDM WITH MS INSERT',
    'EPDM RUBBER WITH MS INSERT': 'EPDM WITH MS INSERT',
    'PTFE WITH SS304 INSERT': 'PTFE WITH SS304 INSERT',
    'PTFE WITH SS316 INSERT': 'PTFE WITH SS316 INSERT',
    'PTFE WITH MS INSERT': 'PTFE WITH MS INSERT',
    'PTFE WITH STEEL INSERT': 'PTFE WITH STEEL INSERT',
    'NATURAL RUBBER WITH SS304 INSERT': 'NATURAL RUBBER WITH SS304 INSERT',
    'NATURAL RUBBER WITH SS316 INSERT': 'NATURAL RUBBER WITH SS316 INSERT',
    'NATURAL RUBBER WITH STEEL INSERT': 'NATURAL RUBBER WITH STEEL INSERT',
    'NATURAL RUBBER WITH MS INSERT': 'NATURAL RUBBER WITH MS INSERT',
    # --- Viton ---
    'VITON GASKET': 'VITON GASKET',
}

# Generic "RUBBER" is ambiguous — must ask customer
_AMBIGUOUS_MOC = {'RUBBER'}

# ---------------------------------------------------------------------------
# Spiral wound helpers
# ---------------------------------------------------------------------------

_SW_RING_ALIASES = {
    # --- Carbon/mild steel ---
    'CARBON STEEL': 'CS', 'C.S.': 'CS', 'MS': 'CS', 'M.S.': 'CS',
    'MILD STEEL': 'CS', 'CS': 'CS',
    # --- SS300-series austenitic ---
    'SS304': 'SS304', 'SS 304': 'SS304', '304': 'SS304', '304SS': 'SS304',
    '304 SS': 'SS304', 'AISI 304': 'SS304', 'TYPE 304': 'SS304',
    'SS304L': 'SS304L', 'SS 304L': 'SS304L', '304L': 'SS304L', 'AISI 304L': 'SS304L',
    'SS310': 'SS310', 'SS 310': 'SS310', '310': 'SS310', 'AISI 310': 'SS310',
    'SS310S': 'SS310S', 'SS 310S': 'SS310S', '310S': 'SS310S',
    'SS316': 'SS316', 'SS 316': 'SS316', '316': 'SS316', '316SS': 'SS316',
    '316 SS': 'SS316', 'AISI 316': 'SS316', 'TYPE 316': 'SS316',
    'SS316L': 'SS316L', 'SS 316L': 'SS316L', '316L': 'SS316L', 'AISI 316L': 'SS316L',
    'SS316H': 'SS316H', 'SS 316H': 'SS316H', '316H': 'SS316H',
    'SS317': 'SS317', 'SS 317': 'SS317', '317': 'SS317',
    'SS317L': 'SS317L', 'SS 317L': 'SS317L', '317L': 'SS317L',
    'SS321': 'SS321', 'SS 321': 'SS321', '321': 'SS321',
    'SS321H': 'SS321H', 'SS 321H': 'SS321H', '321H': 'SS321H',
    'SS347': 'SS347', 'SS 347': 'SS347', '347': 'SS347',
    'SS347H': 'SS347H', 'SS 347H': 'SS347H', '347H': 'SS347H',
    # --- SS400-series ferritic/martensitic ---
    'SS410': 'SS410', 'SS 410': 'SS410', '410': 'SS410',
    'SS410S': 'SS410S', 'SS 410S': 'SS410S', '410S': 'SS410S',
    # --- Nickel alloys ---
    'INCOLOY 825': 'INCOLOY 825', 'INCOLOY825': 'INCOLOY 825', 'INCOLY 825': 'INCOLOY 825',
    'INC 825': 'INCOLOY 825', 'INC825': 'INCOLOY 825', 'INCOLOY': 'INCOLOY 825',
    'INCOLOY 800': 'INCOLOY 800', 'INCOLOY800': 'INCOLOY 800', 'INCOLY 800': 'INCOLOY 800',
    'INC 800': 'INCOLOY 800', 'INC800': 'INCOLOY 800',
    'INCONEL 625': 'INCONEL 625', 'INCONEL625': 'INCONEL 625',
    'INC 625': 'INCONEL 625', 'INC625': 'INCONEL 625', 'ALLOY 625': 'INCONEL 625',
    'INCOLY 625': 'INCONEL 625', 'INCONEL': 'INCONEL 625',
    'UNS N06625': 'INCONEL 625', 'N06625': 'INCONEL 625',
    # --- Other nickel/high alloys ---
    'HASTELLOY C276': 'HASTELLOY C276', 'HAST ALLOY C276': 'HASTELLOY C276',
    'HASTELLOY C-276': 'HASTELLOY C276', 'C276': 'HASTELLOY C276',
    'MONEL 400': 'MONEL 400', 'MONEL400': 'MONEL 400', 'MONEL': 'MONEL 400', 'ALLOY 400': 'MONEL 400',
    'MONEL 800': 'MONEL 800', 'MONEL800': 'MONEL 800',
    'ALLOY 20': 'ALLOY 20', 'ALLOY20': 'ALLOY 20', 'CARPENTER 20': 'ALLOY 20',
    '6MO': '6MO', '6 MO': '6MO', '6-MO': '6MO', '6% MO': '6MO',
    # --- UNS designations ---
    'UNS S31254': 'UNS S31254', 'S31254': 'UNS S31254', 'UNS31254': 'UNS S31254', '31254': 'UNS S31254',
    'UNS S31803': 'UNS S31803', 'S31803': 'UNS S31803', 'UNS31803': 'UNS S31803', '31803': 'UNS S31803',
    'UNS S32205': 'UNS S32205', 'S32205': 'UNS S32205', 'UNS32205': 'UNS S32205', '32205': 'UNS S32205',
    'UNS S32750': 'UNS S32750', 'S32750': 'UNS S32750', 'UNS32750': 'UNS S32750', '32750': 'UNS S32750',
    # --- Titanium ---
    'TITANIUM GR.2': 'TITANIUM GR.2', 'TITANIUM GRADE 2': 'TITANIUM GR.2', 'TI GR2': 'TITANIUM GR.2',
    'TITANIUM GR.12': 'TITANIUM GR.12', 'TITANIUM GRADE 12': 'TITANIUM GR.12', 'TI GR12': 'TITANIUM GR.12',
    # --- Non-ferrous metals ---
    'CU-NI 70/30': 'CU-NI 70/30', 'CUNI 70/30': 'CU-NI 70/30', 'CU-NI/70-30': 'CU-NI 70/30',
    'COPPER NICKEL 70/30': 'CU-NI 70/30',
    'BRASS': 'BRASS',
    'BRONZE': 'BRONZE',
    'ALUMINIUM': 'ALUMINIUM', 'ALUMINUM': 'ALUMINIUM', 'AL': 'ALUMINIUM',
    # --- Low temperature / special ---
    'LTCS': 'LTCS', 'LOW TEMP CARBON STEEL': 'LTCS', 'LOW TEMPERATURE CARBON STEEL': 'LTCS',
    # --- Soft iron (also used as winding/ring in some contexts) ---
    'SOFT IRON': 'SOFT IRON', 'SI': 'SOFT IRON', 'S.I.': 'SOFT IRON',
    # --- Duplex / super duplex (common aliases) ---
    'DUPLEX': 'UNS S31803', '2205': 'UNS S32205',
    'SUPER DUPLEX': 'UNS S32750', 'SDSS': 'UNS S32750', '2507': 'UNS S32750',
}


# Filler material codes/aliases for spiral wound and KAMM gaskets
# Source: Customer Enq - Quote Data - Material .csv (Filler Material section)
_SW_FILLER_ALIASES = {
    'FG': 'GRAPHITE', 'FLEXIBLE GRAPHITE': 'GRAPHITE', 'GRAPHITE': 'GRAPHITE',
    'EXFOLIATED GRAPHITE': 'GRAPHITE', 'EXPANDED GRAPHITE': 'GRAPHITE',
    'PTFE': 'PTFE', 'TEFLON': 'PTFE', 'VIRGIN PTFE': 'PTFE',
    'CNAF': 'CNAF', 'NON ASBESTOS': 'CNAF', 'NAF': 'CNAF',
    'CAF': 'CAF', 'ASBESTOS': 'CAF',
    'ARA': 'ARAMID', 'ARAMID': 'ARAMID', 'ARAMID FIBER': 'ARAMID', 'ARAMID FIBRE': 'ARAMID',
    'CER': 'CERAMIC', 'CERAMIC': 'CERAMIC', 'CERAMIC FIBER': 'CERAMIC', 'CERAMIC FIBRE': 'CERAMIC',
    'MICA': 'MICA', 'FLEXIBLE MICA': 'MICA', 'PHLOGOPITE MICA': 'MICA',
    'VERM': 'VERMICULITE', 'VERMICULITE': 'VERMICULITE',
    'GF': 'GLASS FIBER', 'GLASS FIBER': 'GLASS FIBER', 'GLASS FIBRE': 'GLASS FIBER', 'FIBERGLASS': 'GLASS FIBER',
    'NONE': None,
}


def _norm_ring(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().upper()
    return _SW_RING_ALIASES.get(key, key)


def _norm_filler(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().upper()
    return _SW_FILLER_ALIASES.get(key, key)


def _size_nps_value(size_norm: str | None) -> float | None:
    """Return numeric NPS value from a size string like '28"' or '28 NB'.
    For NB strings, returns None (NB number ≠ NPS number — must go through normalize_size first).
    """
    if not size_norm:
        return None
    s = str(size_norm)
    # If it's an NB string (e.g. "450 NB"), return None — the NPS equivalent
    # is stored in size_norm after normalize_size conversion.
    if re.search(r'\bNB\b', s, re.IGNORECASE):
        return None
    m = re.search(r'([\d.]+)', s)
    return float(m.group(1)) if m else None


def _size_nps_value_from_item(item: dict) -> float | None:
    """Return NPS value, trying size_norm first then raw size (for un-mapped large NPS)."""
    val = _size_nps_value(item.get('size_norm'))
    if val is not None:
        return val
    # Fallback: parse raw size string if it contains '"' (NPS inches, just not in size_map)
    raw = str(item.get('size') or '')
    if '"' in raw and 'NB' not in raw.upper():
        m = re.search(r'([\d.]+)', raw)
        return float(m.group(1)) if m else None
    return None


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
    filler = _norm_filler(item.get('sw_filler'))
    outer_ring = _norm_ring(item.get('sw_outer_ring'))
    inner_ring = _norm_ring(item.get('sw_inner_ring'))

    if not filler:
        filler = 'GRAPHITE'
        applied_defaults.append('filler defaulted to GRAPHITE')

    size_val = _size_nps_value(item.get('size_norm'))

    item['sw_outer_ring'] = outer_ring or None
    item['sw_inner_ring'] = inner_ring or None
    item['sw_filler'] = filler

    # Outer ring is mandatory for spiral wound gaskets
    if not outer_ring:
        flags.append('Missing critical field: outer ring (mandatory for spiral wound gaskets — e.g. CS, SS304)')

    # Inner ring is optional but should be confirmed
    if not inner_ring:
        flags.append('Inner ring not specified — confirm if inner ring is required')

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
    'LTCS': 120,
    # SS300-series austenitic
    'SS304': 160, 'SS304L': 160, 'F304': 160,
    'SS310': 160, 'SS310S': 160,
    'SS316': 160, 'SS316L': 160, 'SS316H': 160, 'F316': 160, 'F316L': 160,
    'SS317': 160, 'SS317L': 160,
    'SS321': 160, 'SS321H': 160,
    'SS347': 160, 'SS347H': 160,
    # SS400-series ferritic/martensitic (harder)
    'SS410': 170, 'SS410S': 150,
    # Nickel alloys
    'MONEL 400': 130, 'MONEL 800': 150,
    'INCONEL 625': 160,
    'HASTELLOY C276': 200,
    'ALLOY 20': 160,
    'INCOLOY 825': 160,
    'INCOLOY 800': 160,
    '6MO': 200,  # UNS S31254 (6% Mo super austenitic)
    # UNS designations
    'UNS N08825': 160,  # Incoloy 825
    'UNS N08800': 160,  # Incoloy 800
    'UNS S31600': 160,  # SS316
    'UNS S31603': 160,  # SS316L
    'UNS S30400': 160,  # SS304
    'UNS N06625': 160,  # Inconel 625
    'UNS S31254': 200,  # 6Mo
    # Titanium
    'TITANIUM GR.2': 200, 'TITANIUM GR.12': 200,
    # Non-ferrous
    'CU-NI 70/30': 100, 'BRASS': 80, 'BRONZE': 80, 'ALUMINIUM': 35,
    # Duplex/super duplex — BHN not defaulted (hardness spec set per applicable spec)
    # UNS S31803 / S32205 (Duplex 2205) max 22 HRC (~250 BHN) — flag for manual entry
    # UNS S32750 (Super Duplex) — same
}

_RTJ_MOC_ALIASES = {
    # Soft iron
    'SOFT IRON': 'SOFTIRON', 'SOFTIRON': 'SOFTIRON', 'SI': 'SOFTIRON', 'S.I.': 'SOFTIRON',
    'SOFT IRON GALVANISED': 'SOFTIRON GALVANISED',
    'SOFT IRON GALVANIZED': 'SOFTIRON GALVANISED',
    'GALVANISED SOFT IRON': 'SOFTIRON GALVANISED',
    'GALVANIZED SOFT IRON': 'SOFTIRON GALVANISED',
    # Carbon/low-alloy steel
    'LOW CARBON STEEL': 'LOW CARBON STEEL', 'LCS': 'LOW CARBON STEEL',
    'CARBON STEEL': 'LOW CARBON STEEL',
    'LTCS': 'LTCS', 'LOW TEMPERATURE CARBON STEEL': 'LTCS', 'LOW TEMP CARBON STEEL': 'LTCS',
    # SS austenitic
    'SS304': 'SS304', 'SS 304': 'SS304', '304SS': 'SS304', '304 SS': 'SS304', 'AISI 304': 'SS304',
    'SS304L': 'SS304L', 'SS 304L': 'SS304L', '304L': 'SS304L',
    'SS310': 'SS310', 'SS 310': 'SS310', 'SS310S': 'SS310S', 'SS 310S': 'SS310S',
    'SS316': 'SS316', 'SS 316': 'SS316', '316SS': 'SS316', '316 SS': 'SS316', 'AISI 316': 'SS316',
    'SS316L': 'SS316L', 'SS 316L': 'SS316L', '316L': 'SS316L',
    'SS316H': 'SS316H', 'SS 316H': 'SS316H', '316H': 'SS316H',
    'SS317': 'SS317', 'SS317L': 'SS317L',
    'SS321': 'SS321', 'SS321H': 'SS321H',
    'SS347': 'SS347', 'SS347H': 'SS347H',
    'SS410': 'SS410', 'SS410S': 'SS410S',
    'F304': 'F304', 'F316': 'F316', 'F316L': 'F316L',
    # Nickel alloys
    'MONEL': 'MONEL 400', 'MONEL 400': 'MONEL 400', 'MONEL400': 'MONEL 400', 'ALLOY 400': 'MONEL 400',
    'MONEL 800': 'MONEL 800', 'MONEL800': 'MONEL 800',
    'INCONEL': 'INCONEL 625', 'INCONEL 625': 'INCONEL 625', 'INCONEL625': 'INCONEL 625',
    'INC 625': 'INCONEL 625', 'INC625': 'INCONEL 625',
    'INCOLOY 825': 'INCOLOY 825', 'INCOLOY825': 'INCOLOY 825', 'INCOLY 825': 'INCOLOY 825',
    'INCOLOY': 'INCOLOY 825',   # bare "Incoloy" is most commonly 825 in RTJ context
    'INCOLOY 800': 'INCOLOY 800', 'INCOLOY800': 'INCOLOY 800', 'INCOLY 800': 'INCOLOY 800',
    'HASTELLOY C276': 'HASTELLOY C276', 'HAST ALLOY C276': 'HASTELLOY C276', 'C276': 'HASTELLOY C276',
    'ALLOY 20': 'ALLOY 20', 'ALLOY20': 'ALLOY 20', 'CARPENTER 20': 'ALLOY 20',
    '6MO': '6MO', '6 MO': '6MO',
    # UNS numbers
    'UNS N06625': 'INCONEL 625', 'N06625': 'INCONEL 625',
    'UNS S31254': 'UNS S31254', 'S31254': 'UNS S31254',
    'UNS S31803': 'UNS S31803', 'S31803': 'UNS S31803',
    'UNS S32205': 'UNS S32205', 'S32205': 'UNS S32205',
    'UNS S32750': 'UNS S32750', 'S32750': 'UNS S32750',
    # Duplex aliases
    'DUPLEX': 'UNS S31803', '2205': 'UNS S32205',
    'SUPER DUPLEX': 'UNS S32750', 'SDSS': 'UNS S32750', '2507': 'UNS S32750',
    # Titanium
    'TITANIUM GR.2': 'TITANIUM GR.2', 'TI GR2': 'TITANIUM GR.2', 'TITANIUM GRADE 2': 'TITANIUM GR.2',
    'TITANIUM GR.12': 'TITANIUM GR.12', 'TI GR12': 'TITANIUM GR.12', 'TITANIUM GRADE 12': 'TITANIUM GR.12',
    # Non-ferrous
    'CU-NI 70/30': 'CU-NI 70/30', 'CUNI 70/30': 'CU-NI 70/30', 'COPPER NICKEL 70/30': 'CU-NI 70/30',
    'BRASS': 'BRASS', 'BRONZE': 'BRONZE',
    'ALUMINIUM': 'ALUMINIUM', 'ALUMINUM': 'ALUMINIUM',
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

    # Normalize ring_no: "BX 156" / "R 24" / "RX53" / "R14" → "BX-156" / "R-24" / "RX-53" / "R-14"
    if item.get('ring_no'):
        rn = str(item['ring_no']).strip()
        # Space separator: "BX 156" → "BX-156"
        rn = re.sub(r'\b(BX|RX|R)\s+(\d+)\b', r'\1-\2', rn, flags=re.IGNORECASE)
        # No separator: "R14" → "R-14", "BX156" → "BX-156"
        rn = re.sub(r'\b(BX|RX)(\d+)\b', r'\1-\2', rn, flags=re.IGNORECASE)
        rn = re.sub(r'\bR(\d+)\b', r'R-\1', rn, flags=re.IGNORECASE)
        item['ring_no'] = rn.upper()

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
    filler = _norm_filler(item.get('sw_filler')) or 'GRAPHITE'
    outer_ring = _norm_ring(item.get('sw_outer_ring'))
    inner_ring = _norm_ring(item.get('sw_inner_ring'))

    if not filler:
        applied_defaults.append('filler defaulted to GRAPHITE')

    item['sw_filler'] = filler
    item['sw_outer_ring'] = outer_ring or None
    item['sw_inner_ring'] = inner_ring or None

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


def _sanitize_llm_nulls(item: dict) -> dict:
    """Convert LLM-returned string 'null' / 'none' / '' to actual None.
    Also strips unit suffixes from numeric fields (e.g. '4.5MM' → 4.5).
    """
    _NULL_STRINGS = {'null', 'none', 'n/a', 'na', ''}
    _NUMERIC_FIELDS = ('thickness_mm', 'od_mm', 'id_mm', 'rtj_hardness_bhn')
    for key, val in item.items():
        if not isinstance(val, str):
            continue
        stripped = val.strip()
        if stripped.lower() in _NULL_STRINGS:
            item[key] = None
        elif key in _NUMERIC_FIELDS:
            # Strip units and try to parse as float: "4.5MM" → 4.5, "3 THK" → 3
            cleaned = re.sub(r'\s*(?:MM|THK|INCH|IN|M)\s*$', '', stripped, flags=re.IGNORECASE).strip()
            try:
                item[key] = float(cleaned)
            except ValueError:
                item[key] = None
    return item


def apply_rules(item: dict) -> dict:
    """
    Normalize, apply defaults, validate, and assign status + flags.
    Returns updated item dict.
    """
    _sanitize_llm_nulls(item)
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
            # Don't flag composite MOCs like "EPDM WITH SS304 INSERT" or
            # "EXPANDED GRAPHITE WITH SS316 REINFORCEMENT" — these are valid combinations
            _is_composite = (
                ' WITH ' in raw_moc and (
                    'INSERT' in raw_moc
                    or 'REINFORCEMENT' in raw_moc
                    or 'RENFORCEMENT' in raw_moc
                )
            )
            if not _is_composite and raw_moc not in ACCEPTED_MOC and raw_moc not in _MOC_ALIASES:
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
            if is_pn:
                item['standard'] = 'EN 1514-1'
                applied_defaults.append('standard defaulted to EN 1514-1')
            else:
                # NPS ≥ 26" → ASME B16.47 (large bore); below 26" → ASME B16.21
                nps_val = _size_nps_value_from_item(item)
                if nps_val is not None and nps_val >= 26:
                    item['standard'] = 'ASME B16.47'
                    applied_defaults.append('standard defaulted to ASME B16.47 (large bore NPS ≥ 26")')
                    flags.append(
                        'Large bore (NPS ≥ 26") — ASME B16.47 has Series A (API 605) and Series B (MSS SP-44): '
                        'confirm which series with customer — dimensions differ'
                    )
                else:
                    item['standard'] = 'ASME B16.21'
                    applied_defaults.append('standard defaulted to ASME B16.21')

        # --- Dimension lookup ---
        dims = None
        if size_norm and rating_norm:
            dims = lookup_dimensions(size_norm, rating_norm, item['face_type'])
        item['dimensions'] = dims
        if not dims and size_norm and rating_norm:
            flags.append('Size/rating not found in standard dimension table — may be non-standard')

    # Business rule: NPS inch size + ASME # pressure class → standard must be ASME (not EN/DIN/BS)
    if size_norm and '"' in str(size_norm) and is_asme:
        current_std = item.get('standard') or ''
        if current_std.startswith('EN') or current_std.startswith('DIN') or current_std.startswith('BS'):
            if gasket_type in ('SPIRAL_WOUND', 'RTJ', 'KAMM'):
                item['standard'] = 'ASME B16.20'
            else:
                nps_val = _size_nps_value_from_item(item)
                if nps_val is not None and nps_val >= 26:
                    item['standard'] = 'ASME B16.47'
                else:
                    item['standard'] = 'ASME B16.21'

    # --- Default: UoM ---
    if item.get('uom') == 'M':
        flags.append('UoM is meters (sheet supply) — confirm if individual gaskets or sheet supply')

    # --- Critical field validation — varies by type ---
    if gasket_type == 'RTJ':
        crit = ['size', 'rating', 'moc', 'ring_no']
    elif gasket_type == 'KAMM':
        # OD/ID KAMM: check od_mm + id_mm + moc (moc built from sw_winding_material by rules engine)
        # NPS KAMM: check size + rating + moc
        if item.get('size_type') == 'OD_ID':
            crit = ['od_mm', 'id_mm', 'moc']
        else:
            crit = ['size', 'rating', 'moc']
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
    elif applied_defaults or flags:
        item['status'] = STATUS_CHECK
        item['applied_defaults'] = applied_defaults
    else:
        item['status'] = STATUS_READY

    item['flags'] = flags
    return item
