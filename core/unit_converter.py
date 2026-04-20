"""
Unit conversion functions for gasket-related measurements.
All functions take a numeric value and return a float result + display string.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# DN ↔ NPS lookup table
# ---------------------------------------------------------------------------
DN_NPS_TABLE: list[tuple[int, str, float]] = [
    # (DN mm, NPS display, NPS decimal)
    (6,    '1/8"',   0.125), (8,    '1/4"',   0.25),  (10,   '3/8"',   0.375),
    (15,   '1/2"',   0.5),   (20,   '3/4"',   0.75),  (25,   '1"',     1.0),
    (32,   '1-1/4"', 1.25),  (40,   '1-1/2"', 1.5),   (50,   '2"',     2.0),
    (65,   '2-1/2"', 2.5),   (80,   '3"',     3.0),   (90,   '3-1/2"', 3.5),
    (100,  '4"',     4.0),   (125,  '5"',     5.0),   (150,  '6"',     6.0),
    (200,  '8"',     8.0),   (250,  '10"',    10.0),  (300,  '12"',    12.0),
    (350,  '14"',    14.0),  (400,  '16"',    16.0),  (450,  '18"',    18.0),
    (500,  '20"',    20.0),  (550,  '22"',    22.0),  (600,  '24"',    24.0),
    (650,  '26"',    26.0),  (700,  '28"',    28.0),  (750,  '30"',    30.0),
    (800,  '32"',    32.0),  (850,  '34"',    34.0),  (900,  '36"',    36.0),
    (1000, '40"',    40.0),  (1050, '42"',    42.0),  (1200, '48"',    48.0),
]

_DN_TO_NPS = {dn: (nps_str, nps_val) for dn, nps_str, nps_val in DN_NPS_TABLE}
_NPS_TO_DN = {nps_val: dn for dn, _nps_str, nps_val in DN_NPS_TABLE}
DN_OPTIONS  = [str(dn) for dn, _, _ in DN_NPS_TABLE]
NPS_OPTIONS = [nps for _, nps, _ in DN_NPS_TABLE]

# ASME Class ↔ PN (approximate)
CLASS_PN: dict[int, int] = {150: 20, 300: 50, 600: 100, 900: 150, 1500: 250, 2500: 420}
PN_CLASS: dict[int, int] = {v: k for k, v in CLASS_PN.items()}


# ---------------------------------------------------------------------------
# Conversion functions
# ---------------------------------------------------------------------------

def inches_to_mm(val: float) -> float:
    return val * 25.4

def mm_to_inches(val: float) -> float:
    return val / 25.4

def psi_to_bar(val: float) -> float:
    return val * 0.0689476

def bar_to_psi(val: float) -> float:
    return val * 14.5038

def psi_to_mpa(val: float) -> float:
    return val * 0.00689476

def mpa_to_psi(val: float) -> float:
    return val / 0.00689476

def bar_to_mpa(val: float) -> float:
    return val * 0.1

def mpa_to_bar(val: float) -> float:
    return val * 10.0

def kpa_to_psi(val: float) -> float:
    return val * 0.145038

def psi_to_kpa(val: float) -> float:
    return val / 0.145038

def c_to_f(val: float) -> float:
    return val * 9 / 5 + 32

def f_to_c(val: float) -> float:
    return (val - 32) * 5 / 9

def c_to_k(val: float) -> float:
    return val + 273.15

def k_to_c(val: float) -> float:
    return val - 273.15

def nm_to_ftlb(val: float) -> float:
    return val * 0.737562

def ftlb_to_nm(val: float) -> float:
    return val / 0.737562

def nm_to_inlb(val: float) -> float:
    return val * 8.85075

def inlb_to_nm(val: float) -> float:
    return val / 8.85075

def kn_to_kgf(val: float) -> float:
    return val * 101.972

def kgf_to_kn(val: float) -> float:
    return val / 101.972

def n_to_lbf(val: float) -> float:
    return val / 4.44822

def lbf_to_n(val: float) -> float:
    return val * 4.44822

def dn_to_nps(dn: int) -> str | None:
    """Return NPS display string for a given DN, or None if not in table."""
    row = _DN_TO_NPS.get(dn)
    return row[0] if row else None

def nps_val_to_dn(nps_val: float) -> int | None:
    """Return DN for a given NPS decimal value, or None if not in table."""
    return _NPS_TO_DN.get(nps_val)

def fmt(val: float, decimals: int = 4) -> str:
    """Format float, stripping trailing zeros."""
    return f'{val:.{decimals}f}'.rstrip('0').rstrip('.')
