"""
Unit conversion tool for gasket-related measurements.
Supports natural-language queries like "4 inches to mm" or "DN 100 to NPS".
Returns plain-text answers — no API needed.
"""
from __future__ import annotations
import re
import math

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

# DN (mm) → NPS display string
_DN_NPS: dict[int, str] = {
    6: '1/8"',   8: '1/4"',   10: '3/8"',  15: '1/2"',  20: '3/4"',
    25: '1"',    32: '1-1/4"', 40: '1-1/2"', 50: '2"',   65: '2-1/2"',
    80: '3"',    90: '3-1/2"', 100: '4"',   125: '5"',   150: '6"',
    200: '8"',   250: '10"',   300: '12"',  350: '14"',  400: '16"',
    450: '18"',  500: '20"',   550: '22"',  600: '24"',  650: '26"',
    700: '28"',  750: '30"',   800: '32"',  850: '34"',  900: '36"',
    1000: '40"', 1050: '42"',  1200: '48"',
}

# NPS decimal value → DN (mm)
_NPS_DN: dict[float, int] = {
    0.125: 6,   0.25: 8,    0.375: 10,  0.5: 15,   0.75: 20,
    1.0: 25,    1.25: 32,   1.5: 40,    2.0: 50,   2.5: 65,
    3.0: 80,    3.5: 90,    4.0: 100,   5.0: 125,  6.0: 150,
    8.0: 200,   10.0: 250,  12.0: 300,  14.0: 350, 16.0: 400,
    18.0: 450,  20.0: 500,  22.0: 550,  24.0: 600, 26.0: 650,
    28.0: 700,  30.0: 750,  32.0: 800,  34.0: 850, 36.0: 900,
    40.0: 1000, 42.0: 1050, 48.0: 1200,
}

# ASME Class ↔ approximate PN equivalents
_CLASS_PN: dict[int, int] = {
    150: 20, 300: 50, 600: 100, 900: 150, 1500: 250, 2500: 420,
}
_PN_CLASS: dict[int, int] = {v: k for k, v in _CLASS_PN.items()}

# NPS fractional strings → decimal
_FRAC_MAP: dict[str, float] = {
    '1/8': 0.125, '1/4': 0.25, '3/8': 0.375, '1/2': 0.5, '3/4': 0.75,
    '1-1/4': 1.25, '1-1/2': 1.5, '2-1/2': 2.5, '3-1/2': 3.5,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v: float) -> str:
    """Format float: drop trailing zeros."""
    return f'{v:.4f}'.rstrip('0').rstrip('.')


def _parse_nps(s: str) -> float | None:
    """Parse NPS value from string like '1/2', '1-1/2', '6', '6.0'."""
    s = s.strip().strip('"\'')
    if s in _FRAC_MAP:
        return _FRAC_MAP[s]
    for frac, val in _FRAC_MAP.items():
        if s == frac:
            return val
    try:
        return float(s)
    except ValueError:
        return None


def _nearest_dn(dn_val: float) -> int | None:
    """Find nearest DN from lookup to handle float input."""
    candidates = list(_DN_NPS.keys())
    nearest = min(candidates, key=lambda x: abs(x - dn_val))
    return nearest if abs(nearest - dn_val) <= 5 else None


def _nearest_nps(nps_val: float) -> float | None:
    """Find nearest NPS from lookup."""
    candidates = list(_NPS_DN.keys())
    nearest = min(candidates, key=lambda x: abs(x - nps_val))
    return nearest if abs(nearest - nps_val) < 0.01 else None


# ---------------------------------------------------------------------------
# Conversion patterns  (checked in order, first match wins)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern, callable]] = []


def _reg(pattern: str):
    """Decorator to register a conversion handler."""
    def decorator(fn):
        _PATTERNS.append((re.compile(pattern, re.IGNORECASE), fn))
        return fn
    return decorator


# --- inches ↔ mm ---

@_reg(r'([\d.,]+)\s*(?:inch(?:es)?|in\b|")\s*(?:to|in|=|->|→)\s*mm')
def _in_to_mm(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)}" = **{_fmt(val * 25.4)} mm**'


@_reg(r'([\d.,]+)\s*mm\s*(?:to|in|=|->|→)\s*(?:inch(?:es)?|in\b|")')
def _mm_to_in(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} mm = **{_fmt(val / 25.4)}"**'


# --- DN ↔ NPS ---

@_reg(r'DN\s*([\d]+)\s*(?:to|in|=|->|→)\s*(?:NPS|NB|inch(?:es)?|")')
def _dn_to_nps(m):
    dn = int(m.group(1))
    nearest = _nearest_dn(dn)
    if nearest is None:
        return f'DN {dn} not found in standard DN/NPS table.'
    nps = _DN_NPS[nearest]
    note = f' (nearest standard DN is {nearest})' if nearest != dn else ''
    return f'DN {dn}{note} = **NPS {nps}**'


@_reg(r'(?:NPS|NB)\s*([\d\-/.,]+)\s*(?:to|in|=|->|→)\s*DN')
def _nps_to_dn(m):
    raw = m.group(1).strip()
    nps_val = _parse_nps(raw)
    if nps_val is None:
        return f'Could not parse NPS value "{raw}".'
    nearest = _nearest_nps(nps_val)
    if nearest is None:
        return f'NPS {raw}" not found in standard DN/NPS table.'
    dn = _NPS_DN[nearest]
    return f'NPS {raw}" = **DN {dn}**'


@_reg(r'([\d\-/.,]+)\s*(?:NPS|NB)\s*(?:to|in|=|->|→)\s*DN')
def _nps_to_dn_suffix(m):
    raw = m.group(1).strip()
    nps_val = _parse_nps(raw)
    if nps_val is None:
        return f'Could not parse NPS value "{raw}".'
    nearest = _nearest_nps(nps_val)
    if nearest is None:
        return f'NPS {raw}" not found in standard DN/NPS table.'
    dn = _NPS_DN[nearest]
    return f'NPS {raw}" = **DN {dn}**'


# --- Standalone DN lookup ---

@_reg(r'(?:what\s+is\s+)?DN\s*([\d]+)(?:\s*(?:NPS|NB|size|equivalent))?$')
def _dn_lookup(m):
    dn = int(m.group(1))
    nearest = _nearest_dn(dn)
    if nearest is None:
        return f'DN {dn} not found in standard table.'
    nps = _DN_NPS[nearest]
    note = f' (nearest standard: DN {nearest})' if nearest != dn else ''
    return f'DN {dn}{note} → **NPS {nps}** (NB {nearest})'


@_reg(r'(?:what\s+is\s+)?(?:NPS|NB)\s*([\d\-/.,]+)(?:\s*(?:DN|size|equivalent))?$')
def _nps_lookup(m):
    raw = m.group(1).strip()
    nps_val = _parse_nps(raw)
    if nps_val is None:
        return f'Could not parse NPS "{raw}".'
    nearest = _nearest_nps(nps_val)
    if nearest is None:
        return f'NPS {raw}" not in standard table.'
    dn = _NPS_DN[nearest]
    return f'NPS {raw}" → **DN {dn}** (NB {dn})'


# --- Pressure: bar ↔ psi ↔ MPa ---

@_reg(r'([\d.,]+)\s*(?:psi|PSI)\s*(?:to|in|=|->|→)\s*(?:bar|BAR)')
def _psi_to_bar(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} psi = **{_fmt(val * 0.0689476)} bar**'


@_reg(r'([\d.,]+)\s*(?:bar|BAR)\s*(?:to|in|=|->|→)\s*(?:psi|PSI)')
def _bar_to_psi(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} bar = **{_fmt(val * 14.5038)} psi**'


@_reg(r'([\d.,]+)\s*(?:psi|PSI)\s*(?:to|in|=|->|→)\s*(?:mpa|MPa)')
def _psi_to_mpa(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} psi = **{_fmt(val * 0.00689476)} MPa**'


@_reg(r'([\d.,]+)\s*(?:mpa|MPa)\s*(?:to|in|=|->|→)\s*(?:psi|PSI)')
def _mpa_to_psi(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} MPa = **{_fmt(val / 0.00689476)} psi**'


@_reg(r'([\d.,]+)\s*(?:bar|BAR)\s*(?:to|in|=|->|→)\s*(?:mpa|MPa)')
def _bar_to_mpa(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} bar = **{_fmt(val * 0.1)} MPa**'


@_reg(r'([\d.,]+)\s*(?:mpa|MPa)\s*(?:to|in|=|->|→)\s*(?:bar|BAR)')
def _mpa_to_bar(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} MPa = **{_fmt(val * 10)} bar**'


@_reg(r'([\d.,]+)\s*(?:kpa|KPa|kPa)\s*(?:to|in|=|->|→)\s*(?:psi|PSI)')
def _kpa_to_psi(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} kPa = **{_fmt(val * 0.145038)} psi**'


@_reg(r'([\d.,]+)\s*(?:psi|PSI)\s*(?:to|in|=|->|→)\s*(?:kpa|KPa|kPa)')
def _psi_to_kpa(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} psi = **{_fmt(val / 0.145038)} kPa**'


# --- ASME Class ↔ PN ---

@_reg(r'(?:class|cl\.?|asme)\s*(150|300|600|900|1500|2500)\s*(?:to|in|=|->|→)\s*PN')
def _class_to_pn(m):
    cls = int(m.group(1))
    pn = _CLASS_PN.get(cls)
    if pn is None:
        return f'Class {cls} not in standard mapping.'
    return f'ASME Class {cls} ≈ **PN {pn}** (approximate — exact value depends on material group & temperature)'


@_reg(r'PN\s*(20|50|100|150|250|420)\s*(?:to|in|=|->|→)\s*(?:class|asme|cl\.?)')
def _pn_to_class(m):
    pn = int(m.group(1))
    cls = _PN_CLASS.get(pn)
    if cls is None:
        return f'PN {pn} not in standard mapping.'
    return f'PN {pn} ≈ **ASME Class {cls}** (approximate)'


# --- Temperature: °C ↔ °F ↔ K ---

@_reg(r'([\-\d.,]+)\s*(?:°?c|celsius|degc)\s*(?:to|in|=|->|→)\s*(?:°?f|fahrenheit|degf)')
def _c_to_f(m):
    val = float(m.group(1).replace(',', '.'))
    f = val * 9 / 5 + 32
    return f'{_fmt(val)} °C = **{_fmt(f)} °F**'


@_reg(r'([\-\d.,]+)\s*(?:°?f|fahrenheit|degf)\s*(?:to|in|=|->|→)\s*(?:°?c|celsius|degc)')
def _f_to_c(m):
    val = float(m.group(1).replace(',', '.'))
    c = (val - 32) * 5 / 9
    return f'{_fmt(val)} °F = **{_fmt(c)} °C**'


@_reg(r'([\-\d.,]+)\s*(?:°?c|celsius|degc)\s*(?:to|in|=|->|→)\s*(?:k|kelvin)')
def _c_to_k(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} °C = **{_fmt(val + 273.15)} K**'


@_reg(r'([\-\d.,]+)\s*(?:k|kelvin)\s*(?:to|in|=|->|→)\s*(?:°?c|celsius|degc)')
def _k_to_c(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} K = **{_fmt(val - 273.15)} °C**'


# --- Torque: N·m ↔ ft·lb ↔ in·lb ---

@_reg(r'([\d.,]+)\s*(?:n\.?m|nm|newton.?met(?:re|er)s?)\s*(?:to|in|=|->|→)\s*(?:ft\.?lb|ft-lb|foot.?pound)')
def _nm_to_ftlb(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} N·m = **{_fmt(val * 0.737562)} ft·lb**'


@_reg(r'([\d.,]+)\s*(?:ft\.?lb|ft-lb|foot.?pound)\s*(?:to|in|=|->|→)\s*(?:n\.?m|nm|newton.?met(?:re|er)s?)')
def _ftlb_to_nm(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} ft·lb = **{_fmt(val / 0.737562)} N·m**'


@_reg(r'([\d.,]+)\s*(?:n\.?m|nm)\s*(?:to|in|=|->|→)\s*(?:in\.?lb|in-lb|inch.?pound)')
def _nm_to_inlb(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} N·m = **{_fmt(val * 8.85075)} in·lb**'


@_reg(r'([\d.,]+)\s*(?:in\.?lb|in-lb|inch.?pound)\s*(?:to|in|=|->|→)\s*(?:n\.?m|nm)')
def _inlb_to_nm(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} in·lb = **{_fmt(val / 8.85075)} N·m**'


# --- Force: kN ↔ kgf ↔ lbf ---

@_reg(r'([\d.,]+)\s*kn\s*(?:to|in|=|->|→)\s*kgf')
def _kn_to_kgf(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} kN = **{_fmt(val * 101.972)} kgf**'


@_reg(r'([\d.,]+)\s*kgf\s*(?:to|in|=|->|→)\s*kn')
def _kgf_to_kn(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} kgf = **{_fmt(val / 101.972)} kN**'


@_reg(r'([\d.,]+)\s*(?:lbf|lb\.?f)\s*(?:to|in|=|->|→)\s*(?:n\b|newton)')
def _lbf_to_n(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} lbf = **{_fmt(val * 4.44822)} N**'


@_reg(r'([\d.,]+)\s*(?:n\b|newton)\s*(?:to|in|=|->|→)\s*(?:lbf|lb\.?f)')
def _n_to_lbf(m):
    val = float(m.group(1).replace(',', '.'))
    return f'{_fmt(val)} N = **{_fmt(val / 4.44822)} lbf**'


# --- Gasket stress / seating stress: MPa ↔ psi (same as pressure, alias) ---

# --- DN/NPS full table ---

@_reg(r'(?:show|list|print|display)?\s*(?:dn|nps)\s*(?:table|chart|list|all)')
def _table(m):
    rows = ['| DN (mm) | NPS (inch) |', '|---------|------------|']
    rows += [f'| {dn} | {nps} |' for dn, nps in _DN_NPS.items()]
    return '\n'.join(rows)


# --- Help ---

@_reg(r'^(?:help|commands|what can you do|usage|\?+)$')
def _help(_m):
    return (
        'I can convert:\n'
        '• **Length**: `4 inches to mm`, `150 mm to inches`\n'
        '• **Pipe size**: `DN 100 to NPS`, `NPS 4 to DN`, `6 NPS to DN`\n'
        '• **Pressure**: `100 psi to bar`, `10 bar to MPa`, `6 MPa to psi`\n'
        '• **Rating**: `class 150 to PN`, `PN 100 to class`\n'
        '• **Temperature**: `200 °C to °F`, `-40 F to C`\n'
        '• **Torque**: `100 Nm to ft-lb`, `50 ft-lb to Nm`\n'
        '• **Force**: `10 kN to kgf`, `500 kgf to kN`\n'
        '• **DN/NPS table**: `show DN table`\n'
        '\nType any conversion naturally!'
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def convert(query: str) -> str:
    """
    Parse a natural-language unit conversion query and return the result.
    Returns an error string if no pattern matches.
    """
    q = query.strip()
    for pattern, handler in _PATTERNS:
        m = pattern.search(q)
        if m:
            try:
                return handler(m)
            except (ValueError, ZeroDivisionError) as e:
                return f'Calculation error: {e}'
    return (
        "I didn't understand that. Try something like:\n"
        '`4 inches to mm` · `DN 150 to NPS` · `100 psi to bar` · `class 300 to PN`\n'
        'Type `help` to see all supported conversions.'
    )
