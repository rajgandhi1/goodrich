"""
Full pipeline e2e tests: LLM extraction → rules.apply_rules → formatter.format_description.
Requires OPENAI_API_KEY in .env (or set in environment).

Each test passes a real customer enquiry string through the pipeline and checks
the resulting ggpl_description against expected GGPL output.

Two assertion helpers:
  _exact(enquiry, expected)  — exact string match
  _contains(enquiry, *parts) — check all parts appear in the description

Run:
    .venv/bin/python tests/test_e2e.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from core.extractor import extract_batch
from core.rules import apply_rules
from core.formatter import format_description


def _run(description, qty=1, uom='Nos'):
    items = [{'description': description, 'quantity': qty, 'uom': uom, 'line_no': 1}]
    extracted = extract_batch(items)
    if not extracted:
        return {}
    item = apply_rules(extracted[0])
    item['ggpl_description'] = format_description(item)
    return item


def _exact(enquiry, expected, label=''):
    item = _run(enquiry)
    got = item.get('ggpl_description', '')
    assert got == expected, (
        f'\n[EXACT/{label}]'
        f'\n  Enquiry : {enquiry}'
        f'\n  Expected: {expected}'
        f'\n  Got     : {got}'
        f'\n  Item    : { {k: v for k, v in item.items() if k not in ("raw_description", "flags", "dimensions")} }'
    )
    return True


def _contains(enquiry, *parts, label=''):
    """Check that all parts appear in the ggpl_description."""
    item = _run(enquiry)
    got = item.get('ggpl_description', '')
    missing = [p for p in parts if p not in got]
    assert not missing, (
        f'\n[CONTAINS/{label}]'
        f'\n  Enquiry : {enquiry}'
        f'\n  Missing : {missing}'
        f'\n  Got     : {got}'
    )
    return True


# ---------------------------------------------------------------------------
# SOFT_CUT
# ---------------------------------------------------------------------------

def test_e2e_soft_cut():
    """E2E: soft-cut gaskets. Checks size/rating/thickness/face/standard in output."""
    passed = 0
    cases = [
        # EPDM 7mm FF — explicit face and thickness
        (
            '24,150#,Sheet Gasket EPDM 150#, ASME B16.21, Flange ASME B16.5, FF, 7.00mm.',
            'SIZE : 24" X 150# X 7MM THK ,EPDM ,FF ,ASME B16.21',
        ),
        # Reinforced chloroprene — LLM extracts moc without shore hardness suffix
        (
            '1.5,150#,REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70, 150#, FF,ASME B16.21.',
            'SIZE : 1.5" X 150# X 3MM THK ,REINFORCED CHLOROPENE RUBBER ,FF ,ASME B16.21',
        ),
        (
            '6,150#,REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70, 150#, FF,ASME B16.21.',
            'SIZE : 6" X 150# X 3MM THK ,REINFORCED CHLOROPENE RUBBER ,FF ,ASME B16.21',
        ),
        # CNAF / Compressed Non-Asbestos Fiber with explicit rating class
        (
            '1CL 300GASKET, CL300, RF, 1.6MM(1/16") THCK, RING TYPE COMP. NON-ASB. SYNTHETIC FIBER, ASME B16.21 B16.5, OIL QUALITY',
            'SIZE : 1" X 300# X 1.6MM THK ,COMPRESSED NON ASBESTOS SYNTHETIC FIBER ,RF ,ASME B16.21',
        ),
    ]
    for enquiry, expected in cases:
        try:
            _exact(enquiry, expected, 'SOFT_CUT')
            passed += 1
        except AssertionError as e:
            print(f'  FAIL:{e}')
    assert passed == len(cases), f'{passed}/{len(cases)} soft-cut e2e cases passed'
    print(f'  All {passed} soft-cut e2e cases passed ✓')


# ---------------------------------------------------------------------------
# SPIRAL WOUND (SPW)
# ---------------------------------------------------------------------------

def test_e2e_spw():
    """E2E: spiral wound gaskets — uses contains checks for LLM-variable moc strings."""
    passed = 0
    cases = [
        # 6" CL900 SS316L EEG — clear spec
        (
            '6" x 4.5mm Nom Thk Gasket Spiral Wound CL900 Dims to ASME B16.20, '
            'SS 316L Windings EXFOLIATED EXPANDED GRAPHITE Filler SS 316L Inner Ring CS Outer Ring',
            ('SIZE : 6"', '900#', '4.5MM THK', 'SS316L', 'EXFOLIATED EXPANDED GRAPHITE', 'SS316L INNER RING', 'CS OUTER RING', 'ASME B16.20'),
        ),
        # 1" CL900 Incoloy 825 Flexible Graphite
        (
            '1" X 4.5MM NOM THK GASKET SPIRAL WOUND CL900 DIMS TO ASME B16.20, '
            'INCOLOY 825 WINDINGS FLEXIBLE GRAPHITE FILLER CS INNER RINGALLOY 825 OUTER RING',
            ('SIZE : 1"', '900#', '4.5MM THK', 'INCOLOY 825', 'GRAPHITE', 'CS INNER RING', 'ALLOY 825 OUTER RING', 'ASME B16.20'),
        ),
        # SPIRAL WOUND GASKET semicolon-separated spec
        (
            'SPIRAL WOUND GASKET; - 1/2 " NS; FOR RF FLANGE; 150 lb; 4.5 mm THK; '
            'STAINLESS STEEL (SS-316) INNER RING; STAINLESS STEEL (SS-316) WINDING METAL; '
            'FLEXIBLE GRAPHITE FILLER; STAINLESS STEEL (SS-316) OUTER RING; NACE MR-01-75 / ISO 15156',
            ('SIZE : 0.5"', '150#', '4.5MM THK', 'SS316', 'SS316 INNER RING', 'SS316 OUTER RING'),
        ),
    ]
    for enquiry, parts in cases:
        try:
            _contains(enquiry, *parts, label='SPW')
            passed += 1
        except AssertionError as e:
            print(f'  FAIL:{e}')
    assert passed == len(cases), f'{passed}/{len(cases)} SPW e2e cases passed'
    print(f'  All {passed} SPW e2e cases passed ✓')


# ---------------------------------------------------------------------------
# RTJ
# ---------------------------------------------------------------------------

def test_e2e_rtj():
    """E2E: RTJ ring joints — ring number, groove (OCTAGONAL), moc, BHN, standard."""
    passed = 0

    # Exact cases: ring number explicit in text, moc clear
    exact_cases = [
        # R-46 Inconel 625, 210 BHN (rules.py default for INCONEL 625)
        (
            'RING JOINT GASKET 6in R46 OCTAGONAL R-TYPE;1500 lb;ASME B16.20;'
            'FOR RTJ FLANGE;ASME B16.5;INCONEL 625 (UNS N06625);NACE MR-01-75 / ISO 15156',
            'SIZE : R-46 ,RTJ ,OCTAGONAL ,INCONEL 625 ,210 BHN HARDNESS ,ASME B16.20',
        ),
        # R-46 Soft Iron Galvanised, 90 BHN (rules.py normalises SOFT IRON → SOFTIRON)
        (
            'RING JOINT GASKET 6in R46 OCTAGONAL R-TYPE;1500 lb;ASME B16.20;'
            'FOR RTJ FLANGE;ASME B16.5;SOFT IRON;GALVANISED;NACE MR-01-75 / ISO 15156',
            'SIZE : R-46 ,RTJ ,OCTAGONAL ,SOFTIRON GALVANISED ,90 BHN HARDNESS ,ASME B16.20',
        ),
    ]
    for enquiry, expected in exact_cases:
        try:
            _exact(enquiry, expected, 'RTJ')
            passed += 1
        except AssertionError as e:
            print(f'  FAIL:{e}')

    # Contains cases: verify key fields present
    contains_cases = [
        # BX-155 SS316 — ring number and moc present
        (
            'BX155-316SSGASKET,RING;BX-155, 316SS',
            ('BX-155', 'SS316', 'BHN HARDNESS', 'ASME B16.20'),
        ),
        # BX-159 SS304
        (
            'BX159-304SSGASKET,RING; BX159 304SS',
            ('BX-159', 'SS304', 'BHN HARDNESS', 'ASME B16.20'),
        ),
    ]
    for enquiry, parts in contains_cases:
        try:
            _contains(enquiry, *parts, label='RTJ')
            passed += 1
        except AssertionError as e:
            print(f'  FAIL:{e}')

    total = len(exact_cases) + len(contains_cases)
    assert passed == total, f'{passed}/{total} RTJ e2e cases passed'
    print(f'  All {passed} RTJ e2e cases passed ✓')


# ---------------------------------------------------------------------------
# KAMMPROFILE (KAMM)
# ---------------------------------------------------------------------------

def test_e2e_kamm():
    """E2E: Kammprofile — NPS and OD/ID cases, moc assembly."""
    passed = 0
    cases = [
        # NPS 24" inner+outer ring — contains checks (LLM moc assembly varies)
        (
            '24GASKET RF 600#, ASME B16.20 Gasket Cam profile, SS 316/ SS 316L GPH, '
            'INR SS 316/316L CS centering ring.',
            ('SIZE : 24"', '600#', '4.5MM THK', 'KAMMPROFILE', 'GRAPHITE', 'INNER RING', 'CS OUTER RING', 'ASME B16.20'),
        ),
        # OD/ID — gasket bore dims with KAMMPROFILE keyword
        (
            'GASKET FOR 5-313-VJ-03 OD=982MM ID=956MM THK= 3 MM, KAMMPROFILE SS 316',
            ('956MM ID', '982MM OD', '3MM THK', 'SS316'),
        ),
        # OD/ID with core thickness
        (
            '2E1 – OD 451mm x ID 372mm , Material Grooved metal SS316 (KAMMPROFILE GASKET) with graphite tape '
            '0.5mm thk both sides, Thk: Core – 4mm, Total- 5mm',
            ('372MM ID', '451MM OD', '5MM THK', 'SS316'),
        ),
    ]
    for enquiry, parts in cases:
        try:
            _contains(enquiry, *parts, label='KAMM')
            passed += 1
        except AssertionError as e:
            print(f'  FAIL:{e}')
    assert passed == len(cases), f'{passed}/{len(cases)} KAMM e2e cases passed'
    print(f'  All {passed} KAMM e2e cases passed ✓')


# ---------------------------------------------------------------------------
# INSULATING GASKET KIT (ISK)
# ---------------------------------------------------------------------------

def test_e2e_isk():
    """E2E: ISK — STYLE-CS, FCS, TYPE-D. Contains checks for moc/component strings."""
    passed = 0
    cases = [
        # STYLE-CS 42" large bore B16.47 SERIES-A
        (
            '42" 150# ASME B16.47 Series A (GASKET DIMENSION D1 IDIR 1041.60, D4 ODCR 1219.20) '
            'PGS COMMANDER EXTREME Flange Isolation Gasket, 4.5 mm THK. RF Type F, '
            'Super Duplex UNS S32760 Steel core with GRE G10 laminate, PTFE seals, to suit flange.',
            ('SIZE: 42"', '150#', 'INSULATING GASKET KIT', 'STYLE-CS', 'RF', 'ASME B16.47 (SERIES-A)'),
        ),
        # STYLE-CS 2" small bore B16.5
        (
            '2" 600# ASME B16.5 (GASKET DIMENSION D1 IDIR 42.82, D4 ODCR 111.30) '
            'PGS COMMANDER EXTREME Flange Isolation Gasket, 4.5 mm THK. RF Type F, '
            'Super Duplex UNS S32760 Steel core with GRE G10 laminate, PTFE seals, to suit flange.',
            ('SIZE: 2"', '600#', 'INSULATING GASKET KIT', 'STYLE-CS', 'RF'),
        ),
        # FCS / VCFS TYPE-F fire safe
        (
            '2" 900# VCFS TYPE - F INSULATION GASKET GRE G10 FIRE SAFE API6FB',
            ('SIZE: 2"', '900#', 'INSULATING GASKET KIT', 'FIRE SAFE'),
        ),
        # TYPE-D non-fire-safe
        (
            '2" 1500# TYPE - D INSULATION GASKET',
            ('SIZE: 2"', '1500#', 'INSULATING GASKET KIT', 'TYPE-D'),
        ),
    ]
    for enquiry, parts in cases:
        try:
            _contains(enquiry, *parts, label='ISK')
            passed += 1
        except AssertionError as e:
            print(f'  FAIL:{e}')
    assert passed == len(cases), f'{passed}/{len(cases)} ISK e2e cases passed'
    print(f'  All {passed} ISK e2e cases passed ✓')


# ---------------------------------------------------------------------------
# ISK_RTJ
# ---------------------------------------------------------------------------

def test_e2e_isk_rtj():
    """E2E: ISK_RTJ — check size/rating/TYPE-RTJ present in output."""
    passed = 0
    cases = [
        (
            '24", INSULATING GASKET KIT, 1500# RTJ, MANUF. STD, '
            'GLASS REINFORCED EPOXY RESIN (GRE G10) w/PTFE',
            ('SIZE: 24"', '1500#', 'ISK'),
        ),
        (
            '6", INSULATING GASKET KIT, 1500# RTJ, MANUF. STD, '
            'GLASS REINFORCED EPOXY RESIN (GRE G10) w/PTFE',
            ('SIZE: 6"', '1500#', 'ISK'),
        ),
    ]
    for enquiry, parts in cases:
        try:
            _contains(enquiry, *parts, label='ISK_RTJ')
            passed += 1
        except AssertionError as e:
            print(f'  FAIL:{e}')
    assert passed == len(cases), f'{passed}/{len(cases)} ISK_RTJ e2e cases passed'
    print(f'  All {passed} ISK_RTJ e2e cases passed ✓')


# ---------------------------------------------------------------------------
# DOUBLE JACKET (DJI)
# ---------------------------------------------------------------------------

def test_e2e_dji():
    """E2E: DJI — OD/ID dims and moc in output."""
    passed = 0
    cases = [
        # Soft iron + graphite, drawing reference
        (
            'DOUBLE JACKETED GASKET CONFIGURATION M, OD 1430 x3x ID 1404 '
            'DRAWING 6273 POSITION 111 MATERIAL SOFT IRON AND GRAPHITE',
            ('1430MM OD', '1404MM ID', 'SOFT IRON', 'GRAPHITE'),
        ),
        # SS316L + graphite with explicit thickness
        (
            'DOUBLE JACKETED GASKET CONFIGURATION M, OD 1618 x 3 x ID 1582, '
            'DRAWING 6299 POSITION 113 MATERIAL 316L AND GRAPHITE',
            ('1618MM OD', '1582MM ID', '3MM THK', 'GRAPHITE'),
        ),
        # Corrugated type
        (
            'DJ NS 367 MM OD X 341 MM ID X 3.2 MM THK, 304L/FG CORRUGATED TYPE',
            ('367MM OD', '341MM ID', '3.2MM THK', 'DOUBLE JACK'),
        ),
    ]
    for enquiry, parts in cases:
        try:
            _contains(enquiry, *parts, label='DJI')
            passed += 1
        except AssertionError as e:
            print(f'  FAIL:{e}')
    assert passed == len(cases), f'{passed}/{len(cases)} DJI e2e cases passed'
    print(f'  All {passed} DJI e2e cases passed ✓')


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        print('WARNING: OPENAI_API_KEY not set — LLM calls will fail\n')

    tests = [
        test_e2e_soft_cut,
        test_e2e_spw,
        test_e2e_rtj,
        test_e2e_kamm,
        test_e2e_isk,
        test_e2e_isk_rtj,
        test_e2e_dji,
    ]
    passed = 0
    print('\nRunning e2e pipeline tests...\n')
    for t in tests:
        print(f'[TEST] {t.__name__}')
        try:
            t()
            passed += 1
        except Exception as e:
            print(f'  FAIL: {e}')
    print(f'\n{passed}/{len(tests)} e2e test suites passed')
