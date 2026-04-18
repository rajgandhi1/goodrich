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
STATUS_REGRET = 'regret'

# Fields that cannot be defaulted — must be provided by customer
CRITICAL_FIELDS = ['size', 'rating', 'moc']

_MOC_ALIASES = {
    # --- Non-asbestos fiber ---
    'COMPRESSED NON ASBESTOS FIBER': 'CNAF',
    'COMPRESSED NON-ASBESTOS FIBER': 'CNAF',
    'NON ASBESTOS COMPRESSED FIBER': 'CNAF',
    'NON ASBESTOS COMPRESSED FIBER GRADE': 'CNAF',
    'NON-ASBESTOS COMPRESSED FIBER': 'CNAF',
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
    # --- PTFE variants & brand names ---
    'PTFE ENVELOPE': 'NON ASBESTOS PTFE ENVELOPED',
    'PTFE ENVELOP': 'NON ASBESTOS PTFE ENVELOPED',
    'PTFE ENVELOPE, FILLED W/COMP. N.ASB': 'NON ASBESTOS PTFE ENVELOPED',
    'PTFE ENVELOP WITH NON ABS': 'NON ASBESTOS PTFE ENVELOPED',
    'PTFE GORE TEX SERIES 300/EQUIVALENT': 'EXPANDED PTFE',
    'PTFE GORE TEX SERIES 300': 'EXPANDED PTFE',
    'GORE TEX': 'EXPANDED PTFE',
    'PTFE (TEADIT 24SH)': 'PTFE',
    'EXPENDED PTFE (MAX 76 SHORE A HARDNESS)': 'EXPANDED PTFE',
    'EXPANDED PTFE (MAX 76 SHORE A HARDNESS)': 'EXPANDED PTFE',
    'PTFE WITH UNS32760 INSERT': 'PTFE WITH UNS32760 INSERT',
    'PTFE WITH UNS32760 INSERT GASKET': 'PTFE WITH UNS32760 INSERT',
    # --- EPDM variants ---
    'EPDM, HARDNESS 70- +/- 5 SHORE A': 'EPDM',
    'EPDM HARDNESS 70 SHORE A': 'EPDM',
    'EPDM WITH STEEL INSERT KROLL ZILLER/EQUIVALENT': 'EPDM WITH STEEL INSERT',
    'EPDM RUBBER WITH STEEL INSERT FLAT RING WITH INTEGRATED O-RING': 'EPDM WITH STEEL INSERT',
    'EPDM RUBBER GASKET WITH W/2 PLY CLOTH INSERT': 'EPDM WITH CLOTH INSERT',
    'EPDM WITH CLOTH INSERT': 'EPDM WITH CLOTH INSERT',
    'EPDM/HNBR': 'EPDM/HNBR',
    # --- Rubber types WITH INSERT (normalizing base name) ---
    'NITRILE RUBBER WITH SS304 INSERT': 'NITRILE BUTADIENE RUBBER WITH SS304 INSERT',
    'NITRILE RUBBER WITH SS316 INSERT': 'NITRILE BUTADIENE RUBBER WITH SS316 INSERT',
    'NITRILE RUBBER WITH MS INSERT': 'NITRILE BUTADIENE RUBBER WITH MS INSERT',
    'NITRILE RUBBER WITH STEEL INSERT': 'NITRILE BUTADIENE RUBBER WITH STEEL INSERT',
    'FLUOROCARBON RUBBER WITH SS304 INSERT': 'VITON WITH SS304 INSERT',
    'FLUOROCARBON RUBBER WITH SS316 INSERT': 'VITON WITH SS316 INSERT',
    'FLUOROCARBON RUBBER WITH MS INSERT': 'VITON WITH MS INSERT',
    'FLUOROCARBON RUBBER WITH STEEL INSERT': 'VITON WITH STEEL INSERT',
    'POLYCHLOROPRENE RUBBER WITH SS304 INSERT': 'NEOPRENE WITH SS304 INSERT',
    'POLYCHLOROPRENE RUBBER WITH SS316 INSERT': 'NEOPRENE WITH SS316 INSERT',
    'POLYCHLOROPRENE RUBBER WITH MS INSERT': 'NEOPRENE WITH MS INSERT',
    'POLYCHLOROPRENE RUBBER WITH STEEL INSERT': 'NEOPRENE WITH STEEL INSERT',
    'CHLOROPRENE RUBBER WITH SS304 INSERT': 'NEOPRENE WITH SS304 INSERT',
    'CHLOROPRENE RUBBER WITH SS316 INSERT': 'NEOPRENE WITH SS316 INSERT',
    'CHLOROPRENE RUBBER WITH MS INSERT': 'NEOPRENE WITH MS INSERT',
    'CHLOROPRENE RUBBER WITH STEEL INSERT': 'NEOPRENE WITH STEEL INSERT',
    'CHLOROSULFONATED RUBBER WITH SS304 INSERT': 'CHLOROSULFONATED POLYETHYLENE RUBBER WITH SS304 INSERT',
    'CHLOROSULFONATED RUBBER WITH SS316 INSERT': 'CHLOROSULFONATED POLYETHYLENE RUBBER WITH SS316 INSERT',
    'CHLOROSULFONATED RUBBER WITH MS INSERT': 'CHLOROSULFONATED POLYETHYLENE RUBBER WITH MS INSERT',
    'CHLOROSULFONATED RUBBER WITH STEEL INSERT': 'CHLOROSULFONATED POLYETHYLENE RUBBER WITH STEEL INSERT',
    # --- Graphite variants ---
    'FABRICATED FLEXIBLE/EXPANDED GRAPHITE GASKET': 'EXPANDED GRAPHITE',
    'FLEXIBLE/EXPANDED GRAPHITE GASKET': 'EXPANDED GRAPHITE',
    'LEXIBLE/EXPANDED GRAPHITE GASKET': 'EXPANDED GRAPHITE',
    'PURE GRAPHITE WITH PERFORATED SS316 PLATE INSIDE': 'FLEXIBLE GRAPHITE WITH SS316 INSERT',
    # --- Rubber with hardness specs ---
    'NEOPRENE, SHORE A60-70': 'NEOPRENE',
    'NEOPRENE, SHORE A 60-70': 'NEOPRENE',
    'REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70': 'NEOPRENE',
    'REINFORCED CHLOROPRENE RUBBER SHORE A HARDNESS OF 70': 'NEOPRENE',
    # --- Non-asbestos variants ---
    'ARAMID FIBRE WITH NBRBINDER': 'ARAMID FIBER WITH NBR BINDER',
    'NON-ASB SYNT FIBER WITH NITRILE BUTADIENE,RUBBER BINDER': 'CNAF',
    'NON-ASBESTOS SYNT FIBER WITH NITRILE BUTADIENE,RUBBER BINDER': 'CNAF',
    'NON ASBESTOS SYNT FIBER WITH NITRILE BUTADIENE RUBBER BINDER': 'CNAF',
    'CNAF NON GRAPHITE GASKET': 'CNAF',
    'NON ASBESTOS BS7531 GRX': 'NON ASBESTOS BS7531',
    'NON ASBESTOS TYPE BS 7531 GR. X': 'NON ASBESTOS BS7531',
    'NON ASBESTOS SHEET WITH OIL RESIST': 'NON ASBESTOS',
    'NON ASBESTOS OR CNAF': 'CNAF',
    'ASBESTOS-FREE': 'NON ASBESTOS',
    # --- Asbestos/CAF variants ---
    'COMPRESSED ASBESTOS(IS 2712 GR. W/2)': 'CAF',
    'COMPRESSED ASBESTOS (IS 2712 GR. W/2)': 'CAF',
    'COMPRESSED ASBESTOS(IS 2712 Gr. W/2)': 'CAF',
    # --- Thermiculite ---
    'FLEXITALLIC TYPE THERMICULITE 715 OR EQUIVALENT GASKET': 'THERMICULITE 715',
    # --- Brand names ---
    'KLINGERSIL C4500': 'KLINGERSIL C4500',
    'KROLLER & ZILLER (G-S-T-P/S) WITH SPACER': 'KROLLER & ZILLER (G-S-T-P/S)',
    'KROLL ZILLER/EQUIVALENT': 'KROLLER & ZILLER (G-S-T-P/S)',
    'WIRE REINFORCED NEOPRENE RUBBER': 'WIRE REINFORCED NEOPRENE RUBBER',
    # --- Rubber reinforced variants ---
    'RUBBER-STGASKET RUBBER REINFORCED': 'EPDM WITH STEEL INSERT',
    'RUBBER STGASKET RUBBER REINFORCED': 'EPDM WITH STEEL INSERT',
    'RUBBER REINFORCED': 'EPDM WITH STEEL INSERT',
    'RUBBER-ST GASKET RUBBER REINFORCED': 'EPDM WITH STEEL INSERT',
}

# Generic "RUBBER" is ambiguous — must ask customer
_AMBIGUOUS_MOC = {'RUBBER'}

# ---------------------------------------------------------------------------
# Thickness normalisation — inch fractions and decimal inches → mm
# ---------------------------------------------------------------------------

# Fractional inch strings → mm  (e.g. "1/8" → 3.2)
_FRAC_INCH_TO_MM: dict[str, float] = {
    '1/64': 0.40,  '1/32': 0.80,  '3/64': 1.20,  '1/16': 1.60,
    '5/64': 2.00,  '3/32': 2.40,  '1/8':  3.20,  '5/32': 4.00,
    '11/64': 4.50, '3/16': 4.80,  '9/32': 7.20,  '1/4':  6.40,
    '5/16': 8.00,
}

# Decimal inch values → mm  (exact matches only — avoids false conversion of valid mm values)
_DECIMAL_INCH_TO_MM: dict[float, float] = {
    0.0039: 0.10,  0.0100: 0.25,  0.0157: 0.40,  0.0197: 0.50,
    0.0312: 0.80,  0.0468: 1.20,  0.0625: 1.60,  0.0781: 2.00,
    0.0937: 2.40,  0.1250: 3.20,  0.1574: 4.00,  0.1750: 4.50,
    0.1875: 4.80,  0.2500: 6.40,  0.2834: 7.20,  0.3150: 8.00,
    # rounded variants that appear in supplier data
    0.020:  0.50,  0.031:  0.80,  0.039:  1.00,  0.060:  1.50,
    0.079:  2.00,  0.098:  2.50,  0.118:  3.00,  0.125:  3.20,
    0.157:  4.00,  0.177:  4.50,  0.188:  4.80,  0.197:  5.00,
    0.236:  6.00,  0.250:  6.40,  0.276:  7.00,  0.315:  8.00,
}


def _parse_thickness_to_mm(raw: str) -> float | None:
    """Parse a thickness string that may be in mm or inches, return mm float or None."""
    s = raw.strip().rstrip('"\'').strip()
    # Strip unit suffix but remember if inch unit was explicit
    inch_explicit = bool(re.search(r'["\'"]|\bIN(CH(ES?)?)?\b', s, re.IGNORECASE))
    cleaned = re.sub(r'\s*(?:MM|THK|THICK|INCH(ES?)?|IN|"|\')\s*', '', s, flags=re.IGNORECASE).strip()

    # Try fractional form first: "1/8", "3/16", "1 1/8" (whole + fraction)
    frac_m = re.fullmatch(r'(\d+)\s+(\d+)/(\d+)', cleaned)
    if frac_m:
        whole, num, den = int(frac_m.group(1)), int(frac_m.group(2)), int(frac_m.group(3))
        inch_val = whole + num / den
        return round(inch_val * 25.4, 2)
    frac_m = re.fullmatch(r'(\d+)/(\d+)', cleaned)
    if frac_m:
        key = f'{frac_m.group(1)}/{frac_m.group(2)}'
        if key in _FRAC_INCH_TO_MM:
            return _FRAC_INCH_TO_MM[key]
        return round(int(frac_m.group(1)) / int(frac_m.group(2)) * 25.4, 2)

    # Plain number
    try:
        val = float(cleaned)
    except ValueError:
        return None

    if inch_explicit:
        return round(val * 25.4, 2)

    # No explicit unit — check if value matches a known decimal-inch entry
    rounded = round(val, 4)
    if rounded in _DECIMAL_INCH_TO_MM:
        return _DECIMAL_INCH_TO_MM[rounded]

    return val  # assume mm


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
    # --- Zinc plated / galvanised carbon steel ring ---
    'ZINC PLATED CARBON STEEL': 'ZINC PLATED CARBON STEEL',
    'ZINC-PLATED CARBON STEEL': 'ZINC PLATED CARBON STEEL',
    'ZINC PLATED CS': 'ZINC PLATED CARBON STEEL',
    'ZINC PLATED MS': 'ZINC PLATED CARBON STEEL',
    # --- Duplex / super duplex (common aliases) ---
    'DUPLEX': 'UNS S31803', '2205': 'UNS S32205',
    'SUPER DUPLEX': 'UNS S32750', 'SDSS': 'UNS S32750', '2507': 'UNS S32750',
}


# Filler material codes/aliases for spiral wound and KAMM gaskets
# Source: Customer Enq - Quote Data - Material .csv (Filler Material section)
_SW_FILLER_ALIASES = {
    'FG': 'FLEXIBLE GRAPHITE', 'FLEXIBLE GRAPHITE': 'FLEXIBLE GRAPHITE', 'GRAPHITE': 'GRAPHITE',
    'EXFOLIATED GRAPHITE': 'GRAPHITE', 'EXPANDED GRAPHITE': 'GRAPHITE',
    # Flexible inhibited graphite (corrosion-inhibited grade — noted explicitly in GGPL descriptions)
    'FLEXIBLE INHIBITED GRAPHITE': 'FLEXIBLE INHIBITED GRAPHITE',
    'FLEX INHIB GRAPHITE': 'FLEXIBLE INHIBITED GRAPHITE',
    'FLEXITALLIC INHIBITED GRAPHITE': 'FLEXIBLE INHIBITED GRAPHITE',
    'INHIBITED GRAPHITE': 'FLEXIBLE INHIBITED GRAPHITE',
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
    # If filler has a parenthetical qualifier (e.g. "GRAPHITE (98% PURE GRAPHITE)"),
    # place the FILLER keyword before the parenthetical for correct GGPL format.
    paren_m = re.match(r'^(.*?)\s*(\(.*\))\s*$', filler.strip())
    if paren_m:
        filler_str = f'{paren_m.group(1).strip()} FILLER {paren_m.group(2).strip()}'
    else:
        filler_str = f'{filler} FILLER'
    moc = f'{winding_mat} SPIRAL WOUND GASKET WITH {filler_str}'
    if inner_ring and outer_ring:
        moc += f' + {inner_ring} INNER RING & {outer_ring} OUTER RING'
    elif outer_ring:
        moc += f' + {outer_ring} OUTER RING'
    return moc


_B1647_FLAG = (
    'Missing critical field: B16.47 Series A or B not specified — '
    'Series A (ex-API 605, larger OD) and Series B (ex-MSS SP-44, smaller OD) '
    'have DIFFERENT gasket dimensions — customer must confirm'
)


def _set_b1647_standard(item: dict, flags: list, applied_defaults: list) -> None:
    """Normalize B16.47 standard and flag if series A/B not specified."""
    std = (item.get('standard') or '').upper()
    if 'SERIES A' in std or 'SERIES-A' in std:
        item['standard'] = 'ASME B16.47 (SERIES-A)'
        return
    if 'SERIES B' in std or 'SERIES-B' in std:
        item['standard'] = 'ASME B16.47 (SERIES-B)'
        return
    item['standard'] = 'ASME B16.47'
    if _B1647_FLAG not in flags:
        flags.append(_B1647_FLAG)  # Contains "missing critical" → triggers STATUS_MISSING


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

    # Inner ring mandatory rules (ASME B16.20)
    is_pn_sw = str(item.get('rating') or '').upper().startswith('PN')
    cls_m = re.search(r'(\d+)', str(item.get('rating') or ''))
    pressure_cls = int(cls_m.group(1)) if cls_m else 0
    inner_mandatory = False
    inner_reason = ''
    if 'PTFE' in (filler or '').upper():
        inner_mandatory = True
        inner_reason = 'PTFE-filled SPW always requires inner ring (ASME B16.20)'
    elif pressure_cls == 2500 and size_val is not None and size_val >= 4:
        inner_mandatory = True
        inner_reason = 'Inner ring mandatory: 2500# NPS ≥ 4" (ASME B16.20)'
    elif pressure_cls == 1500 and size_val is not None and size_val >= 12:
        inner_mandatory = True
        inner_reason = 'Inner ring mandatory: 1500# NPS ≥ 12" (ASME B16.20)'
    elif pressure_cls == 900 and size_val is not None and size_val >= 24:
        inner_mandatory = True
        inner_reason = 'Inner ring mandatory: 900# NPS ≥ 24" (ASME B16.20)'

    if not inner_ring:
        if inner_mandatory:
            flags.append(f'Missing critical field: inner ring — {inner_reason}')
        else:
            flags.append('Inner ring not specified — confirm if required for this service')

    # Handle "SS" without grade — ambiguous, cannot build valid MOC
    grade_flag_fired = False
    if winding_mat == 'SS':
        flags.append('Spiral wound: winding grade not specified — confirm SS304/SS316/SS316L/etc.')
        grade_flag_fired = True
        winding_mat = None
        item['sw_winding_material'] = None

    # FLEXIBLE INHIBITED GRAPHITE: GGPL convention is to also append the filler
    # as a note at the end of the description — store in special for formatter to pick up.
    if filler == 'FLEXIBLE INHIBITED GRAPHITE' and not item.get('special'):
        item['special'] = 'FLEXIBLE INHIBITED GRAPHITE FILLER'

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

    # Standard: EN 1514-2 for PN-rated, ASME B16.20 otherwise
    if not item.get('standard'):
        if is_pn_sw:
            item['standard'] = 'EN 1514-2'
            applied_defaults.append('standard defaulted to EN 1514-2 (SPW on PN-rated flanges)')
        elif size_val is not None and size_val >= 26:
            _set_b1647_standard(item, flags, applied_defaults)
        else:
            item['standard'] = 'ASME B16.20'
            applied_defaults.append('standard defaulted to ASME B16.20')


# ---------------------------------------------------------------------------
# RTJ helpers
# ---------------------------------------------------------------------------

_RTJ_HARDNESS_DEFAULTS = {
    'SOFTIRON': 90,
    'SOFTIRON GALVANISED': 90,
    'SOFTIRON ELECTROPLATED': 90,
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
    # Nickel alloys (ASME B16.20 / API 6A max BHN values)
    'MONEL 400': 130, 'MONEL 800': 150,
    'INCONEL 600': 160,                          # Alloy 600 (UNS N06600)
    'INCONEL 625': 210,                          # Alloy 625 (UNS N06625) — GGPL standard
    'INCONEL 718': 160,
    'HASTELLOY C276': 200,                       # UNS N10276
    'HASTELLOY C22': 200,
    'ALLOY 20': 160,
    'INCOLOY 825': 160,                          # Alloy 825 (UNS N08825)
    'INCOLOY 800': 160,                          # Alloy 800 (UNS N08800)
    '6MO': 200,                                  # UNS S31254 (6% Mo super austenitic)
    # Chrome-moly
    'F5': 130,                                   # 4–6% Cr, 0.5% Mo (ASME B16.20 Table 1)
    '4-6% CR 0.5% MO': 130,
    # UNS designations
    'UNS N06600': 160,  # Inconel 600
    'UNS N08825': 160,  # Incoloy 825
    'UNS N08800': 160,  # Incoloy 800
    'UNS S31600': 160,  # SS316
    'UNS S31603': 160,  # SS316L
    'UNS S30400': 160,  # SS304
    'UNS N06625': 160,  # Inconel 625
    'UNS S31254': 200,  # 6Mo
    # Titanium
    'TITANIUM GR.2': 215, 'TITANIUM GR.12': 215,
    # Duplex / super duplex — 22 HRC max = ~250 BHN (ASME B16.20 Annex A)
    'UNS S31803': 250, 'UNS S32205': 250,        # Duplex 2205
    'UNS S32750': 250, 'UNS S32760': 250,        # Super Duplex
    # Non-ferrous
    'CU-NI 70/30': 100, 'BRASS': 80, 'BRONZE': 80, 'ALUMINIUM': 35,
}

# Max BHN per material — used to validate customer-supplied hardness
_RTJ_MAX_BHN = _RTJ_HARDNESS_DEFAULTS.copy()

_RTJ_MOC_ALIASES = {
    # Soft iron
    'SOFT IRON': 'SOFTIRON', 'SOFTIRON': 'SOFTIRON', 'SI': 'SOFTIRON', 'S.I.': 'SOFTIRON',
    'SOFT IRON GALVANISED': 'SOFTIRON GALVANISED',
    'SOFT IRON GALVANIZED': 'SOFTIRON GALVANISED',
    'GALVANISED SOFT IRON': 'SOFTIRON GALVANISED',
    'GALVANIZED SOFT IRON': 'SOFTIRON GALVANISED',
    'SOFT IRON ELECTROPLATED': 'SOFTIRON ELECTROPLATED',
    'SOFTIRON ELECTROPLATED': 'SOFTIRON ELECTROPLATED',
    'SOFT IRON ZINC PLATED': 'SOFTIRON GALVANISED',
    'SOFT IRON CN+ZN PLATED': 'SOFTIRON GALVANISED',
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
    'INCONEL 600': 'INCONEL 600', 'INCONEL600': 'INCONEL 600', 'INC 600': 'INCONEL 600', 'ALLOY 600': 'INCONEL 600',
    'UNS N06600': 'INCONEL 600', 'N06600': 'INCONEL 600',
    'INCONEL 718': 'INCONEL 718', 'INCONEL718': 'INCONEL 718',
    'INCONEL': 'INCONEL 625', 'INCONEL 625': 'INCONEL 625', 'INCONEL625': 'INCONEL 625',
    'INC 625': 'INCONEL 625', 'INC625': 'INCONEL 625',
    'INCOLOY 825': 'INCOLOY 825', 'INCOLOY825': 'INCOLOY 825', 'INCOLY 825': 'INCOLOY 825',
    'INCOLOY': 'INCOLOY 825',   # bare "Incoloy" is most commonly 825 in RTJ context
    'INCOLOY 800': 'INCOLOY 800', 'INCOLOY800': 'INCOLOY 800', 'INCOLY 800': 'INCOLOY 800',
    'HASTELLOY C276': 'HASTELLOY C276', 'HAST ALLOY C276': 'HASTELLOY C276', 'C276': 'HASTELLOY C276',
    'HASTELLOY C22': 'HASTELLOY C22', 'C22': 'HASTELLOY C22',
    'F5': 'F5', '4-6% CR 0.5% MO': 'F5', '4-6CR 0.5MO': 'F5', 'CHROME MOLY': 'F5', 'CR-MO': 'F5',
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
    # Normalize MOC — if LLM returned null, try to recover from raw_description via aliases
    raw_moc = (item.get('moc') or '').strip().upper()
    if not raw_moc:
        raw_desc_upper = (item.get('raw_description') or '').upper()
        for alias_key in sorted(_RTJ_MOC_ALIASES, key=len, reverse=True):
            if re.search(r'\b' + re.escape(alias_key) + r'\b', raw_desc_upper):
                raw_moc = alias_key
                break
    if raw_moc.startswith('UNS '):
        norm_moc = raw_moc
    else:
        norm_moc = _RTJ_MOC_ALIASES.get(raw_moc, raw_moc) if raw_moc else None
    item['moc'] = norm_moc

    # Groove type — normalise abbreviation then default
    _groove_norm = {'OCT': 'OCTAGONAL', 'OVAL': 'OVAL'}
    if item.get('rtj_groove_type'):
        item['rtj_groove_type'] = _groove_norm.get(
            item['rtj_groove_type'].upper(), item['rtj_groove_type'].upper()
        )
    else:
        item['rtj_groove_type'] = 'OCTAGONAL'
        applied_defaults.append('groove type defaulted to OCTAGONAL')

    # Convert HRBW (Rockwell B) to BHN if the description contains HRB/HRBW values
    # (customer spec sheets sometimes use HRB instead of BHN)
    _HRBW_TO_BHN = {68: 120, 83: 160}
    raw_desc = (item.get('raw_description') or '').upper()
    if not item.get('rtj_hardness_bhn'):
        hrb_m = re.search(r'(\d+)\s*HRB(?:W)?\b', raw_desc)
        if hrb_m:
            hrb_val = int(hrb_m.group(1))
            bhn_converted = _HRBW_TO_BHN.get(hrb_val)
            if bhn_converted:
                item['rtj_hardness_bhn'] = bhn_converted
                item['rtj_hardness_spec'] = f'{bhn_converted}BHN HARDNESS'
                applied_defaults.append(f'converted {hrb_val} HRBW → {bhn_converted} BHN')

    # BHN hardness — default from MOC, then validate against material maximum
    if not item.get('rtj_hardness_bhn') and not item.get('rtj_hardness_spec') and norm_moc:
        bhn = _RTJ_HARDNESS_DEFAULTS.get(norm_moc)
        if bhn:
            item['rtj_hardness_bhn'] = bhn
            item['rtj_hardness_spec'] = f"{bhn} BHN HARDNESS"
            applied_defaults.append(f'BHN hardness defaulted to {bhn} for {norm_moc}')
        else:
            # BHN is mandatory on all RTJ gaskets (ASME B16.20)
            flags.append(
                f'RTJ BHN hardness not known for "{norm_moc}" — confirm BHN value with customer (ASME B16.20)'
            )
    elif item.get('rtj_hardness_bhn') and not item.get('rtj_hardness_spec'):
        item['rtj_hardness_spec'] = f"{int(item['rtj_hardness_bhn'])} BHN HARDNESS"
    elif not item.get('rtj_hardness_bhn') and not item.get('rtj_hardness_spec') and not norm_moc:
        flags.append('RTJ BHN hardness not specified — confirm with customer (ASME B16.20)')

    # Validate supplied BHN does not exceed material maximum (ASME B16.20)
    if norm_moc and item.get('rtj_hardness_bhn'):
        max_bhn = _RTJ_MAX_BHN.get(norm_moc)
        if max_bhn and float(item['rtj_hardness_bhn']) > max_bhn:
            flags.append(
                f'RTJ BHN {int(item["rtj_hardness_bhn"])} exceeds max allowed {max_bhn} BHN '
                f'for {norm_moc} (ASME B16.20) — verify with customer'
            )

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

    # Set standard based on ring prefix, rating, or bore size
    rn_upper = (item.get('ring_no') or '').upper()
    rating = item.get('rating') or ''
    if rating.startswith('API ') or item.get('standard') == 'API 6A':
        item['standard'] = 'API 6A'
    elif rn_upper.startswith('RX-'):
        item['standard'] = 'NACE MR-01-75 / ISO 15156, API 6B'
    elif rn_upper.startswith('BX-'):
        item['standard'] = 'ASME B16.20'
    else:
        size_val = _size_nps_value_from_item(item)
        if size_val is not None and size_val >= 26:
            _set_b1647_standard(item, flags, applied_defaults)
        else:
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
            item['moc'] = f'KAMMPROFILE {winding_mat} WITH {filler} LAYER ON BOTH SIDES'
    elif not item.get('moc'):
        flags.append('KAMM: winding material not identified — verify SS316/SS304/etc.')

    if not item.get('thickness_mm'):
        item['thickness_mm'] = 4.5
        applied_defaults.append('thickness defaulted to 4.5mm (KAMM)')

    # No standard for custom OD/ID KAMM; only for NPS-rated KAMM
    if item.get('size_type') != 'OD_ID' and not item.get('standard'):
        is_pn_kamm = str(item.get('rating') or '').upper().startswith('PN')
        size_val = _size_nps_value(item.get('size_norm'))
        if is_pn_kamm:
            item['standard'] = 'EN 1514-6'
            applied_defaults.append('standard defaulted to EN 1514-6 (KAMM on PN-rated flanges)')
        elif size_val is not None and size_val >= 26:
            _set_b1647_standard(item, flags, applied_defaults)
        else:
            item['standard'] = 'ASME B16.20'
            applied_defaults.append('standard defaulted to ASME B16.20')

    item['face_type'] = None


# ---------------------------------------------------------------------------
# DJI helpers
# ---------------------------------------------------------------------------

def _apply_dji_rules(item: dict, flags: list, applied_defaults: list) -> None:
    if not item.get('od_mm') or not item.get('id_mm'):
        flags.append('DJI: OD and ID dimensions required')
    if not item.get('thickness_mm'):
        flags.append('DJI: thickness not specified — confirm with customer')
    item['face_type'] = None
    # Default filler to GRAPHITE if not extracted by LLM
    if not item.get('dji_filler'):
        item['dji_filler'] = 'GRAPHITE'
        applied_defaults.append('DJI filler defaulted to GRAPHITE')
    # EN 1514-4 for PN-rated flanges; no standard otherwise (DJI is OD/ID based)
    is_pn_dji = str(item.get('rating') or '').upper().startswith('PN')
    item['standard'] = 'EN 1514-4' if is_pn_dji else None
    if is_pn_dji:
        applied_defaults.append('standard set to EN 1514-4 (DJI on PN-rated flanges)')
    item['rating'] = None  # DJI has no pressure class


# ---------------------------------------------------------------------------
# ISK helpers
# ---------------------------------------------------------------------------

_FIRE_SAFE_RE = re.compile(r'\bFIRE\s*SAFE\b', re.IGNORECASE)
_NON_FIRE_SAFE_RE = re.compile(r'\bNON[-\s]FIRE\s*SAFE\b', re.IGNORECASE)
# Spring-energised seal patterns → NON FIRE SAFE
_SPRING_SEAL_RE = re.compile(
    r'\bPRES\s+ENRG\b|\bPRESSURE\s+ENERGI[SZ]ED\b|\bSPRING[\s-]ENERGI[SZ]ED\b|'
    r'\bSPIRL\s+SPRING\b|\bSPIRAL\s+SPRING\b|\bSPRING\s+SEAL\b|\bSS\s+PRES\s+ENRG\b',
    re.IGNORECASE,
)
# TEFLON/PTFE flat seal patterns → FIRE SAFE
_TEFLON_SEAL_RE = re.compile(
    r'\bW/TEFLON\s+SEALS?\b|\bTEFLON\s+SEALS?\b|\bPTFE/EPDM\s+SEAL\b|\bW/TEFLON\b',
    re.IGNORECASE,
)


def _infer_isk_fire_safety(item: dict) -> str | None:
    """Infer ISK fire safety from description and special field using regex patterns.
    Returns 'FIRE SAFE', 'NON FIRE SAFE', or None if undeterminable.
    """
    combined = ' '.join(filter(None, [
        item.get('raw_description', ''),
        item.get('special', ''),
    ]))
    if _NON_FIRE_SAFE_RE.search(combined):
        return 'NON FIRE SAFE'
    if _FIRE_SAFE_RE.search(combined):
        return 'FIRE SAFE'
    # Domain rules
    if _SPRING_SEAL_RE.search(combined):
        return 'NON FIRE SAFE'
    if _TEFLON_SEAL_RE.search(combined):
        return 'FIRE SAFE'
    return None


_ISK_MATERIAL_RE = re.compile(
    r'(GLASS\s+REINFORCED\s+EPOXY\b.*|GRE\s+G[-\s]?1[01]\b.*)',
    re.IGNORECASE,
)
# Boilerplate in WAFER-format descriptions that should be stripped
_ISK_WAFER_BOILERPLATE_RE = re.compile(
    r'(?:MANUFACTURE\s+STD\s+WAFER\s+\d+\s+R\.?F\.?\s*\(125-250\s+AARH\)\s*_?\s*|'
    r'Standard\s+MANUFACTURE\s+STD\s+WAFER\s+\d+\s+R\.?F\.?\s*)',
    re.IGNORECASE,
)


def _extract_isk_special_from_desc(item: dict) -> str | None:
    """When LLM fails to populate 'special' for ISK, try to extract material
    description from the raw_description. Handles WAFER-format ISK descriptions like:
    'NPS: 16 ... MANUFACTURE STD WAFER 300 R.F. (125-250 AARH) _ GLASS REINFORCED EPOXY (NEMA G10) W/TEFLON SEALS SS 316 METAL CORE REINFORCEMENT'
    → 'GLASS REINFORCED EPOXY (NEMA G10) W/TEFLON SEALS SS 316 METAL CORE REINFORCEMENT'
    """
    raw = (item.get('raw_description') or '').strip()
    # Strip the WAFER boilerplate then check for GRE/GLASS REINFORCED EPOXY
    cleaned = _ISK_WAFER_BOILERPLATE_RE.sub('', raw)
    m = _ISK_MATERIAL_RE.search(cleaned)
    if m:
        return m.group(0).strip()
    return None


# Matches core material in raw ISK descriptions: "316 SS CORE", "SS316 CORE", "SS 316 CORE",
# "SS316L CORE", "DUPLEX CORE", "INCONEL CORE", "CS CORE", etc.
_ISK_CORE_RE = re.compile(
    r'\b(?:SS\s*3\d{2}L?|3\d{2}L?\s*SS|DUPLEX|SUPER\s+DUPLEX|INCONEL|HASTELLOY|CS|CARBON\s+STEEL|ALLOY\s+\w+)\s+CORE\b',
    re.IGNORECASE,
)


def _recover_isk_core(item: dict) -> None:
    """If core material appears in raw description but is absent from special, append it.
    Skipped when isk_core_material is already populated (regex extractor already handled it)."""
    if item.get('isk_core_material'):
        return  # dedicated field already populated — no need to duplicate into special
    raw = (item.get('raw_description') or '').strip()
    special = (item.get('special') or '').upper()
    m = _ISK_CORE_RE.search(raw)
    if m and 'CORE' not in special:
        core_str = m.group(0).upper()
        # Normalise "316 SS CORE" → "SS316 CORE"
        core_str = re.sub(r'^(\d{3}L?)\s*(SS)', r'SS\1', core_str)
        item['special'] = (item['special'] + ', ' + core_str).lstrip(', ') if item.get('special') else core_str


_ISK_ABBREV = [
    # Abbreviation → full GGPL-standard term (applied to special field post-LLM)
    (re.compile(r'\bPRES(?:SURE)?\s+ENRG(?:IZED)?\b', re.IGNORECASE), 'PRESSURE ENERGIZED'),
    (re.compile(r'\bSPIRL\b', re.IGNORECASE), 'SPIRAL'),
    (re.compile(r'\bSPNG\b', re.IGNORECASE), 'SPRING'),
    (re.compile(r'\bENRG(?:IZED)?\b', re.IGNORECASE), 'ENERGIZED'),
    (re.compile(r'\bSPRING\s+ENRG(?:IZED)?\b', re.IGNORECASE), 'SPRING ENERGIZED'),
]


def _normalize_isk_special(special: str) -> str:
    """Expand common LLM abbreviations in ISK special field to full GGPL terms."""
    s = special
    for pattern, replacement in _ISK_ABBREV:
        s = pattern.sub(replacement, s)
    return s


def _apply_isk_rules(item: dict, flags: list, applied_defaults: list) -> None:
    gtype = item.get('gasket_type', 'ISK')

    # TYPE-E = full face (FF) by definition; TYPE-F = raised face (RF) always
    isk_style_raw = (item.get('isk_style') or '').upper()
    if 'TYPE-E' in isk_style_raw or isk_style_raw == 'TYPE E':
        item['face_type'] = 'FF'
    elif 'TYPE-F' in isk_style_raw or isk_style_raw == 'TYPE F':
        item['face_type'] = 'RF'  # Type F = raised face = always RF

    # Face type: extract from LLM or default RF
    if not item.get('face_type'):
        item['face_type'] = 'RF'
        applied_defaults.append('face type defaulted to RF (ISK)')

    item['thickness_mm'] = None

    # Normalize rating: ASME class numbers without '#' → add '#' (e.g. "300" → "300#")
    raw_rating = str(item.get('rating') or '').strip()
    if raw_rating and not raw_rating.upper().startswith('PN') and not raw_rating.endswith('#'):
        _ASME_CLASSES_ISK = {150, 300, 600, 900, 1500, 2500, 3000}
        try:
            if int(raw_rating) in _ASME_CLASSES_ISK:
                item['rating'] = raw_rating + '#'
        except ValueError:
            pass

    # If LLM failed to extract special, try regex extraction from raw description.
    # Skip when regex_extractor already populated the dedicated component fields.
    if not item.get('special') and not item.get('isk_gasket_material'):
        extracted_special = _extract_isk_special_from_desc(item)
        if extracted_special:
            item['special'] = extracted_special

    # Normalize common ISK component abbreviations in special field
    if item.get('special'):
        item['special'] = _normalize_isk_special(item['special'])

    # Default seal/gasket material to PTFE SPRING ENERGIZED SEAL if nothing extracted
    if not item.get('isk_gasket_material') and not item.get('special'):
        item['isk_gasket_material'] = 'PTFE SPRING ENERGIZED SEAL'
        applied_defaults.append('ISK gasket material defaulted to PTFE SPRING ENERGIZED SEAL')

    # Recover core material the LLM may have dropped (e.g. "316 SS CORE" → appended to special)
    _recover_isk_core(item)

    # Fire safety: regex inference is more reliable than LLM for this field
    # (LLM can cross-contaminate values across batched items).
    # Inference overrides LLM when it finds a clear pattern.
    inferred_fs = _infer_isk_fire_safety(item)
    if inferred_fs:
        item['isk_fire_safety'] = inferred_fs
    # else: keep LLM value (if any) or leave None

    # Track whether the customer explicitly stated a standard (used by formatter)
    customer_standard = item.get('standard')
    item['isk_standard_explicit'] = bool(
        customer_standard and str(customer_standard).lower() not in ('null', 'none', '')
    )

    if gtype == 'ISK_RTJ':
        if not item.get('standard'):
            item['standard'] = 'ASME B16.5'
            applied_defaults.append('standard defaulted to ASME B16.5 (ISK_RTJ)')
    else:
        # Standard ISK: always determine from size per GGPL convention
        # (GGPL uses B16.20 for <26" and B16.47 for ≥26", regardless of what customer states)
        is_pn = str(item.get('rating') or '').upper().startswith('PN')
        if is_pn:
            item['standard'] = 'EN 1514-5'
            applied_defaults.append('standard set to EN 1514-5 (ISK on PN-rated flanges)')
        else:
            nps_val = _size_nps_value_from_item(item)
            if nps_val is not None and nps_val >= 26:
                _set_b1647_standard(item, flags, applied_defaults)
            else:
                item['standard'] = 'ASME B16.20'
                applied_defaults.append('standard set to ASME B16.20 (ISK)')


def _sanitize_llm_nulls(item: dict) -> dict:
    """Convert LLM-returned string 'null' / 'none' / '' to actual None.
    Parses thickness strings including fractions and inch values; strips unit
    suffixes from other numeric fields.
    """
    _NULL_STRINGS = {'null', 'none', 'n/a', 'na', ''}
    _OTHER_NUMERIC = ('od_mm', 'id_mm', 'rtj_hardness_bhn')
    for key, val in list(item.items()):
        if not isinstance(val, str):
            continue
        stripped = val.strip()
        if stripped.lower() in _NULL_STRINGS:
            item[key] = None
        elif key == 'thickness_mm':
            item[key] = _parse_thickness_to_mm(stripped)
        elif key in _OTHER_NUMERIC:
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

    # If "non-metallic" is mentioned in the original description, force SOFT_CUT
    raw_desc = (item.get('description') or '').upper()
    if re.search(r'NON[\s\-]?METALLIC', raw_desc) and gasket_type not in ('SOFT_CUT',):
        gasket_type = 'SOFT_CUT'
        item['gasket_type'] = 'SOFT_CUT'

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
    elif gasket_type not in ('SOFT_CUT',):
        # Unrecognised gasket type — pass through but flag for manual review
        flags.append(
            f'Unrecognised gasket type "{gasket_type}" — verify and convert to GGPL format manually'
        )
        item['dimensions'] = None
    else:
        # --- Normalize MOC (soft cut) ---
        raw_moc = (item.get('moc') or '').strip().upper()
        # Normalize brand+number codes: "AF 139" → "AF139", "AF 157" → "AF157", etc.
        import re as _re_moc
        raw_moc = _re_moc.sub(r'\bAF\s+(\d)', r'AF\1', raw_moc)
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
            # "X / EQUIVALENT" or "X OR EQUIVALENT" specs are passed through verbatim — don't flag
            _is_equivalent_spec = (
                '/ EQUIVALENT' in raw_moc
                or '/EQUIVALENT' in raw_moc
                or 'OR EQUIVALENT' in raw_moc
                or '/ EQUAL' in raw_moc
            )
            if not _is_composite and not _is_equivalent_spec and raw_moc not in ACCEPTED_MOC and raw_moc not in _MOC_ALIASES:
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
                    _set_b1647_standard(item, flags, applied_defaults)
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
                    _set_b1647_standard(item, flags, applied_defaults)
                else:
                    item['standard'] = 'ASME B16.21'

    # --- Normalize B16.47: flag if series not specified (handles LLM-extracted standards) ---
    std = item.get('standard') or ''
    if 'B16.47' in std and 'SERIES' not in std.upper():
        _set_b1647_standard(item, flags, applied_defaults)

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
