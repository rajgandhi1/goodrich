"""
Real-world integration test: 20 line items covering all 7 gasket types.

Makes ACTUAL LLM calls (no mocking) — requires OPENAI_API_KEY in .env or env.
Validates the full pipeline: extract_batch → apply_rules → format_description.

Items include both HIGH-confidence (regex alone) and MEDIUM/LOW (LLM fills gaps)
cases from reference/ground_truth.csv. Assertions use _contains checks so minor
LLM phrasing variation still passes, but structural correctness is enforced.

Run:
    .venv/bin/python tests/test_extractor_mocked.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from core.extractor import extract_batch
from core.rules import apply_rules
from core.formatter import format_description


# ---------------------------------------------------------------------------
# 20 real-world line items (ground truth CSV examples, all 7 types)
# ---------------------------------------------------------------------------

ITEMS = [
    # ── SOFT CUT (5 items) ─────────────────────────────────────────────────
    # 1. Standard NPS CNAF — regex HIGH
    {
        'line_no': 1, 'quantity': 20, 'uom': 'Nos',
        'description': 'NPS 6, CNAF Flat Ring Gaskets, Cl. 150, as per ASME B16.21 for B16.5 flanges',
        'expect_contains': ('6"', '150#', 'CNAF', 'ASME B16.21'),
        'expect_type': 'SOFT_CUT',
        'label': 'Softcut NPS6 CNAF CL150',
    },
    # 2. EPDM with explicit face and thickness — regex HIGH
    {
        'line_no': 2, 'quantity': 10, 'uom': 'Nos',
        'description': '6" x 150 LBS x 3mm thk, EPDM Gasket, RF',
        'expect_contains': ('6"', '150#', 'EPDM', 'RF'),
        'expect_type': 'SOFT_CUT',
        'label': 'Softcut EPDM RF 150LBS',
    },
    # 3. DN/PN format → EN standard — regex HIGH
    {
        'line_no': 3, 'quantity': 5, 'uom': 'Nos',
        'description': 'DN 100 PN 16 CNAF Gasket, Full Face, EN 1514-1',
        'expect_contains': ('DN 100', 'PN 16', 'CNAF', 'FF', 'EN 1514'),
        'expect_type': 'SOFT_CUT',
        'label': 'Softcut DN100 PN16 FF',
    },
    # 4. Mixed fraction size — regex HIGH
    {
        'line_no': 4, 'quantity': 8, 'uom': 'Nos',
        'description': '1-1/2" X 300# X 3MM THK, VITON, RF, ASME B16.21',
        'expect_contains': ('300#', 'VITON', 'RF', 'ASME B16.21'),
        'expect_type': 'SOFT_CUT',
        'label': 'Softcut 1.5" Viton CL300',
    },
    # 5. Unusual comma-size format "1.5,150#" — regex MEDIUM, LLM normalises MOC
    # Ground truth row from e2e test: output = SIZE : 1.5" X 150# X 3MM THK ,... ,FF ,ASME B16.21
    {
        'line_no': 5, 'quantity': 4, 'uom': 'Nos',
        'description': '1.5,150#,REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70, 150#, FF,ASME B16.21.',
        'expect_contains': ('1.5"', '150#', 'FF', 'ASME B16.21'),
        'expect_type': 'SOFT_CUT',
        'label': 'Softcut 1.5 comma-format LLM normalises MOC',
    },

    # ── SPIRAL WOUND (5 items) ──────────────────────────────────────────────
    # 6. SS316 with all rings — regex HIGH
    {
        'line_no': 6, 'quantity': 15, 'uom': 'Nos',
        'description': (
            '2" x 4.5mm, SS316 SPIRAL WOUND GRAPHITE FILLED GASKET '
            'WITH SS316 INNER AND CS OUTER RINGS, 150#, ASME B16.20'
        ),
        'expect_contains': ('2"', '150#', 'SS316', 'GRAPHITE', 'ASME B16.20'),
        'expect_type': 'SPIRAL_WOUND',
        'label': 'SPW SS316 Graphite CL150',
    },
    # 7. SS316L CL600 with inner+outer rings — regex HIGH
    {
        'line_no': 7, 'quantity': 6, 'uom': 'Nos',
        'description': (
            '4" 600# SPIRAL WOUND GASKET SS316L GRAPHITE FILLER '
            'SS316L INNER CS OUTER RING ASME B16.20'
        ),
        'expect_contains': ('4"', '600#', 'SS316L', 'GRAPHITE', 'CS OUTER RING', 'ASME B16.20'),
        'expect_type': 'SPIRAL_WOUND',
        'label': 'SPW SS316L CL600',
    },
    # 8. Incoloy 825 with flexible graphite — regex HIGH
    {
        'line_no': 8, 'quantity': 3, 'uom': 'Nos',
        'description': (
            '1" X 4.5MM NOM THK GASKET SPIRAL WOUND CL900 DIMS TO ASME B16.20, '
            'INCOLOY 825 WINDINGS FLEXIBLE GRAPHITE FILLER CS INNER RING ALLOY 825 OUTER RING'
        ),
        'expect_contains': ('1"', '900#', 'GRAPHITE', 'CS INNER RING', 'ASME B16.20'),
        'expect_type': 'SPIRAL_WOUND',
        'label': 'SPW Incoloy825 CL900',
    },
    # 9. Non-standard format '316L/GRAPH' — regex MEDIUM → LLM normalises
    {
        'line_no': 9, 'quantity': 12, 'uom': 'Nos',
        'description': 'GSKT SPIR WND 2" 300# 316L/GRAPH',
        'expect_contains': ('2"', '300#'),
        'expect_type': 'SPIRAL_WOUND',
        'label': 'SPW nonstd 316L/GRAPH LLM fills',
    },
    # 10. Hastelloy C276 with PTFE filler — regex HIGH (winding in description)
    {
        'line_no': 10, 'quantity': 2, 'uom': 'Nos',
        'description': (
            'SPIRAL WOUND GASKET 6" 150# HASTELLOY C276 PTFE FILL CS OUTER RING ASME B16.20'
        ),
        'expect_contains': ('6"', '150#', 'HASTELLOY C276', 'PTFE', 'ASME B16.20'),
        'expect_type': 'SPIRAL_WOUND',
        'label': 'SPW Hastelloy C276 PTFE CL150',
    },

    # ── RTJ (4 items) ───────────────────────────────────────────────────────
    # 11. Soft iron octagonal CL600 — regex HIGH; RTJ format uses ring_no, not NPS size
    # Ring R-23 is auto-assigned for 2" CL600 from dimension table
    {
        'line_no': 11, 'quantity': 4, 'uom': 'Nos',
        'description': (
            'NPS 2, Gasket, Cl 600, Soft Iron Octagonal Ring Joint Gasket, Galvanised'
        ),
        'expect_contains': ('RTJ', 'OCTAGONAL', 'SOFTIRON', 'ASME B16.20'),
        'expect_type': 'RTJ',
        'label': 'RTJ Soft Iron Octagonal CL600',
    },
    # 12. Inconel 625 with ring number R-46 — regex HIGH
    {
        'line_no': 12, 'quantity': 2, 'uom': 'Nos',
        'description': (
            'RING JOINT GASKET 6in R46 OCTAGONAL R-TYPE;1500 lb;ASME B16.20;'
            'FOR RTJ FLANGE;ASME B16.5;INCONEL 625 (UNS N06625)'
        ),
        'expect_contains': ('R-46', 'RTJ', 'OCTAGONAL', 'INCONEL 625', 'ASME B16.20'),
        'expect_type': 'RTJ',
        'label': 'RTJ R46 Inconel625 1500lb',
    },
    # 13. Oval groove with Soft Iron — regex HIGH; ring_no auto-assigned from dim table
    {
        'line_no': 13, 'quantity': 8, 'uom': 'Nos',
        'description': 'RTJ GASKET 4" CL 600 OVAL RING JOINT SOFT IRON',
        'expect_contains': ('RTJ', 'OVAL', 'SOFTIRON', 'ASME B16.20'),
        'expect_type': 'RTJ',
        'label': 'RTJ Oval CL600 Soft Iron',
    },
    # 14. BX ring number — regex HIGH (clean description)
    {
        'line_no': 14, 'quantity': 1, 'uom': 'Nos',
        'description': 'GASKET RTJ 6" 1500# BX-155 SS316 OCTAGONAL ASME B16.20',
        'expect_contains': ('BX-155', 'SS316', 'ASME B16.20'),
        'expect_type': 'RTJ',
        'label': 'RTJ BX155 SS316 1500#',
    },

    # ── KAMMPROFILE (2 items) ───────────────────────────────────────────────
    # 15. Camprofile NPS with SS316 — LLM fills moc → KAMMPROFILE in output
    # Ground truth: '24GASKET RF 600#...' → SIZE : 24" X 600# X 4.5MM THK,SS316 KAMMPROFILE GASKET...
    {
        'line_no': 15, 'quantity': 2, 'uom': 'Nos',
        'description': (
            '24GASKET RF 600#, ASME B16.20 Gasket Cam profile, '
            'SS 316/ SS 316L GPH, INR SS 316/316L CS centering ring.'
        ),
        'expect_contains': ('24"', '600#', 'KAMMPROFILE', 'SS316', 'ASME B16.20'),
        'expect_type': 'KAMM',
        'label': 'KAMM 24" CL600 SS316 camprofile',
    },
    # 16. OD/ID kammprofile — KAMM output format: SIZE : NNN ID X NNN OD X NNN THK,{moc}
    {
        'line_no': 16, 'quantity': 1, 'uom': 'Nos',
        'description': '2E1 OD 451mm x ID 372mm KAMMPROFILE GASKET SS316 GRAPHITE 5MM THK',
        'expect_contains': ('372MM ID', '451MM OD', '5MM THK', 'SS316'),
        'expect_type': 'KAMM',
        'label': 'KAMM OD451 ID372 SS316 graphite',
    },

    # ── ISK (2 items) ────────────────────────────────────────────────────────
    # 17. GRE G10 isolating kit with RF — regex HIGH
    {
        'line_no': 17, 'quantity': 10, 'uom': 'Nos',
        'description': '8", GSKT INSULATION 150# RF, GASKET GRE (G10), W/316SS CORE',
        'expect_contains': ('8"', '150#', 'INSULATING GASKET KIT', 'RF'),
        'expect_type': 'ISK',
        'label': 'ISK GRE G10 RF 150#',
    },
    # 18. VCFS Type F, fire safe — regex HIGH
    {
        'line_no': 18, 'quantity': 4, 'uom': 'Nos',
        'description': '2" 900# VCFS TYPE - F INSULATION GASKET GRE G10 FIRE SAFE API6FB',
        'expect_contains': ('2"', '900#', 'INSULATING GASKET KIT', 'FIRE SAFE'),
        'expect_type': 'ISK',
        'label': 'ISK VCFS TypeF FireSafe 900#',
    },

    # ── ISK-RTJ (1 item) ─────────────────────────────────────────────────────
    # 19. ISK ring joint variant — regex HIGH
    {
        'line_no': 19, 'quantity': 6, 'uom': 'Nos',
        'description': (
            '6", INSULATING GASKET KIT, 1500# RTJ, MANUF. STD, '
            'GLASS REINFORCED EPOXY RESIN (GRE G10) w/PTFE'
        ),
        'expect_contains': ('6"', '1500#', 'ISK'),
        'expect_type': ('ISK', 'ISK_RTJ'),
        'label': 'ISK-RTJ 6" 1500# GRE G10',
    },

    # ── DJI (1 item) ─────────────────────────────────────────────────────────
    # 20. Double jacketed SS316L + graphite — regex/LLM fills moc
    {
        'line_no': 20, 'quantity': 3, 'uom': 'Nos',
        'description': (
            'DOUBLE JACKETED GASKET OD 400 x 3 x ID 380, '
            'MATERIAL S.S 316L AND GRAPHITE'
        ),
        'expect_contains': ('400MM OD', '380MM ID', 'DOUBLE JACK'),
        'expect_type': 'DJI',
        'label': 'DJI OD400 ID380 SS316L+Graphite',
    },
]


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_pipeline(items):
    raw = [
        {
            'description': it['description'],
            'quantity': it['quantity'],
            'uom': it['uom'],
            'line_no': it['line_no'],
        }
        for it in items
    ]
    extracted = extract_batch(raw)
    processed = []
    for ext in extracted:
        item = apply_rules(ext)
        item['ggpl_description'] = format_description(item)
        processed.append(item)
    return processed


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _check_contains(ggpl_desc: str, parts: tuple, label: str) -> list[str]:
    """Return list of missing parts (empty = pass)."""
    return [p for p in parts if p not in ggpl_desc]


def _check_type(gasket_type: str, expected_type, label: str) -> str | None:
    """Return error string if type doesn't match, else None."""
    if isinstance(expected_type, tuple):
        if gasket_type not in expected_type:
            return f'type={gasket_type!r} not in {expected_type}'
    else:
        if gasket_type != expected_type:
            return f'type expected {expected_type!r}, got {gasket_type!r}'
    return None


# ---------------------------------------------------------------------------
# Single combined test — all 20 items
# ---------------------------------------------------------------------------

def test_20_line_items_all_types():
    """
    Full pipeline test: 20 real-world items covering all 7 gasket types.
    Runs actual LLM calls. Validates gasket_type and key fields in ggpl_description.
    """
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        print('WARNING: OPENAI_API_KEY not set — LLM calls will be skipped for MEDIUM/LOW items\n')

    print(f'\nProcessing {len(ITEMS)} line items...\n')
    results = run_pipeline(ITEMS)

    # Map line_no → result
    by_line = {r['line_no']: r for r in results}

    passed = failed = 0
    failures = []

    for spec in ITEMS:
        ln = spec['line_no']
        result = by_line.get(ln, {})
        desc = result.get('ggpl_description', '')
        gtype = result.get('gasket_type', '')
        label = spec['label']

        errors = []

        # Check gasket type
        type_err = _check_type(gtype, spec['expect_type'], label)
        if type_err:
            errors.append(type_err)

        # Check expected substrings in GGPL description
        missing = _check_contains(desc, spec['expect_contains'], label)
        if missing:
            errors.append(f'Missing in description: {missing}')

        if errors:
            failed += 1
            failures.append((label, desc, errors))
            print(f'  FAIL  [{ln:02d}] {label}')
            for e in errors:
                print(f'         {e}')
            print(f'         Output: {desc}')
        else:
            passed += 1
            print(f'  PASS  [{ln:02d}] {label}')
            print(f'         {desc}')

    print(f'\n{passed}/{passed + failed} items passed')

    if failures:
        summary = '\n'.join(
            f'  [{spec}] {errs}' for spec, _, errs in failures
        )
        raise AssertionError(
            f'\n{failed} item(s) failed:\n{summary}'
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    try:
        test_20_line_items_all_types()
        print('\nAll tests passed.')
    except AssertionError as e:
        print(e)
        sys.exit(1)
