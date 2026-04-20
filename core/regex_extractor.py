from __future__ import annotations
"""
Regex-based gasket field extraction engine.
Extracts all structured fields from raw description strings using pattern matching.
Returns a dict matching the _null_extract() schema with a confidence score.

HIGH confidence items skip the LLM entirely.
MEDIUM/LOW items are sent to LLM, but regex-extracted values override LLM on merge.
"""
import re
from typing import Optional

# Import alias dicts from rules.py for MOC/material matching
from core.rules import (
    _MOC_ALIASES, _SW_RING_ALIASES, _SW_FILLER_ALIASES, _RTJ_MOC_ALIASES,
)

# ---------------------------------------------------------------------------
# Gasket type detection (same patterns as extractor.py)
# ---------------------------------------------------------------------------

_SW_RE = re.compile(
    r'SPIRAL[\s\-]?WOUND|\bSPRL[\s\-]?WND\b|\bSPWD?\b|\bSPWG\b|\bSWG\b|'
    r'\bGASW[\s:\-]|'
    r'\bS\.?W\.\s*GASKET|\bWND\b|'
    r'\bGASKETSSPIRAL\b|\bGASKETSPIRAL\b',
    re.IGNORECASE,
)
_RTJ_RE = re.compile(
    r'\bRTJ\b|\bR\.T\.J\b|\bR/J\b|\bRING[\s\-]TYPE\s+JOINT\b|'
    r'\bOCTAGONAL\s+RTJ\b|\bOCTAGONAL\s+RING\b|\bOVAL\s+RING\b|'
    r'\bOCTA(?:GONAL)?\s+R/J\b|'
    # Allow digit immediately before RING (e.g. "B16.20RING JOINT" where . separates)
    r'(?<![A-Za-z])RING\s+JOINT\b|\bJOINT\s+TOR[EI]\b|\bJOINT\s+TORIQUE\b',
    re.IGNORECASE,
)
_KAMM_RE = re.compile(r'KAMMPROFILE|\bKAMM\b|\bCAM[\s\-]?PROFILE\b|\bSKAG\b', re.IGNORECASE)
_DJI_RE = re.compile(
    r'\bDOUBLE[\s\-]?JACKET(?:ED)?\b|\bCOPPER\s+JACKET\b',
    re.IGNORECASE,
)
_ISK_RE = re.compile(
    r'\bINSULATING\s+GASKET\b|\bINSULATION\s+GASKET\b|'
    r'\bISK\b|\bINSULATION\s+KITS?\b|\bINSULATING\s+KITS?\b|'
    r'\bFLANGE\s+ISOLATION\b|\bISOLATION\s+GASKET\b|'
    r'\bINST\.?\s+KIT\b|\bGSKT\s+INSULATION\b',
    re.IGNORECASE,
)
_ISK_RTJ_RE = re.compile(
    r'\bISK\s+RTJ\b|\bISK\s+TYPE[\s\-]?RTJ\b|\bINSULATING\s+RING\s+TYPE\s+JOINT\b',
    re.IGNORECASE,
)


_SW_RING_KW_RE = re.compile(
    r'\bINNER\s+RING\b|\bOUTER\s+RING\b|\bCENTERING\s+RING\b|\bI/R\b|\bO/R\b|\bI\s+RING\b',
    re.IGNORECASE,
)


def _detect_type(desc: str) -> str:
    """Detect gasket type from keywords. Returns type string."""
    if _SW_RE.search(desc):
        return 'SPIRAL_WOUND'
    if _KAMM_RE.search(desc):
        return 'KAMM'
    if _DJI_RE.search(desc):
        return 'DJI'
    # ISK_RTJ before ISK before RTJ
    if _ISK_RTJ_RE.search(desc):
        return 'ISK_RTJ'
    if _ISK_RE.search(desc):
        # Check if it also mentions RTJ flange context
        if re.search(r'\bRTJ\b', desc, re.IGNORECASE) and not re.search(r'\bRF\b|\bFF\b', desc, re.IGNORECASE):
            return 'ISK_RTJ'
        return 'ISK'
    # RTJ before SW_RING_RE: "RING JOINT" / explicit RTJ keyword / ring number (R-35, BX-156)
    # takes priority over SW_RING_RE matching ring material names (e.g. SS347 is also an RTJ MOC)
    if _RTJ_RE.search(desc):
        return 'RTJ'
    if _RING_NO_RE.search(desc):
        return 'RTJ'
    # Inner/outer ring implies spiral wound (checked after RTJ to avoid false positives)
    if _SW_RING_KW_RE.search(desc):
        return 'SPIRAL_WOUND'
    return 'SOFT_CUT'


# ---------------------------------------------------------------------------
# Size extraction
# ---------------------------------------------------------------------------

_ASME_CLASSES = '150|300|600|900|1500|2500|3000'

# OD x ID patterns (various formats)
_OD_ID_RE = re.compile(
    r'OD[\s:\-=]*(\d+(?:\.\d+)?)\s*(?:MM)?\s*[XxX×,\s]+\s*'
    r'(?:\d+(?:\.\d+)?\s*[XxX×,\s]+\s*)?'  # optional middle dim (thickness)
    r'ID[\s:\-=]*(\d+(?:\.\d+)?)',
    re.IGNORECASE,
)
# Reversed: ID before OD
_ID_OD_RE = re.compile(
    r'ID[\s:\-=]*(\d+(?:\.\d+)?)\s*(?:MM)?\s*[XxX×,\s]+\s*'
    r'(?:\d+(?:\.\d+)?\s*[XxX×,\s]+\s*)?'
    r'OD[\s:\-=]*(\d+(?:\.\d+)?)',
    re.IGNORECASE,
)
# "346 GID x 372 GOD" — number BEFORE keyword (Gasket Inner/Outer Diameter)
_GID_GOD_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:MM)?\s*GID\b.*?(\d+(?:\.\d+)?)\s*(?:MM)?\s*GOD\b',
    re.IGNORECASE,
)
_GOD_GID_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:MM)?\s*GOD\b.*?(\d+(?:\.\d+)?)\s*(?:MM)?\s*GID\b',
    re.IGNORECASE,
)

# Parenthesized: "343(OD) x 210(ID)" or "343 (OD) x 210 (ID)"
_PAREN_OD_ID_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*\(\s*OD\s*\)\s*[XxX×,\s]+\s*'
    r'(\d+(?:\.\d+)?)\s*\(\s*ID\s*\)',
    re.IGNORECASE,
)
_PAREN_ID_OD_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*\(\s*ID\s*\)\s*[XxX×,\s]+\s*'
    r'(\d+(?:\.\d+)?)\s*\(\s*OD\s*\)',
    re.IGNORECASE,
)
# Bare NxN (DJI copper jacket pattern): "101X110 X1,5" — smaller=ID, larger=OD
_BARE_DIMS_RE = re.compile(
    r'(?:GASKET|JACKET)\s*(\d+(?:\.\d+)?)\s*[XxX×]\s*(\d+(?:\.\d+)?)\s*[XxX×]\s*(\d+(?:[.,]\d+)?)',
    re.IGNORECASE,
)
# DN format
_DN_RE = re.compile(r'\bDN[\s\-]*(\d+)\b', re.IGNORECASE)
# NB format
_NB_RE = re.compile(r'\b(\d+)\s*NB\b', re.IGNORECASE)
# NPS explicit: "NPS 6" or "NPS: 6"
_NPS_EXPLICIT_RE = re.compile(r'\bNPS[\s:]*(\d+(?:\.\d+)?)\b', re.IGNORECASE)
# NPS suffix: "2 NPS" or "30 NPS" (number before NPS keyword)
_NPS_SUFFIX_RE = re.compile(r'\b(\d+(?:\.\d+)?)\s+NPS\b', re.IGNORECASE)
# Inch with quote: 6" or 1.5" or 1-1/2"
_INCH_QUOTE_RE = re.compile(r'\b(\d+(?:\.\d+)?(?:\s*[-]\s*\d+/\d+)?)\s*"', re.IGNORECASE)
# "X INCH" or "X IN "
_INCH_WORD_RE = re.compile(r'\b(\d+(?:\.\d+)?)\s*(?:INCH(?:ES)?|IN)\b', re.IGNORECASE)
# Packed format: "4CL 150" or "1CL 300" — size glued to CL
_PACKED_SIZE_CL_RE = re.compile(
    rf'^(\d{{1,3}})(?:CL\s*(?:{_ASME_CLASSES}))', re.IGNORECASE
)
# Packed format: "24GASKET" — size glued to GASKET keyword
_PACKED_SIZE_GASKET_RE = re.compile(
    r'^(\d{1,3})(?:GASKET)', re.IGNORECASE
)
# Mixed fraction: "1 1/2" or "1-1/2"
_MIXED_FRAC_RE = re.compile(r'\b(\d+)\s*[-\s]\s*(\d+)/(\d+)\s*["\s]', re.IGNORECASE)
# "2.1/16" pattern (API flanges)
_API_FRAC_RE = re.compile(r'\b(\d+)\.(\d+)/(\d+)["\s]', re.IGNORECASE)
# Bare fractional decimal inch — no " suffix, appears between commas: ",0.875,"
# Matches sub-2" decimals (0.125–1.875) to avoid confusing with ratings/thicknesses
_BARE_FRAC_INCH_RE = re.compile(
    r'(?:^|,)\s*((?:0|1)\.\d{2,4})\s*(?:,|$)'
)


def _extract_size(desc: str, gasket_type: str) -> dict:
    """Extract size fields. Returns dict with size, size_type, od_mm, id_mm."""
    result = {'size': None, 'size_type': 'UNKNOWN', 'od_mm': None, 'id_mm': None}
    upper = desc.upper()

    # 1. OD x ID explicit (highest priority)
    m = _OD_ID_RE.search(upper)
    if m:
        result['od_mm'] = float(m.group(1))
        result['id_mm'] = float(m.group(2))
        result['size_type'] = 'OD_ID'
        return result

    # 1b. ID x OD reversed
    m = _ID_OD_RE.search(upper)
    if m:
        result['id_mm'] = float(m.group(1))
        result['od_mm'] = float(m.group(2))
        result['size_type'] = 'OD_ID'
        return result

    # 1c. Parenthesized: "343(OD) x 210(ID)"
    m = _PAREN_OD_ID_RE.search(upper)
    if m:
        result['od_mm'] = float(m.group(1))
        result['id_mm'] = float(m.group(2))
        result['size_type'] = 'OD_ID'
        return result

    m = _PAREN_ID_OD_RE.search(upper)
    if m:
        result['id_mm'] = float(m.group(1))
        result['od_mm'] = float(m.group(2))
        result['size_type'] = 'OD_ID'
        return result

    # 1d. "346 GID x 372 GOD" — Gasket Inner/Outer Diameter notation
    m = _GID_GOD_RE.search(upper)
    if m:
        result['id_mm'] = float(m.group(1))  # GID = inner diameter
        result['od_mm'] = float(m.group(2))  # GOD = outer diameter
        result['size_type'] = 'OD_ID'
        return result

    m = _GOD_GID_RE.search(upper)
    if m:
        result['od_mm'] = float(m.group(1))  # GOD = outer diameter
        result['id_mm'] = float(m.group(2))  # GID = inner diameter
        result['size_type'] = 'OD_ID'
        return result

    # 1e. Bare NxNxN for DJI (copper jacket): smaller=ID, larger=OD, last=thickness
    if gasket_type == 'DJI':
        m = _BARE_DIMS_RE.search(desc)
        if m:
            d1, d2 = float(m.group(1)), float(m.group(2))
            result['id_mm'] = min(d1, d2)
            result['od_mm'] = max(d1, d2)
            result['size_type'] = 'OD_ID'
            return result

    # 2. DN
    m = _DN_RE.search(upper)
    if m:
        result['size'] = f'DN {m.group(1)}'
        result['size_type'] = 'DN'
        return result

    # 3. NB
    m = _NB_RE.search(upper)
    if m:
        result['size'] = f'{m.group(1)} NB'
        result['size_type'] = 'NB'
        return result

    # 4. Mixed fraction: "1 1/2" or "1-1/2" — preserve as "1-1/2"
    m = _MIXED_FRAC_RE.search(desc)
    if m:
        whole = int(m.group(1))
        num, den = int(m.group(2)), int(m.group(3))
        result['size'] = f'{whole}-{num}/{den}"'
        result['size_type'] = 'NPS'
        return result

    # 4b. API fraction: "2.1/16"
    m = _API_FRAC_RE.search(desc)
    if m:
        whole = int(m.group(1))
        num, den = int(m.group(2)), int(m.group(3))
        val = whole + num / den
        result['size'] = f'{val}"'
        result['size_type'] = 'NPS'
        return result

    # 5. NPS explicit: "NPS 6"
    m = _NPS_EXPLICIT_RE.search(upper)
    if m:
        val = m.group(1)
        result['size'] = f'{val}"'
        result['size_type'] = 'NPS'
        return result

    # 5b. NPS suffix: "2 NPS" or "30 NPS"
    m = _NPS_SUFFIX_RE.search(upper)
    if m:
        val = m.group(1)
        result['size'] = f'{val}"'
        result['size_type'] = 'NPS'
        return result

    # 6. Inch with quote mark
    m = _INCH_QUOTE_RE.search(desc)
    if m:
        val = m.group(1).strip()
        result['size'] = f'{val}"'
        result['size_type'] = 'NPS'
        return result

    # 7. "X INCH"
    m = _INCH_WORD_RE.search(upper)
    if m:
        val = m.group(1)
        result['size'] = f'{val}"'
        result['size_type'] = 'NPS'
        return result

    # 8. Packed: "4CL 150GASKET" → size=4"
    m = _PACKED_SIZE_CL_RE.match(upper.replace(' ', ''))
    if m:
        result['size'] = f'{m.group(1)}"'
        result['size_type'] = 'NPS'
        return result

    # 8b. Packed: "24GASKET"
    m = _PACKED_SIZE_GASKET_RE.match(upper.replace(' ', ''))
    if m:
        result['size'] = f'{m.group(1)}"'
        result['size_type'] = 'NPS'
        return result

    # 8c. Packed "CL30012"" — size is the digits after the known ASME class
    m = _RATING_CL_PACKED_RE.search(desc)
    if m:
        result['size'] = f'{m.group(2)}"'
        result['size_type'] = 'NPS'
        return result

    # 9. Bare fractional decimal (no " suffix) between commas — e.g. ",0.875," in row data
    m = _BARE_FRAC_INCH_RE.search(desc)
    if m:
        val = float(m.group(1))
        if 0.125 <= val <= 1.875:
            result['size'] = f'{val}"'
            result['size_type'] = 'NPS'
            return result

    return result


# ---------------------------------------------------------------------------
# Rating extraction
# ---------------------------------------------------------------------------

# "150#" or "300 #" or "150 LB" or "150LB" or "150LBS"
_RATING_HASH_RE = re.compile(
    rf'\b({_ASME_CLASSES})\s*(?:#|LBS?\b)', re.IGNORECASE
)
# "CL 150" or "CL.150" or "CLASS 300" or "Cl.150"
_RATING_CL_RE = re.compile(
    rf'\bCL(?:ASS)?[\s.]*({_ASME_CLASSES})\b', re.IGNORECASE
)
# Packed "CL30012"" — class rating glued to size with trailing inch mark (e.g. CL30012")
_RATING_CL_PACKED_RE = re.compile(
    rf'\bCL({_ASME_CLASSES})(\d+(?:\.\d+)?)"', re.IGNORECASE
)
# "PN 10" or "PN16" or "PN 40"
_RATING_PN_RE = re.compile(r'\bPN[\s\-]*(\d+)\b', re.IGNORECASE)
# Packed: "INCL. 300" or "INCL.300" — the 300 is rating for garbled SPW
_RATING_INCL_RE = re.compile(
    rf'\bINCL\.?\s*({_ASME_CLASSES})\b', re.IGNORECASE
)
# "1500 PSI" pattern
_RATING_PSI_RE = re.compile(
    rf'\b({_ASME_CLASSES})\s*PSI\b', re.IGNORECASE
)
# "300RF" or "150FF" — ASME class with face type suffix directly appended (no space/# needed)
_RATING_FACE_RE = re.compile(
    rf'\b({_ASME_CLASSES})\s*(?:RF|FF|RTJ|RJ)\b', re.IGNORECASE
)
# "S-150" / "S-300" catalog series notation (e.g. Flexitallic CWR S-150)
_RATING_S_SERIES_RE = re.compile(
    rf'\bS-({_ASME_CLASSES})\b', re.IGNORECASE
)


def _extract_rating(desc: str) -> str | None:
    """Extract pressure rating. Returns formatted string like '150#' or 'PN 10'."""
    upper = desc.upper()

    # PN rating (check first to avoid PN being consumed by ASME)
    m = _RATING_PN_RE.search(upper)
    if m:
        return f'PN {m.group(1)}'

    # ASME class with # or LB
    m = _RATING_HASH_RE.search(upper)
    if m:
        return f'{m.group(1)}#'

    # CL/CLASS prefix
    m = _RATING_CL_RE.search(upper)
    if m:
        return f'{m.group(1)}#'

    # Packed "CL30012"" — extract rating from glued CL+rating+size token
    m = _RATING_CL_PACKED_RE.search(desc)
    if m:
        return f'{m.group(1)}#'

    # INCL. pattern (garbled SPW)
    m = _RATING_INCL_RE.search(upper)
    if m:
        return f'{m.group(1)}#'

    # PSI
    m = _RATING_PSI_RE.search(upper)
    if m:
        return f'{m.group(1)}#'

    # "300RF" / "150FF" — class with face-type suffix, no # symbol
    m = _RATING_FACE_RE.search(upper)
    if m:
        return f'{m.group(1)}#'

    # "S-150" catalog series notation
    m = _RATING_S_SERIES_RE.search(upper)
    if m:
        return f'{m.group(1)}#'

    return None


# ---------------------------------------------------------------------------
# MOC extraction — build regex from _MOC_ALIASES keys
# ---------------------------------------------------------------------------

def _build_moc_pattern(aliases: dict) -> re.Pattern:
    """Build a compiled regex alternation from alias dict keys, longest first."""
    keys = sorted(aliases.keys(), key=len, reverse=True)
    escaped = [re.escape(k) for k in keys]
    pattern = r'\b(' + '|'.join(escaped) + r')\b'
    return re.compile(pattern, re.IGNORECASE)


_SOFTCUT_MOC_RE = _build_moc_pattern(_MOC_ALIASES)
_RTJ_MOC_RE_PATTERN = _build_moc_pattern(_RTJ_MOC_ALIASES)
_SW_FILLER_RE_PATTERN = _build_moc_pattern(_SW_FILLER_ALIASES)


def _extract_softcut_moc(desc: str) -> str | None:
    """Extract MOC for soft cut gaskets using alias matching."""
    m = _SOFTCUT_MOC_RE.search(desc.upper())
    if m:
        raw = m.group(1).strip()
        return _MOC_ALIASES.get(raw, raw)
    return None


def _extract_rtj_moc(desc: str) -> str | None:
    """Extract MOC for RTJ gaskets."""
    m = _RTJ_MOC_RE_PATTERN.search(desc.upper())
    if m:
        raw = m.group(1).strip()
        return _RTJ_MOC_ALIASES.get(raw, raw)
    return None


# ---------------------------------------------------------------------------
# Thickness extraction
# ---------------------------------------------------------------------------

# "3MM THK" or "3 MM THK" or "3MMTHK"
_THK_MM_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:MM\s+)?THK', re.IGNORECASE)
# "4.5mm" or "3 mm" without THK — common in SPW descriptions
_THK_BARE_MM_RE = re.compile(r'[XxX×]\s*(\d+(?:\.\d+)?)\s*MM\b', re.IGNORECASE)
# "THK 3" or "THK-3" or "THK: 3" or "THCK, 2.0"
# "THCK:0.175 IN" — thickness in inches (label:value IN suffix); convert to mm
_THK_INCH_PREFIX_RE = re.compile(r'\bTHK?C?K?[\s:\-,]*(\d+(?:[.,]\d+)?)\s*IN(?:CH(?:ES)?)?\b', re.IGNORECASE)
_THK_PREFIX_RE = re.compile(r'\bTHK?C?K?[\s:\-,]*(\d+(?:[.,]\d+)?)', re.IGNORECASE)
# "3T" or "3T X" — common in DJI: "3T X 1285 OD"
_THK_T_RE = re.compile(r'\b(\d+(?:\.\d+)?)T\b', re.IGNORECASE)
# "x 4.5mm" at end or "x 4.5 mm" — last dimension in triplet
_THK_LAST_DIM_RE = re.compile(r'[XxX×]\s*(\d+(?:[.,]\d+)?)\s*(?:MM)?\s*$', re.IGNORECASE)
# European comma: "1,5" in "X1,5"
_THK_EURO_RE = re.compile(r'[XxX×]\s*(\d+),(\d+)\s*$', re.IGNORECASE)


_THK_DUAL_LAYER_RE = re.compile(
    r'\d+(?:[.,]\d+)?\s*(?:MM\s+)?THK\s*[+&]\s*\d+(?:[.,]\d+)?\s*(?:MM\s+)?THK',
    re.IGNORECASE,
)


def _extract_thickness(desc: str) -> float | None:
    """Extract thickness in mm. Returns None for dual-layer specs like '4.45 THK + 3.2 THK'
    (winding + ring dimensions) so rules.py can apply the correct standard default."""
    if _THK_DUAL_LAYER_RE.search(desc):
        return None

    m = _THK_MM_RE.search(desc)
    if m:
        return float(m.group(1).replace(',', '.'))

    # Thickness stated in inches — convert to mm and return
    m = _THK_INCH_PREFIX_RE.search(desc)
    if m:
        val_in = float(m.group(1).replace(',', '.'))
        mm = val_in * 25.4
        return round(round(mm / 0.5) * 0.5, 1)  # round to nearest 0.5mm (standard SPW thickness)

    m = _THK_PREFIX_RE.search(desc)
    if m:
        return float(m.group(1).replace(',', '.'))

    m = _THK_EURO_RE.search(desc)
    if m:
        return float(f'{m.group(1)}.{m.group(2)}')

    m = _THK_T_RE.search(desc)
    if m:
        return float(m.group(1))

    # "x 4.5mm" — bare mm suffix after dimension separator
    m = _THK_BARE_MM_RE.search(desc)
    if m:
        return float(m.group(1))

    m = _THK_LAST_DIM_RE.search(desc)
    if m:
        return float(m.group(1).replace(',', '.'))

    return None


# ---------------------------------------------------------------------------
# Face type, standard, special
# ---------------------------------------------------------------------------

_FACE_RE = re.compile(r'\b(RF|FF)\b|\bRAISED\s+FACE\b|\bFULL\s+FACE\b', re.IGNORECASE)
_SERIES_RE = re.compile(r'\bSERIES[\s\-]?([AB])\b', re.IGNORECASE)
_STANDARD_RE = re.compile(
    r'ASME\s+B16\.\d+(?:\s*\(?\s*SERIES[\s\-]?[AB]\s*\)?)?|'
    r'EN\s+1514[\s\-]\d+|'
    r'API\s+6[AB]\b|'
    r'API\s+6[AB]\b',
    re.IGNORECASE,
)
_SPECIAL_KEYWORDS = re.compile(
    r'\bFOOD\s+GRADE\b|\bNACE(?:\s+MR[\s\-]?01[\s\-]?75)?\b|'
    r'\bLETHAL\b|\bEIL\s+APPROVED\b|\bSERIES\s+[AB]\b|'
    r'\bAS\s+PER\s+DRAWING\b|\bAS\s+PER\s+DRG\b|'
    r'\bE\.?GALV(?:ANIZ(?:ED|ING)|ANIS(?:ED|ING))?\b|'
    r'\bELECTRO[\s\-]?GALVAN(?:IZ|IS)(?:ED|ING)?\b|'
    r'\bEPOXY[\s\-]?COAT(?:ED|ING)?\b|'
    r'\bZINC[\s\-]?COAT(?:ED|ING)?\b|\bGALVAN(?:IZ|IS)(?:ED|ING)\b|'
    r'\bPHOSPHATE[\s\-]?COAT(?:ED|ING)?\b|\bNICKEL[\s\-]?PLAT(?:ED|ING)?\b',
    re.IGNORECASE,
)

# Normalise electro-galvanising variations → GGPL standard abbreviation
_EGALV_RE = re.compile(
    r'\bELECTRO[\s\-]?GALVAN(?:IZ|IS)(?:ED|ING)?\b|\bE\.?GALV(?:ANIZ(?:ED|ING)|ANIS(?:ED|ING))?\b',
    re.IGNORECASE,
)
# Normalise coating/surface-treatment keywords to GGPL standard form
_COATING_NORMS = [
    (re.compile(r'\bEPOXY[\s\-]?COAT(?:ED|ING)?\b', re.IGNORECASE), 'EPOXY COATED'),
    (re.compile(r'\bZINC[\s\-]?COAT(?:ED|ING)?\b', re.IGNORECASE), 'ZINC COATED'),
    (re.compile(r'\bGALVAN(?:IZ|IS)(?:ED|ING)\b', re.IGNORECASE), 'GALVANISED'),
    (re.compile(r'\bPHOSPHATE[\s\-]?COAT(?:ED|ING)?\b', re.IGNORECASE), 'PHOSPHATE COATED'),
    (re.compile(r'\bNICKEL[\s\-]?PLAT(?:ED|ING)?\b', re.IGNORECASE), 'NICKEL PLATED'),
]


def _extract_face_type(desc: str) -> str | None:
    m = _FACE_RE.search(desc)
    if not m:
        return None
    val = m.group(0).upper().strip()
    if 'FULL' in val:
        return 'FF'
    if 'RAISED' in val:
        return 'RF'
    return val  # RF or FF


def _extract_standard(desc: str) -> str | None:
    m = _STANDARD_RE.search(desc)
    if m:
        return m.group(0).strip()
    return None


def _extract_special(desc: str) -> str | None:
    matches = _SPECIAL_KEYWORDS.findall(desc)
    if not matches:
        return None
    normalised = []
    for m in matches:
        token = m.strip()
        if _EGALV_RE.fullmatch(token):
            token = 'E.GALV'
        else:
            for pat, replacement in _COATING_NORMS:
                if pat.fullmatch(token):
                    token = replacement
                    break
        normalised.append(token)
    return ', '.join(normalised)


# ---------------------------------------------------------------------------
# Spiral wound component extraction
# ---------------------------------------------------------------------------

# Filler: "graphite filler" or "PTFE fill" or "graphite filled"
_SW_FILLER_CTX_RE = re.compile(
    r'(\b[\w\s]+?)\s+FILL(?:ER|ED)?\b',
    re.IGNORECASE,
)
# "WITH FLEXIBLE GRAPHITE FILLER" / "W/FLEX INHIB GRAPHITE FILLER" / "W/ GRAPHITE FILLER(98%...)"
# Group 1 = base material, Group 2 = optional parenthetical qualifier after FILLER keyword
_SW_FILLER_WITH_RE = re.compile(
    r'(?:WITH|W/)\s*([\w\s]+?)\s+FILL(?:ER|ED)?\s*(\([^)]+\))?',
    re.IGNORECASE,
)
# Inner ring: "SS316 INNER RING" / "SS316 I/R" / "I/R SS316" / "INNER RING SS316" / "IR SS316"
# Also handles "INNERING RING" (customer typo) and "INNER CENTERING RING" (shared inner+outer ring)
_SW_IR_RE = re.compile(
    r'([\w\s]+?)\s+(?:INNER(?:ING)?\s+RING|I/R|\bIR\b|\bI\s+RING\b)\b'
    r'|\b(?:INNER(?:ING)?\s+RING|I/R|IR|I\s+RING)\s+(SS\s*\d{3}\w?|\d{3}\w?|CS|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|ALLOY\s*\d+|DUPLEX\w*)',
    re.IGNORECASE,
)
# Outer ring: "CS OUTER RING" / "CS O/R" / "CS CENTERING RING" / "CS CR" / "CR CS"
_SW_OR_RE = re.compile(
    r'([\w\s]+?)\s+(?:OUTER\s+RING|O/R|CENTERING(?:\s+RING)?|\bCR\b)\b'
    r'|\b(?:OUTER\s+RING|O/R|CENTERING(?:\s+RING)?|CR)\s+(SS\s*\d{3}\w?|\d{3}\w?|CS|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|ALLOY\s*\d+|DUPLEX\w*)',
    re.IGNORECASE,
)
# Filler brand names that may appear quoted/standalone after FILL keyword
# e.g. "GRAPHITE FILL 'FLEXICARB'" → FLEXIBLE GRAPHITE
_FILLER_BRAND_RE = re.compile(
    r"['\"]?(FLEXICARB|FLEXI[\s\-]CARB|SIGRAFLEX|GRAFOIL|GRAFIL|THERMICULITE|PAPYEX)\b['\"]?",
    re.IGNORECASE,
)

# Structured field-label patterns: "WINDING MATL:316L SS", "FILLER MATL:GRAPHITE",
# "CENTERING RING MATL:316L SS", "INNER(ING) RING MATL:316L SS"
# Stops at the next field label keyword to avoid over-consuming.
_MATL_STOP = r'(?=\s*(?:WINDING|FILLER|CENTERING|INNER(?:ING)?|OUTER|STYLE|SPEC|CLASS|THCK?|SIZE|\Z))'
_SW_WINDING_MATL_RE = re.compile(
    r'\bWINDING\s+MATL\s*[:\-]\s*([\w]+(?:\s+[\w]+)?)', re.IGNORECASE
)
_SW_FILLER_MATL_RE = re.compile(
    r'\bFILLER\s+MATL\s*[:\-]\s*([\w]+(?:\s+[\w]+)?)', re.IGNORECASE
)
_SW_CR_MATL_RE = re.compile(
    r'\bCENTERING\s+RING\s+MATL\s*[:\-]\s*([\w]+(?:\s+[\w]+)?)', re.IGNORECASE
)
_SW_IR_MATL_RE = re.compile(
    r'\bINNER(?:ING)?\s+RING\s+MATL\s*[:\-]\s*([\w]+(?:\s+[\w]+)?)', re.IGNORECASE
)
# Colon-only label notation (catalog style without MATL keyword):
# "Filler: graphite" / "Filler: graphite or PTFE" (takes first option before OR)
_SW_FILLER_LABEL_RE = re.compile(
    r'\bFILLER\s*:\s*([\w\s]+?)(?:\s+OR\s+[\w\s]+)?(?=\s*(?:,|\Z|\bWINDING\b|\bINNER\b|\bOUTER\b))',
    re.IGNORECASE,
)
# "winding: AISI 304" / "winding material: 316L"
_SW_WINDING_LABEL_RE = re.compile(
    r'\bWINDING(?:\s+(?:MATL|MATERIAL))?\s*:\s*([\w\s]+?)(?=\s*(?:,|\Z|\bFILLER\b|\bINNER\b|\bOUTER\b))',
    re.IGNORECASE,
)
# "Inner Ring: zinc-plated carbon steel" — allows hyphens within material words
_SW_IR_LABEL_RE = re.compile(
    r'\bINNER(?:ING)?\s+RING\s*:\s*([\w][\w\-]*(?:\s+[\w][\w\-]*){0,3}?)(?=\s*(?:,|\Z|\bOUTER\b|\bFILLER\b|\bWINDING\b))',
    re.IGNORECASE,
)

# "CR/IR <material>" — shared material for both centering ring (outer) and inner ring
_SW_CR_IR_RE = re.compile(
    r'\bCR\s*/\s*IR\s+(SS\s*\d{3}\w?|\d{3}\w?|CS|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|ALLOY\s*\d+|DUPLEX\w*)',
    re.IGNORECASE,
)
# Keyword-before-material outer ring: "OUTER RING CARBON STEEL" / "O/R CS"
# Captures 1–3 word material after keyword (handles CARBON STEEL, SOFT IRON, etc.)
_SW_OR_AFTER_RE = re.compile(
    r'\b(?:OUTER\s+RING|O/R|CENTERING(?:\s+RING)?|CR)\s+([\w]+(?:\s+[\w]+){0,2}?)(?=\s*(?:[,()\[\n]|$))',
    re.IGNORECASE,
)
# Words that indicate a coating/treatment, NOT a ring material
_NON_RING_MATERIAL_RE = re.compile(
    r'\b(GALVANI[SZ]\w*|ELECTRO|EPOXY|PHOSPHATE|COAT(?:ED|ING)?|PLAT(?:ED|ING)?|TREATED|PAINTED)\b',
    re.IGNORECASE,
)
# Keyword-before-material inner ring: "INNER RING SS304" / "I/R SS316" / "IR 316L" / "INNERING RING SS316L"
_SW_IR_AFTER_RE = re.compile(
    r'\b(?:INNER(?:ING)?\s+RING|I/R|IR|I\s+RING)\s+([\w]+(?:\s+[\w]+){0,2}?)(?=\s*(?:[,()\[\n&+]|$|\b(?:OUTER|O/R|CENTERING)\b))',
    re.IGNORECASE,
)
# Winding material: SS316/SS304/etc before "SPIRAL WOUND" or standalone
# Allow optional comma between material and SPIRAL keyword (e.g. "UNS N06625, Spiral wound")
_SW_WINDING_BEFORE_RE = re.compile(
    r'[,\s](SS\s*\d{3}\w?|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|ALLOY\s*\d+|'
    r'HASTELLOY\s*\w?\d{3}|MONEL\s*\d{3}|DUPLEX|SUPER\s*DUPLEX|'
    r'UNS\s*[SNR]\d+|TITANIUM\s*GR\.?\d+)[,\s]+'
    r'(?:SPIRAL|SPRL|SPW)',
    re.IGNORECASE,
)
# Winding material after "WINDING" keyword
_SW_WINDING_AFTER_RE = re.compile(
    r'WINDING\s+(?:MATERIAL[\s:]*)?'
    r'(SS\s*\d{3}\w?|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|ALLOY\s*\d+|'
    r'HASTELLOY\s*\w?\d{3}|MONEL\s*\d{3})',
    re.IGNORECASE,
)
# Compact "316L/GRAPH" or "SS316L/GRAPHITE" — grade slash filler (no space around /)
_SW_GRADE_SLASH_FILLER_RE = re.compile(
    r'\b(SS\s*\d{3}\w?|\d{3}\w?)\s*/\s*(GRAPH\w*|PTFE|TEFLON|FG|FLEXIBLE\s+GRAPHITE|MICA|CERAMIC|VERMICULITE)',
    re.IGNORECASE,
)
# Compact "INOUT=316L/CS" — inner/outer ring in one token
_SW_INOUT_RE = re.compile(
    r'\bINOUT\s*=\s*(\w+)\s*/\s*(\w+)',
    re.IGNORECASE,
)


def _norm_ring_material(raw: str | None) -> str | None:
    """Normalize a ring/winding material string through _SW_RING_ALIASES."""
    if not raw:
        return None
    key = raw.strip().upper()
    # Clean up common prefixes
    key = re.sub(r'^(?:AND|WITH|W/)(?:\s+|$)', '', key).strip()
    key = re.sub(r'\s+', ' ', key)
    return _SW_RING_ALIASES.get(key, key if len(key) > 1 else None)


def _norm_filler_material(raw: str | None) -> str | None:
    """Normalize filler material through _SW_FILLER_ALIASES."""
    if not raw:
        return None
    key = raw.strip().upper()
    key = re.sub(r'^(?:AND|WITH|W/)(?:\s+|$)', '', key).strip()
    key = re.sub(r'\s+', ' ', key)
    return _SW_FILLER_ALIASES.get(key, key if len(key) > 1 else None)


def _extract_sw_fields(desc: str) -> dict:
    """Extract spiral wound component fields."""
    result = {
        'sw_winding_material': None,
        'sw_filler': None,
        'sw_inner_ring': None,
        'sw_outer_ring': None,
    }
    upper = desc.upper()

    # Normalize compact "CSCentering" / "SS316Centering" (material glued to CENTERING keyword)
    upper = re.sub(r'\b([A-Z0-9]{2,6})(CENTERING)\b', r'\1 \2', upper)

    # --- Structured field labels (highest priority) ---
    # "WINDING MATL:316L SS", "FILLER MATL:GRAPHITE", "CENTERING RING MATL:316L SS", etc.
    m = _SW_WINDING_MATL_RE.search(upper)
    if m:
        result['sw_winding_material'] = _norm_ring_material(m.group(1).strip())
    m = _SW_FILLER_MATL_RE.search(upper)
    if m:
        # Only set from MATL label if a more-specific filler hasn't been found yet
        result['_filler_matl_label'] = _norm_filler_material(m.group(1).strip())
    m = _SW_CR_MATL_RE.search(upper)
    if m:
        result['sw_outer_ring'] = _norm_ring_material(m.group(1).strip())
    m = _SW_IR_MATL_RE.search(upper)
    if m:
        result['sw_inner_ring'] = _norm_ring_material(m.group(1).strip())

    # --- Colon-only label notation (catalog/datasheet style): "winding: AISI 304", "Filler: graphite" ---
    if not result['sw_winding_material']:
        m = _SW_WINDING_LABEL_RE.search(upper)
        if m:
            result['sw_winding_material'] = _norm_ring_material(m.group(1).strip())
    if not result.get('_filler_matl_label'):
        m = _SW_FILLER_LABEL_RE.search(upper)
        if m:
            result['_filler_matl_label'] = _norm_filler_material(m.group(1).strip())
    if not result['sw_inner_ring']:
        m = _SW_IR_LABEL_RE.search(upper)
        if m:
            raw = m.group(1).strip()
            result['sw_inner_ring'] = _norm_ring_material(raw)

    # Compact "316L/GRAPH" or "SS316L/GRAPHITE" — grade/filler slash notation
    gsf = _SW_GRADE_SLASH_FILLER_RE.search(upper)
    if gsf:
        result['sw_winding_material'] = _norm_ring_material(gsf.group(1))
        result['sw_filler'] = _norm_filler_material(gsf.group(2))

    # Compact "INOUT=316L/CS" — inner ring / outer ring
    inout = _SW_INOUT_RE.search(upper)
    if inout:
        result['sw_inner_ring'] = _norm_ring_material(inout.group(1))
        result['sw_outer_ring'] = _norm_ring_material(inout.group(2))

    # "CR/IR 316L" — centering ring (outer) and inner ring share one material
    cr_ir = _SW_CR_IR_RE.search(upper)
    if cr_ir:
        mat = _norm_ring_material(cr_ir.group(1))
        result['sw_inner_ring'] = result['sw_inner_ring'] or mat
        result['sw_outer_ring'] = result['sw_outer_ring'] or mat

    # Winding material: look for material before "SPIRAL WOUND"
    if not result['sw_winding_material']:
        m = _SW_WINDING_BEFORE_RE.search(upper)
        if m:
            result['sw_winding_material'] = _norm_ring_material(m.group(1))
        else:
            m = _SW_WINDING_AFTER_RE.search(upper)
            if m:
                result['sw_winding_material'] = _norm_ring_material(m.group(1))
            else:
                # Try first SS/alloy/UNS mention as winding material
                m = re.search(
                    r'\b(SS\s*\d{3}\w?|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|'
                    r'ALLOY\s*\d+|HASTELLOY\s*\w?\d{3}|MONEL\s*\d{3}|'
                    r'UNS\s*[SNR]\d+|TITANIUM\s*GR\.?\d+|'
                    r'DUPLEX\s*SS?\d*|SUPER\s*DUPLEX)',
                    upper,
                )
                if m:
                    result['sw_winding_material'] = _norm_ring_material(m.group(1))

    # Filler
    if not result['sw_filler']:
        m = _SW_FILLER_WITH_RE.search(upper)
        if m:
            filler_raw = m.group(1).strip()
            paren = (m.group(2) or '').strip()  # e.g. "(98% PURE GRAPHITE)"
            # Normalize the base material name, then re-attach any parenthetical
            base = _norm_filler_material(filler_raw)
            result['sw_filler'] = (f'{base} {paren}'.strip()) if (base and paren) else base
        else:
            m = _SW_FILLER_CTX_RE.search(upper)
            if m:
                result['sw_filler'] = _norm_filler_material(m.group(1).strip().split()[-1])
            else:
                # Common standalone: "GRAPHITE" in SW context
                if 'GRAPHITE' in upper:
                    result['sw_filler'] = 'GRAPHITE'
                elif 'PTFE' in upper or 'TEFLON' in upper:
                    result['sw_filler'] = 'PTFE'

    # Override with specific filler brand name if present (e.g. 'FLEXICARB' → FLEXIBLE GRAPHITE)
    bm = _FILLER_BRAND_RE.search(desc)
    if bm:
        brand_resolved = _norm_filler_material(bm.group(1).replace('-', ' ').upper())
        if brand_resolved:
            result['sw_filler'] = brand_resolved

    # Reconcile MATL-label filler vs free-text filler: more specific type wins
    # e.g. "FILLER MATL:GRAPHITE" + "W/FLEX INHIB GRAPHITE FILLER" → FLEXIBLE INHIBITED GRAPHITE
    label_filler = result.pop('_filler_matl_label', None)
    if not result['sw_filler'] and label_filler:
        result['sw_filler'] = label_filler
    elif label_filler and result['sw_filler']:
        # Prefer the more descriptive: FLEXIBLE INHIBITED > FLEXIBLE GRAPHITE > GRAPHITE
        _FILLER_RANK = {'FLEXIBLE INHIBITED GRAPHITE': 3, 'FLEXIBLE GRAPHITE': 2, 'GRAPHITE': 1}
        if _FILLER_RANK.get(label_filler, 0) > _FILLER_RANK.get(result['sw_filler'], 0):
            result['sw_filler'] = label_filler

    # Inner ring (only if not already set by INOUT= / CR-IR pattern)
    if not result['sw_inner_ring']:
        # Try keyword-before-material first ("INNER RING SS304", "I/R 316L")
        m = _SW_IR_AFTER_RE.search(upper)
        if m:
            mat = _norm_ring_material(m.group(1).strip().split()[0])  # first token only
            result['sw_inner_ring'] = mat
        if not result['sw_inner_ring']:
            # Fall back to material-before-keyword ("SS304 INNER RING")
            m = _SW_IR_RE.search(upper)
            if m:
                raw = (m.group(1) or m.group(2) or '').strip()
                mat = _norm_ring_material(raw.split()[-1] if raw else None)
                result['sw_inner_ring'] = mat

    # Outer ring (only if not already set by INOUT= / CR-IR pattern)
    if not result['sw_outer_ring']:
        # Try keyword-before-material first ("OUTER RING CARBON STEEL", "O/R CS")
        m = _SW_OR_AFTER_RE.search(upper)
        if m:
            raw = m.group(1).strip()
            # Skip if captured text is a coating/treatment word or the bare word RING
            # (RING can be captured when CENTERING matches without its RING suffix)
            if raw.upper() != 'RING' and not _NON_RING_MATERIAL_RE.search(raw):
                mat = _norm_ring_material(raw) or _norm_ring_material(raw.split()[-1])
                result['sw_outer_ring'] = mat
        if not result['sw_outer_ring']:
            # Fall back to material-before-keyword ("CS OUTER RING")
            m = _SW_OR_RE.search(upper)
            if m:
                raw = (m.group(1) or '').strip()
                mat = _norm_ring_material(raw.split()[-1] if raw else None)
                result['sw_outer_ring'] = mat

    # "inner & outer ring" with shared material: "SS316 inner & outer ring"
    # Also handles reversed order: "316 outer & inner ring"
    _RING_MAT_PAT = (
        r'(SS\s*\d{3}\w?|\b\d{3}\w{0,2}\b|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|CS|'
        r'ALLOY\s*\d+|DUPLEX\s*SS?\d*)'
    )
    shared_re = re.search(
        _RING_MAT_PAT + r'\s+(?:INNER\s*[&+]\s*OUTER|OUTER\s*[&+]\s*INNER)\s+RING',
        upper,
    )
    if shared_re:
        mat = _norm_ring_material(shared_re.group(1))
        if mat:
            result['sw_inner_ring'] = result['sw_inner_ring'] or mat
            result['sw_outer_ring'] = result['sw_outer_ring'] or mat

    # "SS INNER AND CS OUTER RINGS" pattern
    mixed_re = re.search(
        r'(SS\s*\d{0,4}\w?|CS|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|ALLOY\s*\d+)\s+INNER\s+'
        r'AND\s+(SS\s*\d{0,4}\w?|CS|INCOLOY\s*\d{3}|INCONEL\s*\d{3}|ALLOY\s*\d+)\s+OUTER',
        upper,
    )
    if mixed_re:
        ir = _norm_ring_material(mixed_re.group(1))
        ore = _norm_ring_material(mixed_re.group(2))
        if ir:
            result['sw_inner_ring'] = ir
        if ore:
            result['sw_outer_ring'] = ore

    # If winding material found but inner ring says just "SS" with no grade,
    # inherit grade from winding
    wm = result.get('sw_winding_material')
    if wm:
        for field in ('sw_inner_ring', 'sw_outer_ring'):
            if result[field] in ('SS', None):
                pass  # leave as-is, rules.py handles defaults

    return result


# ---------------------------------------------------------------------------
# RTJ field extraction
# ---------------------------------------------------------------------------

_RING_NO_RE = re.compile(r'\b((?:BX|RX|R)[\s\-]?\d+)\b', re.IGNORECASE)
_GROOVE_RE = re.compile(r'\b(OCTAGONAL|OVAL)\b', re.IGNORECASE)
_BHN_RE = re.compile(r'(\d+)\s*BHN\b', re.IGNORECASE)
_HRBW_RE = re.compile(r'(?:HARDNESS\s+)?(\d+)\s*(?:HRBW?|HRB)\b', re.IGNORECASE)
_GALVANISED_RE = re.compile(r'\bGALVANI[SZ]ED\b', re.IGNORECASE)


def _extract_rtj_fields(desc: str) -> dict:
    """Extract RTJ-specific fields."""
    result = {
        'ring_no': None,
        'rtj_groove_type': None,
        'rtj_hardness_bhn': None,
        'moc': None,
    }
    upper = desc.upper()

    # Ring number
    m = _RING_NO_RE.search(upper)
    if m:
        raw = m.group(1).upper().replace(' ', '-')
        # Normalize: R24 → R-24, BX156 → BX-156
        if raw[0] == 'R' and raw[1] != '-' and raw[1] != 'X':
            raw = 'R-' + raw[1:]
        elif raw[:2] in ('BX', 'RX') and raw[2] != '-':
            raw = raw[:2] + '-' + raw[2:]
        result['ring_no'] = raw

    # Groove type
    m = _GROOVE_RE.search(upper)
    if m:
        result['rtj_groove_type'] = 'OCT' if 'OCT' in m.group(1).upper() else 'OVAL'

    # BHN
    m = _BHN_RE.search(upper)
    if m:
        result['rtj_hardness_bhn'] = int(m.group(1))
    else:
        m = _HRBW_RE.search(upper)
        if m:
            hrb = int(m.group(1))
            # Common conversions
            if hrb >= 80:
                result['rtj_hardness_bhn'] = 160
            elif hrb >= 65:
                result['rtj_hardness_bhn'] = 120
            else:
                result['rtj_hardness_bhn'] = 90

    # MOC
    result['moc'] = _extract_rtj_moc(desc)
    # Check for galvanised suffix
    if result['moc'] and _GALVANISED_RE.search(upper):
        if 'GALVANISED' not in (result['moc'] or '').upper():
            result['moc'] = result['moc'] + ' GALVANISED'

    return result


# ---------------------------------------------------------------------------
# ISK field extraction
# ---------------------------------------------------------------------------

_ISK_STYLE_RE = re.compile(
    r'\b(STYLE[\s\-]?(?:CS|N|FCS)|TYPE[\s\-]?[ADEFIK]|FCS|VCFS)\b',
    re.IGNORECASE,
)
_ISK_FS_RE = re.compile(
    r'\b(NON[\s\-]?FIRE\s*SAFE|FIRE\s*SAFE|NFS|(?<!\w)FS(?!\w))\b',
    re.IGNORECASE,
)
# GRE grade: "GRE G10", "GRE (G-10)", "GRE G-11", "G10", "G11", "(G-10/11)"
_ISK_GRE_RE = re.compile(
    r'\bGRE\s*\(?\s*G[\s\-]?(\d+(?:/\d+)?)\s*\)?'
    r'|\(G[\s\-]?(\d+(?:/\d+)?)\)'
    r'|\b(?:GRADE\s+)?G(10|11)\b',
    re.IGNORECASE,
)
# Core metal: "WITH SS316 CORE", "SS316L CORE", "CS CORE"
# Also reversed: "316 SS CORE", "304 SS CORE"
_ISK_CORE_RE = re.compile(
    r'(?:WITH\s+)?'
    r'(SS\s*3(?:04|16L?|21)|CS|CARBON\s+STEEL|DUPLEX|SUPER\s+DUPLEX'
    r'|INCONEL\s+\d+|ALLOY\s+\d+|HASTELLOY\s+\w+|UNS\s+\w+)'
    r'\s+CORE\b'
    r'|(?:WITH\s+)?(3(?:04|16L?|21))\s+SS\s+CORE\b',
    re.IGNORECASE,
)
# Sleeve material: "GRE G-11 INSU SLEEVES", "PTFE SLEEVES"
_ISK_SLEEVE_RE = re.compile(
    r'(GRE\s*\(?\s*G[\s\-]?\d+\s*\)?|G10|G11|PTFE)\s+'
    r'(?:INSU(?:LATION|LATING)?\s+)?SLEEVES?',
    re.IGNORECASE,
)
# Washer/bolt material: "CS WASHERS", "SS316 BOLT SLEEVES & WASHERS"
_ISK_WASHER_RE = re.compile(
    r'(CS|SS\s*3(?:04|16L?|21)|CARBON\s+STEEL|STEEL)\s+'
    r'(?:BOLT\s+)?(?:SLEEVES?\s+(?:&|AND)\s+)?WASHERS?',
    re.IGNORECASE,
)


def _normalise_gre(m_gre) -> str | None:
    """Return normalised GRE string from a _ISK_GRE_RE match.
    Handles: 'GRE G10', 'GRE (G-10/11)', '(G-10/11)', standalone 'G10/G11'."""
    if m_gre is None:
        return None
    # group(1) = grade after "GRE G..." , group(2) = grade in (G-XX) , group(3) = standalone G10/G11
    grade = m_gre.group(1) or m_gre.group(2) or m_gre.group(3)
    if not grade:
        return None
    # Normalise range "10/11" → "G-10/11"; single "10" or "11" → "GRE G10/G11"
    if '/' in grade:
        # Range like "10/11" or "G-10/11" — produce "GRE G-10/11"
        base = grade.lstrip('G- ')
        return f'GRE G-{base}'
    return f'GRE G{grade}'


def _extract_isk_fields(desc: str) -> dict:
    """Extract ISK/ISK_RTJ fields: style, fire safety, gasket material,
    core material, sleeve material, washer material."""
    result = {
        'isk_style': None,
        'isk_fire_safety': None,
        'isk_gasket_material': None,
        'isk_core_material': None,
        'isk_sleeve_material': None,
        'isk_washer_material': None,
    }
    upper = desc.upper()

    # Style (STYLE-CS, STYLE-N, TYPE-A, TYPE-E, TYPE-F, FCS/VCFS …)
    m = _ISK_STYLE_RE.search(upper)
    if m:
        raw = m.group(1).upper().replace(' ', '-').replace('--', '-')
        if 'VCFS' in raw or 'FCS' in raw:
            raw = 'FCS'
        # TYPE-A is the customer term for GGPL's STYLE-CS
        elif raw in ('TYPE-A', 'TYPE A'):
            raw = 'STYLE-CS'
        result['isk_style'] = raw

    # Fire safety
    m = _ISK_FS_RE.search(upper)
    if m:
        raw = m.group(1).upper()
        result['isk_fire_safety'] = 'NON FIRE SAFE' if ('NON' in raw or raw == 'NFS') else 'FIRE SAFE'

    # Gasket/insulation ring material (GRE > PEEK > PTFE in priority)
    m_gre = _ISK_GRE_RE.search(desc)
    if m_gre:
        result['isk_gasket_material'] = _normalise_gre(m_gre)
    elif re.search(r'\bPEEK\b', desc, re.IGNORECASE):
        result['isk_gasket_material'] = 'PEEK'
    elif re.search(r'\bPTFE\b', desc, re.IGNORECASE) and 'SEAL' not in upper and 'SPRING' not in upper:
        # Don't capture PTFE as gasket material if it's part of a spring/seal component
        result['isk_gasket_material'] = 'PTFE'

    # Core material — group(1) = "SS316 CORE" style, group(2) = "316 SS CORE" reversed style
    m = _ISK_CORE_RE.search(desc)
    if m:
        if m.group(1):
            raw = re.sub(r'\s+', '', m.group(1).strip().upper())
        else:
            # Reversed: "316 SS CORE" → normalise to "SS316"
            raw = 'SS' + m.group(2).strip().upper()
        result['isk_core_material'] = raw

    # Sleeve material
    m = _ISK_SLEEVE_RE.search(desc)
    if m:
        raw = m.group(1).strip().upper()
        # Check if it references a GRE grade
        m_gre2 = _ISK_GRE_RE.match(raw)
        if m_gre2:
            result['isk_sleeve_material'] = _normalise_gre(m_gre2)
        elif raw in ('G10', 'G11'):
            result['isk_sleeve_material'] = f'GRE {raw}'
        else:
            result['isk_sleeve_material'] = raw

    # Washer material
    m = _ISK_WASHER_RE.search(desc)
    if m:
        raw = m.group(1).strip().upper()
        result['isk_washer_material'] = re.sub(r'\s+', '', raw) if raw.startswith('SS') else raw

    return result


# ---------------------------------------------------------------------------
# DJI field extraction
# ---------------------------------------------------------------------------

_DJI_FILLER_RE = re.compile(
    r'\b(?:AND|WITH)\s+(GRAPHITE|ASBESTOS\s+FREE|CERAMIC)\b',
    re.IGNORECASE,
)
_DJI_JACKET_RE = re.compile(
    r'\b(COPPER|SS\s*316L?|SOFT\s+IRON|ARMCO\s+IRON)\b',
    re.IGNORECASE,
)


def _extract_dji_fields(desc: str) -> dict:
    """Extract DJI-specific fields."""
    result = {'dji_filler': None, 'moc': None}
    upper = desc.upper()

    m = _DJI_FILLER_RE.search(upper)
    if m:
        result['dji_filler'] = m.group(1).strip()

    m = _DJI_JACKET_RE.search(upper)
    if m:
        raw = m.group(1).strip()
        result['moc'] = _SW_RING_ALIASES.get(raw, raw)

    # Check for drawing reference
    if re.search(r'\bDRAWING\b|\bDRG\b', upper):
        result['dji_filler'] = result.get('dji_filler') or None

    return result


# ---------------------------------------------------------------------------
# DJI thickness from bare dims: "101X110 X1,5" → thk=1.5
# ---------------------------------------------------------------------------

def _extract_dji_thickness(desc: str) -> float | None:
    """Extract thickness from DJI bare dimension pattern."""
    m = _BARE_DIMS_RE.search(desc)
    if m:
        thk_raw = m.group(3).replace(',', '.')
        return float(thk_raw)
    return None


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

_CRITICAL_FIELDS = {
    'SOFT_CUT': ['size', 'rating', 'moc'],
    'SPIRAL_WOUND': ['size', 'rating', 'sw_winding_material'],
    'RTJ': ['size', 'rating', 'moc'],
    'KAMM': ['size', 'rating'],
    'DJI': ['od_mm', 'id_mm', 'moc'],
    'ISK': ['size', 'rating'],
    'ISK_RTJ': ['size', 'rating'],
}


def _score_confidence(extracted: dict, gasket_type: str) -> str:
    """Score extraction confidence based on how many critical fields were found."""
    critical = _CRITICAL_FIELDS.get(gasket_type, ['size', 'rating', 'moc'])
    found = 0
    for f in critical:
        val = extracted.get(f)
        if val is not None:
            found += 1
    total = len(critical)

    if found == total:
        return 'HIGH'
    elif found >= total - 1:
        return 'MEDIUM'
    return 'LOW'


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def regex_extract(description: str) -> dict:
    """
    Extract all structured gasket fields from a raw description using regex.

    Returns a dict with the same 22 keys as extractor._null_extract():
        size, size_type, od_mm, id_mm, rating, gasket_type, moc, face_type,
        thickness_mm, standard, special, isk_style, isk_fire_safety, dji_filler,
        sw_winding_material, sw_filler, sw_inner_ring, sw_outer_ring,
        rtj_groove_type, rtj_hardness_bhn, ring_no, confidence

    Non-detected fields are None. confidence is 'HIGH', 'MEDIUM', or 'LOW'.
    """
    desc = description.strip()
    upper = desc.upper()

    # Initialize all fields to None
    result = {
        'size': None, 'size_type': 'UNKNOWN', 'od_mm': None, 'id_mm': None,
        'rating': None, 'gasket_type': 'SOFT_CUT', 'moc': None,
        'face_type': None, 'thickness_mm': None, 'standard': None,
        'special': None,
        'isk_style': None, 'isk_fire_safety': None,
        'isk_gasket_material': None, 'isk_core_material': None,
        'isk_sleeve_material': None, 'isk_washer_material': None,
        'dji_filler': None,
        'kamm_core_material': None, 'kamm_surface_material': None,
        'sw_winding_material': None, 'sw_filler': None,
        'sw_inner_ring': None, 'sw_outer_ring': None,
        'rtj_groove_type': None, 'rtj_hardness_bhn': None,
        'ring_no': None, 'series': None, 'confidence': 'LOW',
    }

    # 1. Gasket type
    gasket_type = _detect_type(desc)
    result['gasket_type'] = gasket_type

    # 2. Size
    size_info = _extract_size(desc, gasket_type)
    result.update(size_info)

    # 3. Rating
    result['rating'] = _extract_rating(desc)

    # 4. Thickness
    if gasket_type == 'DJI':
        result['thickness_mm'] = _extract_dji_thickness(desc) or _extract_thickness(desc)
    elif gasket_type != 'RTJ':  # RTJ has no thickness
        result['thickness_mm'] = _extract_thickness(desc)

    # 5. Face type (only for SOFT_CUT, ISK, ISK_RTJ)
    if gasket_type in ('SOFT_CUT', 'ISK', 'ISK_RTJ'):
        result['face_type'] = _extract_face_type(desc)

    # 6. Standard
    result['standard'] = _extract_standard(desc)

    # 7. Special requirements
    result['special'] = _extract_special(desc)

    # 7b. Series A/B (standalone — also captured inside standard string by _STANDARD_RE)
    m = _SERIES_RE.search(upper)
    if m:
        result['series'] = m.group(1).upper()

    # 8. Type-specific extraction
    if gasket_type == 'SPIRAL_WOUND':
        sw = _extract_sw_fields(desc)
        result.update(sw)
        result['moc'] = None  # SW uses component fields, not moc

    elif gasket_type == 'RTJ':
        rtj = _extract_rtj_fields(desc)
        result.update(rtj)

    elif gasket_type in ('ISK', 'ISK_RTJ'):
        isk = _extract_isk_fields(desc)
        result.update(isk)

    elif gasket_type == 'DJI':
        dji = _extract_dji_fields(desc)
        # Only update fields that DJI extractor found
        if dji.get('moc'):
            result['moc'] = dji['moc']
        if dji.get('dji_filler'):
            result['dji_filler'] = dji['dji_filler']

    elif gasket_type == 'KAMM':
        # Extract KAMM core (metal) and surface (graphite/PTFE) materials
        sw = _extract_sw_fields(desc)
        if sw.get('sw_winding_material'):
            result['kamm_core_material'] = sw['sw_winding_material']
        if sw.get('sw_filler'):
            result['kamm_surface_material'] = sw['sw_filler']
        if not result['kamm_core_material']:
            result['kamm_core_material'] = _extract_softcut_moc(desc)
        result['moc'] = result['kamm_core_material']  # keep moc populated for rules.py

    else:
        # SOFT_CUT
        result['moc'] = _extract_softcut_moc(desc)

    # 9. Confidence scoring
    result['confidence'] = _score_confidence(result, gasket_type)

    return result
