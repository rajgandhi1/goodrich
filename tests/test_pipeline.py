"""
End-to-end pipeline tests using the WABAG email and L&T Excel as inputs.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from core.parser import parse_email_text, parse_excel_file
from core.extractor import extract_batch
from core.rules import apply_rules, STATUS_READY, STATUS_CHECK, STATUS_MISSING
from core.formatter import format_description

WABAG_EMAIL = """
Sl.No	Line No	Release No	Notes	Quantity	Inv UoM
1	1	1	Gasket - Rubber - 0.5'' PN10	10	m
2	1	4	Gasket - Rubber - 16'' PN10	14	m
3	1	6	Gasket - Rubber - 5'' PN10	16	m
4	1	2	Gasket - Rubber - 10'' PN10	18	m
5	1	9	Gasket - Rubber - 12'' PN10	18	m
6	1	3	Gasket - Rubber - 14'' PN10	2	m
7	1	7	Gasket - Rubber - 6'' PN10	27	m
8	1	10	Gasket - Rubber - 3'' PN10	5	m
9	1	8	Gasket - Rubber - 8'' PN10	60	m
10	1	5	Gasket - Rubber - 22'' PN10	8	m
11	2	4	Gasket 150# - Neoprene - 0.5"	104	Nos
12	2	1	Gasket 150# - Neoprene - 1"	104	Nos
13	2	8	Gasket 150# - Neoprene - 10"	13	Nos
14	2	9	Gasket 150# - Neoprene - 12"	8	Nos
15	2	6	Gasket 150# - Neoprene - 3"	28	Nos
16	2	5	Gasket 150# - Neoprene - 4"	30	Nos
17	2	7	Gasket 150# - Neoprene - 5"	6	Nos
18	2	3	Gasket 150# - Neoprene - 6"	25	Nos
19	2	2	Gasket 150# - Neoprene - 8"	150	Nos
"""

# Expected GGPL descriptions for Neoprene items (from completed WABAG quote)
EXPECTED_NEOPRENE = {
    '0.5"':  'SIZE : 1/2" X 150# X 3MM THK ,NEOPRENE ,RF ,ASME B16.21',
    '1"':    'SIZE : 1" X 150# X 3MM THK ,NEOPRENE ,RF ,ASME B16.21',
    '6"':    'SIZE : 6" X 150# X 3MM THK ,NEOPRENE ,RF ,ASME B16.21',
}


def run_pipeline(raw_items):
    extracted = extract_batch(raw_items)
    processed = [apply_rules(item) for item in extracted]
    for item in processed:
        item['ggpl_description'] = format_description(item)
    return processed


def test_email_parsing():
    items = parse_email_text(WABAG_EMAIL)
    assert len(items) == 19, f'Expected 19 items, got {len(items)}'
    print(f'  Parsed {len(items)} items from email ✓')


def test_rubber_flagged_as_missing():
    items = parse_email_text(WABAG_EMAIL)
    processed = run_pipeline(items)
    rubber_items = [i for i in processed if 'RUBBER' in (i.get('moc') or '').upper()
                    and 'PN' in (i.get('rating') or '')]
    assert len(rubber_items) == 10, f'Expected 10 rubber items, got {len(rubber_items)}'
    for item in rubber_items:
        assert item['status'] == STATUS_MISSING, f'Rubber item should be MISSING: {item}'
        assert any('ambiguous' in f.lower() for f in item['flags'])
    print(f'  All {len(rubber_items)} rubber PN items correctly flagged as MISSING ✓')


def test_neoprene_items_ready_or_check():
    items = parse_email_text(WABAG_EMAIL)
    processed = run_pipeline(items)
    neoprene_items = [i for i in processed if 'NEOPRENE' in (i.get('moc') or '').upper()]
    assert len(neoprene_items) == 9, f'Expected 9 neoprene items, got {len(neoprene_items)}'
    for item in neoprene_items:
        assert item['status'] in (STATUS_READY, STATUS_CHECK), \
            f'Neoprene item should not be MISSING: {item}'
    print(f'  All {len(neoprene_items)} neoprene items are ready/check ✓')


def test_description_format():
    items = parse_email_text(WABAG_EMAIL)
    processed = run_pipeline(items)
    neoprene = {i['size']: i for i in processed if 'NEOPRENE' in (i.get('moc') or '')}
    for size, expected in EXPECTED_NEOPRENE.items():
        item = neoprene.get(size)
        if item:
            assert item['ggpl_description'] == expected, \
                f'\nExpected: {expected}\nGot:      {item["ggpl_description"]}'
    print(f'  GGPL description format matches expected output ✓')


def test_excel_wabag():
    path = os.path.join(os.path.dirname(__file__), '..', 'reference', 'WABAG_ENQUIRY.xlsx')
    with open(path, 'rb') as f:
        items = parse_excel_file(f.read())
    # WABAG excel is the completed quote — all items have GGPL description already
    # Parser should find the description column and return items
    assert len(items) > 0, 'Expected items from WABAG Excel'
    print(f'  Parsed {len(items)} items from WABAG Excel ✓')


def test_lt_excel():
    path = os.path.join(os.path.dirname(__file__), '..', 'reference',
                        'EXCEL OFFER - LARSEN & TOUBRO - (ENQUIRY OF GASKET ) ADNOC PROJECT.xlsx')
    with open(path, 'rb') as f:
        items = parse_excel_file(f.read())
    assert len(items) > 0, 'Expected items from L&T Excel'
    print(f'  Parsed {len(items)} items from L&T Excel ✓')


def test_softcut_formatter():
    """Test soft-cut formatter output for a range of sizes, face types, and thicknesses.
    All fields are pre-set — no LLM needed.
    """
    cases = [
        # Basic FF, 3mm, B16.21 (1.5")
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': '1.5"', 'rating': '150#',
                'thickness_mm': 3, 'moc': 'REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : 1.5" X 150# X 3MM THK ,REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70 ,FF ,ASME B16.21',
        },
        # Same MOC, larger bore 6"
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': '6"', 'rating': '150#',
                'thickness_mm': 3, 'moc': 'REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : 6" X 150# X 3MM THK ,REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70 ,FF ,ASME B16.21',
        },
        # Large bore 48" — B16.47 Series B
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': '48"', 'rating': '150#',
                'thickness_mm': 3, 'moc': 'REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70',
                'face_type': 'FF', 'standard': 'ASME B16.47 (SERIES-B)',
            },
            'expected': 'SIZE : 48" X 150# X 3MM THK ,REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70 ,FF ,ASME B16.47 (SERIES-B)',
        },
        # RF face, ARAMID WITH NBR BINDER
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': '1"', 'rating': '150#',
                'thickness_mm': 3, 'moc': 'ARAMID WITH NBR BINDER',
                'face_type': 'RF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : 1" X 150# X 3MM THK ,ARAMID WITH NBR BINDER ,RF ,ASME B16.21',
        },
        # 1.5mm thickness (thin gasket)
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': '10"', 'rating': '150#',
                'thickness_mm': 1.5, 'moc': 'CNAF',
                'face_type': 'RF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : 10" X 150# X 1.5MM THK ,CNAF ,RF ,ASME B16.21',
        },
        # 7mm thickness, FF
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': '10"', 'rating': '150#',
                'thickness_mm': 7, 'moc': 'REINFORCED CHLOROPENE RUBBER',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : 10" X 150# X 7MM THK ,REINFORCED CHLOROPENE RUBBER ,FF ,ASME B16.21',
        },
        # EPDM 24" 7mm FF
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': '24"', 'rating': '150#',
                'thickness_mm': 7, 'moc': 'EPDM',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : 24" X 150# X 7MM THK ,EPDM ,FF ,ASME B16.21',
        },
        # DN metric size — 3" (NPS) equivalent
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': '3"', 'rating': '150#',
                'thickness_mm': 3, 'moc': 'EPDM GASKET',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : 3" X 150# X 3MM THK ,EPDM GASKET ,FF ,ASME B16.21',
        },
        # DN 100 — formatter keeps DN prefix with space
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': 'DN 100', 'rating': '150#',
                'thickness_mm': 3, 'moc': 'EPDM GASKET',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : DN 100 X 150# X 3MM THK ,EPDM GASKET ,FF ,ASME B16.21',
        },
        # DN 150 3mm FF
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': 'DN 150', 'rating': '150#',
                'thickness_mm': 3, 'moc': 'EPDM GASKET',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : DN 150 X 150# X 3MM THK ,EPDM GASKET ,FF ,ASME B16.21',
        },
        # DN 350 7mm FF (< 26" NPS equivalent → B16.21)
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': 'DN 350', 'rating': '150#',
                'thickness_mm': 7, 'moc': 'EPDM GASKET',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : DN 350 X 150# X 7MM THK ,EPDM GASKET ,FF ,ASME B16.21',
        },
        # DN 500 7mm FF
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': 'DN 500', 'rating': '150#',
                'thickness_mm': 7, 'moc': 'EPDM GASKET',
                'face_type': 'FF', 'standard': 'ASME B16.21',
            },
            'expected': 'SIZE : DN 500 X 150# X 7MM THK ,EPDM GASKET ,FF ,ASME B16.21',
        },
        # DN 700 8mm FF — large bore → B16.47 Series A
        {
            'item': {
                'gasket_type': 'SOFT_CUT', 'size': 'DN 700', 'rating': '150#',
                'thickness_mm': 8, 'moc': 'EPDM GASKET',
                'face_type': 'FF', 'standard': 'ASME B16.47 (SERIES-A)',
            },
            'expected': 'SIZE : DN 700 X 150# X 8MM THK ,EPDM GASKET ,FF ,ASME B16.47 (SERIES-A)',
        },
    ]

    for i, case in enumerate(cases):
        result = format_description(case['item'])
        assert result == case['expected'], (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {case["expected"]}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} soft-cut formatter cases passed ✓')


def test_spw_formatter():
    """Spiral wound formatter tests — pre-set moc string, no LLM needed.
    Note: formatter always appends FILLER keyword and converts size fractions to decimals.
    """
    def spw(size, rating, thk, moc_str):
        return {
            'gasket_type': 'SPIRAL_WOUND', 'size': size, 'rating': rating,
            'thickness_mm': thk, 'moc': moc_str,
            'face_type': None, 'standard': 'ASME B16.20',
        }

    _EEG = 'EXFOLIATED EXPANDED GRAPHITE FILLER'  # normalized filler name
    _FG  = 'FLEXIBLE GRAPHITE FILLER'
    _G   = 'GRAPHITE FILLER'

    cases = [
        # SS316L, Exfoliated Expanded Graphite, SS316L inner, CS outer — CL900 6"
        (spw('6"', '900#', 4.5, f'SS316L SPIRAL WOUND GASKET WITH {_EEG} + SS316L INNER RING & CS OUTER RING'),
         'SIZE : 6" X 900# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH EXFOLIATED EXPANDED GRAPHITE FILLER + SS316L INNER RING & CS OUTER RING, ASME B16.20'),
        # Same spec, 1" CL1500
        (spw('1"', '1500#', 4.5, f'SS316L SPIRAL WOUND GASKET WITH {_EEG} + SS316L INNER RING & CS OUTER RING'),
         'SIZE : 1" X 1500# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH EXFOLIATED EXPANDED GRAPHITE FILLER + SS316L INNER RING & CS OUTER RING, ASME B16.20'),
        # 2" CL1500
        (spw('2"', '1500#', 4.5, f'SS316L SPIRAL WOUND GASKET WITH {_EEG} + SS316L INNER RING & CS OUTER RING'),
         'SIZE : 2" X 1500# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH EXFOLIATED EXPANDED GRAPHITE FILLER + SS316L INNER RING & CS OUTER RING, ASME B16.20'),
        # SS316 winding, plain Graphite filler, SS316 inner, CS outer — CL900
        (spw('2"', '900#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_G} + SS316 INNER RING & CS OUTER RING'),
         'SIZE : 2" X 900# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316 INNER RING & CS OUTER RING, ASME B16.20'),
        (spw('4"', '900#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_G} + SS316 INNER RING & CS OUTER RING'),
         'SIZE : 4" X 900# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316 INNER RING & CS OUTER RING, ASME B16.20'),
        (spw('6"', '900#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_G} + SS316 INNER RING & CS OUTER RING'),
         'SIZE : 6" X 900# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316 INNER RING & CS OUTER RING, ASME B16.20'),
        # Incoloy 825 winding, Flexible Graphite filler, CS inner, Alloy 825 outer
        (spw('1"', '900#', 4.5, f'INCOLOY 825 SPIRAL WOUND GASKET WITH {_FG} + CS INNER RING & ALLOY 825 OUTER RING'),
         'SIZE : 1" X 900# X 4.5MM THK, INCOLOY 825 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER + CS INNER RING & ALLOY 825 OUTER RING, ASME B16.20'),
        # SS316, Flexible Graphite, SS316 inner & outer — fractional sizes (1/2→0.5, 3/4→0.75)
        (spw('1/2"', '150#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_FG} + SS316 INNER RING & SS316 OUTER RING'),
         'SIZE : 0.5" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
        (spw('3/4"', '150#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_FG} + SS316 INNER RING & SS316 OUTER RING'),
         'SIZE : 0.75" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
        (spw('1"', '150#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_FG} + SS316 INNER RING & SS316 OUTER RING'),
         'SIZE : 1" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
        # 1 1/2" mixed fraction → 1.5"; CL600 SS316L with CNAF filler
        (spw('1 1/2"', '600#', 4.5, f'SS316L SPIRAL WOUND GASKET WITH CNAF FILLER + SS316L INNER RING & SS316L OUTER RING'),
         'SIZE : 1.5" X 600# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH CNAF FILLER + SS316L INNER RING & SS316L OUTER RING, ASME B16.20'),
        # 1 1/2" CL150
        (spw('1 1/2"', '150#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_FG} + SS316 INNER RING & SS316 OUTER RING'),
         'SIZE : 1.5" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
        # 2", 3", 4" CL150
        (spw('2"', '150#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_FG} + SS316 INNER RING & SS316 OUTER RING'),
         'SIZE : 2" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
        (spw('3"', '150#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_FG} + SS316 INNER RING & SS316 OUTER RING'),
         'SIZE : 3" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
        (spw('4"', '150#', 4.5, f'SS316 SPIRAL WOUND GASKET WITH {_FG} + SS316 INNER RING & SS316 OUTER RING'),
         'SIZE : 4" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
    ]

    for i, (item, expected) in enumerate(cases):
        result = format_description(item)
        assert result == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {expected}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} SPW formatter cases passed ✓')


def test_rtj_formatter():
    """RTJ formatter tests — pre-set item dicts, no LLM needed.
    Covers: R-type rings (with RTJ+groove), BX rings (no groove), coatings, NACE standard.
    """
    def rtj(ring_no, moc, bhn, standard, groove='OCTAGONAL'):
        return {
            'gasket_type': 'RTJ', 'ring_no': ring_no, 'moc': moc,
            'rtj_groove_type': groove, 'rtj_hardness_bhn': bhn, 'standard': standard,
        }

    _B16 = 'ASME B16.20'
    _NACE_B16 = 'NACE MR-01-75 / ISO 15156, ASME B16.20'

    cases = [
        # R-46, Inconel 625, 210 BHN — plain B16.20
        (rtj('R-46', 'INCONEL 625', 210, _B16),
         'SIZE : R-46 ,RTJ ,OCTAGONAL ,INCONEL 625 ,210 BHN HARDNESS ,ASME B16.20'),
        # R-46, Soft Iron Galvanised, 90 BHN — coating kept as part of moc (not split)
        (rtj('R-46', 'SOFT IRON GALVANISED', 90, _B16),
         'SIZE : R-46 ,RTJ ,OCTAGONAL ,SOFT IRON GALVANISED ,90 BHN HARDNESS ,ASME B16.20'),
        # R-75, Inconel 625, 210 BHN
        (rtj('R-75', 'INCONEL 625', 210, _B16),
         'SIZE : R-75 ,RTJ ,OCTAGONAL ,INCONEL 625 ,210 BHN HARDNESS ,ASME B16.20'),
        # R-63, Inconel 625, 210 BHN
        (rtj('R-63', 'INCONEL 625', 210, _B16),
         'SIZE : R-63 ,RTJ ,OCTAGONAL ,INCONEL 625 ,210 BHN HARDNESS ,ASME B16.20'),
        # R-63, Soft Iron Galvanised, 90 BHN
        (rtj('R-63', 'SOFT IRON GALVANISED', 90, _B16),
         'SIZE : R-63 ,RTJ ,OCTAGONAL ,SOFT IRON GALVANISED ,90 BHN HARDNESS ,ASME B16.20'),
        # NACE cases — standard field contains both NACE and B16.20 as one string
        (rtj('R-46', 'UNS S32205', 230, _NACE_B16),
         'SIZE : R-46 ,RTJ ,OCTAGONAL ,UNS S32205 ,230 BHN HARDNESS ,NACE MR-01-75 / ISO 15156, ASME B16.20'),
        (rtj('R-12', 'SOFT IRON', 90, _NACE_B16),
         'SIZE : R-12 ,RTJ ,OCTAGONAL ,SOFT IRON ,90 BHN HARDNESS ,NACE MR-01-75 / ISO 15156, ASME B16.20'),
        (rtj('R-12', 'UNS S32205', 230, _NACE_B16),
         'SIZE : R-12 ,RTJ ,OCTAGONAL ,UNS S32205 ,230 BHN HARDNESS ,NACE MR-01-75 / ISO 15156, ASME B16.20'),
        (rtj('R-14', 'SOFT IRON', 90, _NACE_B16),
         'SIZE : R-14 ,RTJ ,OCTAGONAL ,SOFT IRON ,90 BHN HARDNESS ,NACE MR-01-75 / ISO 15156, ASME B16.20'),
        (rtj('R-14', 'UNS S32205', 230, _NACE_B16),
         'SIZE : R-14 ,RTJ ,OCTAGONAL ,UNS S32205 ,230 BHN HARDNESS ,NACE MR-01-75 / ISO 15156, ASME B16.20'),
        (rtj('R-16', 'SOFT IRON', 90, _NACE_B16),
         'SIZE : R-16 ,RTJ ,OCTAGONAL ,SOFT IRON ,90 BHN HARDNESS ,NACE MR-01-75 / ISO 15156, ASME B16.20'),
        (rtj('R-20', 'SOFT IRON', 90, _NACE_B16),
         'SIZE : R-20 ,RTJ ,OCTAGONAL ,SOFT IRON ,90 BHN HARDNESS ,NACE MR-01-75 / ISO 15156, ASME B16.20'),
        (rtj('R-23', 'SOFT IRON', 90, _NACE_B16),
         'SIZE : R-23 ,RTJ ,OCTAGONAL ,SOFT IRON ,90 BHN HARDNESS ,NACE MR-01-75 / ISO 15156, ASME B16.20'),
        # BX rings — no RTJ/groove designation, ASME B16.20
        (rtj('BX-155', 'SS316', 160, _B16),
         'SIZE : BX-155 ,SS316 ,160 BHN HARDNESS ,ASME B16.20'),
        (rtj('BX-156', 'SS316', 160, _B16),
         'SIZE : BX-156 ,SS316 ,160 BHN HARDNESS ,ASME B16.20'),
        (rtj('BX-157', 'SS316', 160, _B16),
         'SIZE : BX-157 ,SS316 ,160 BHN HARDNESS ,ASME B16.20'),
        (rtj('BX-159', 'SS316', 160, _B16),
         'SIZE : BX-159 ,SS316 ,160 BHN HARDNESS ,ASME B16.20'),
        (rtj('BX-159', 'SS304', 160, _B16),
         'SIZE : BX-159 ,SS304 ,160 BHN HARDNESS ,ASME B16.20'),
    ]

    for i, (item, expected) in enumerate(cases):
        result = format_description(item)
        assert result == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {expected}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} RTJ formatter cases passed ✓')


def test_kamm_formatter():
    """Kammprofile formatter tests — pre-set moc, no LLM needed.
    Covers NPS (with/without inner ring, large bore B16.47) and OD/ID (with/without special).
    """
    def nps(size, rating, thk, moc_str, standard):
        return {'gasket_type': 'KAMM', 'size': size, 'rating': rating, 'thickness_mm': thk,
                'moc': moc_str, 'standard': standard, 'size_type': 'NPS'}

    def oid(od, id_, thk, moc_str, special=None):
        return {'gasket_type': 'KAMM', 'size_type': 'OD_ID',
                'od_mm': od, 'id_mm': id_, 'thickness_mm': thk,
                'moc': moc_str, 'special': special}

    _B16   = 'ASME B16.20'
    _B1647 = 'ASME B16.47 (SERIES-B)'
    _GF    = 'GRAPHITE FILLER'
    _GL    = 'GRAPHITE LAYERS ON BOTH SIDES'

    cases = [
        # --- NPS with inner + outer ring ---
        # 24" CL600 — SS316/SS316L inner + CS outer — B16.20
        (nps('24"', '600#', 4.5,
             f'SS316/SS316L KAMMPROFILE GASKET WITH {_GF} + SS316/SS316L INNER RING & CS OUTER RING', _B16),
         'SIZE : 24" X 600# X 4.5MM THK,SS316/SS316L KAMMPROFILE GASKET WITH GRAPHITE FILLER + SS316/SS316L INNER RING & CS OUTER RING,ASME B16.20'),
        # 32" CL600 — large bore → B16.47 Series B
        (nps('32"', '600#', 4.5,
             f'SS316/SS316L KAMMPROFILE GASKET WITH {_GF} + SS316/SS316L INNER RING & CS OUTER RING', _B1647),
         'SIZE : 32" X 600# X 4.5MM THK,SS316/SS316L KAMMPROFILE GASKET WITH GRAPHITE FILLER + SS316/SS316L INNER RING & CS OUTER RING,ASME B16.47 (SERIES-B)'),
        # --- NPS with outer ring only (centering ring) ---
        # 6" CL150 SS316L outer ring
        (nps('6"', '150#', 5,
             f'SS316L KAMMPROFILE GASKET WITH {_GL} + SS316L OUTER RING', _B16),
         'SIZE : 6" X 150# X 5MM THK,SS316L KAMMPROFILE GASKET WITH GRAPHITE LAYERS ON BOTH SIDES + SS316L OUTER RING,ASME B16.20'),
        # 1" CL300 SS321 outer ring
        (nps('1"', '300#', 5,
             f'SS321 KAMMPROFILE GASKET WITH {_GL} + SS321 OUTER RING', _B16),
         'SIZE : 1" X 300# X 5MM THK,SS321 KAMMPROFILE GASKET WITH GRAPHITE LAYERS ON BOTH SIDES + SS321 OUTER RING,ASME B16.20'),
        # 1" CL300 SS321H outer ring
        (nps('1"', '300#', 5,
             f'SS321H KAMMPROFILE GASKET WITH {_GL} + SS321H OUTER RING', _B16),
         'SIZE : 1" X 300# X 5MM THK,SS321H KAMMPROFILE GASKET WITH GRAPHITE LAYERS ON BOTH SIDES + SS321H OUTER RING,ASME B16.20'),
        # 2" CL300 SS321
        (nps('2"', '300#', 5,
             f'SS321 KAMMPROFILE GASKET WITH {_GL} + SS321 OUTER RING', _B16),
         'SIZE : 2" X 300# X 5MM THK,SS321 KAMMPROFILE GASKET WITH GRAPHITE LAYERS ON BOTH SIDES + SS321 OUTER RING,ASME B16.20'),
        # 10" CL300 SS321
        (nps('10"', '300#', 5,
             f'SS321 KAMMPROFILE GASKET WITH {_GL} + SS321 OUTER RING', _B16),
         'SIZE : 10" X 300# X 5MM THK,SS321 KAMMPROFILE GASKET WITH GRAPHITE LAYERS ON BOTH SIDES + SS321 OUTER RING,ASME B16.20'),
        # --- OD/ID (custom bore, no pressure class) ---
        # 956/982mm × 3mm — no special
        (oid(982, 956, 3, 'SS316 KAMMPROFILE WITH GRAPHITE COATED ON BOTH SIDES'),
         'SIZE : 956MM ID X 982MM OD X 3MM THK,SS316 KAMMPROFILE WITH GRAPHITE COATED ON BOTH SIDES'),
        # 451/372mm × 5mm — core thickness in special, drawing reference in moc
        (oid(451, 372, 5,
             'GROOVED METAL SS316 KAMMPROFILE GASKET WITH GRAPHITE LAYER ON BOTH SIDES (AS PER DRAWING)',
             special='4MM CORE THICKNESS'),
         'SIZE : 372MM ID X 451MM OD X 5MM THK,4MM CORE THICKNESS,GROOVED METAL SS316 KAMMPROFILE GASKET WITH GRAPHITE LAYER ON BOTH SIDES (AS PER DRAWING)'),
        # 410/340mm × 5mm — same spec
        (oid(410, 340, 5,
             'GROOVED METAL SS316 KAMMPROFILE GASKET WITH GRAPHITE LAYER ON BOTH SIDES (AS PER DRAWING)',
             special='4MM CORE THICKNESS'),
         'SIZE : 340MM ID X 410MM OD X 5MM THK,4MM CORE THICKNESS,GROOVED METAL SS316 KAMMPROFILE GASKET WITH GRAPHITE LAYER ON BOTH SIDES (AS PER DRAWING)'),
        # 100/132mm × 4mm — drawing reference in moc, no special
        (oid(132, 100, 4, 'SS316 KAMMPROFILE GASKET WITH GRAPHITE LAYER ON BOTH SIDES (AS PER DRAWING)'),
         'SIZE : 100MM ID X 132MM OD X 4MM THK,SS316 KAMMPROFILE GASKET WITH GRAPHITE LAYER ON BOTH SIDES (AS PER DRAWING)'),
    ]

    for i, (item, expected) in enumerate(cases):
        result = format_description(item)
        assert result == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {expected}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} KAMM formatter cases passed ✓')


def test_kamm_new_formats():
    """New KAMM format variants from CSV ground truth:
    - OD/ID with core thickness annotation and integral/named outer ring
    - NPS with GROOOVED METAL GASKET format (integral / named outer ring)
    - Covering layers: GRAPHITE, PTFE, MICA
    """
    def oid_new(od, id_, thk, core, covering, integral=False, outer_ring=None, core_thk=None, standard=None):
        return {
            'gasket_type': 'KAMM', 'size_type': 'OD_ID',
            'od_mm': od, 'id_mm': id_, 'thickness_mm': thk,
            'kamm_core_material': core, 'kamm_surface_material': covering,
            'kamm_integral_outer_ring': integral, 'sw_outer_ring': outer_ring,
            'kamm_core_thk': core_thk, 'standard': standard,
            'moc': None, 'special': None,
        }

    def nps_new(size, rating, thk, core, covering, integral=False, outer_ring=None, inner_ring=None, standard='ASME B16.20'):
        return {
            'gasket_type': 'KAMM', 'size': size, 'rating': rating, 'thickness_mm': thk,
            'kamm_core_material': core, 'kamm_surface_material': covering,
            'kamm_integral_outer_ring': integral,
            'sw_outer_ring': outer_ring, 'sw_inner_ring': inner_ring,
            'standard': standard, 'size_type': 'NPS', 'moc': None,
        }

    cases = [
        # --- OD/ID with core thickness annotation (CSV ground truth rows 1-2) ---
        (oid_new(988, 956, 4.5, 'SS316L', 'GRAPHITE', core_thk=3.3),
         'SIZE : OD 988MM X ID 956MM X 4.5MM THK (3.3MM CORE THK) KAMMPROFILE SS316L GRAPHITE LAYER ON BOTH SIDES'),

        # --- OD/ID with integral outer ring + core thickness (CSV ground truth row 3) ---
        (oid_new(1216, 1184, 4, 'SS347', 'GRAPHITE', integral=True, core_thk=3),
         'SIZE : OD 1216MM X ID 1184MM X 4MM THK (3MM CORE THK) KAMMPROFILE SS347 GRAPHITE LAYER ON BOTH SIDES + INTEGRAL OUTER RING'),

        # --- OD/ID with PTFE covering layer (CSV ground truth row 11) ---
        (oid_new(1035, 1009, 5, 'SS316L', 'PTFE', core_thk=4),
         'SIZE : OD 1035MM X ID 1009MM X 5MM THK (4MM CORE THK) KAMMPROFILE SS316L PTFE LAYER ON BOTH SIDES'),

        # --- OD/ID with integral outer ring only (no core_thk) ---
        (oid_new(982, 956, 3, 'SS316', 'GRAPHITE', integral=True),
         'SIZE : OD 982MM X ID 956MM X 3MM THK KAMMPROFILE SS316 GRAPHITE LAYER ON BOTH SIDES + INTEGRAL OUTER RING'),

        # --- OD/ID with MICA covering layer ---
        (oid_new(500, 450, 4, 'SS316L', 'MICA', core_thk=3),
         'SIZE : OD 500MM X ID 450MM X 4MM THK (3MM CORE THK) KAMMPROFILE SS316L MICA LAYER ON BOTH SIDES'),

        # --- NPS with integral outer ring → GROOOVED METAL format (CSV ground truth row 6) ---
        (nps_new('24"', '300#', 4.5, 'SS316', 'GRAPHITE', integral=True),
         'SIZE : 24" X 300# X 4.5MM THK, KAMMPROFILE SS316 GROOOVED METAL GASKET WITH GRAPHITE COVERING LAYER ON BOTH SIDES, INTEGRAL OUTER RING, ASME B16.20'),

        # --- NPS with named outer ring (CSV ground truth row 7 pattern) ---
        (nps_new('34"', '300#', 4.5, 'SS316', 'GRAPHITE', outer_ring='SS316', standard='ASME B16.47 (SERIES-B)'),
         'SIZE : 34" X 300# X 4.5MM THK, KAMMPROFILE SS316 GROOOVED METAL GASKET WITH GRAPHITE COVERING LAYER ON BOTH SIDES, SS316 OUTER RING, ASME B16.47 (SERIES-B)'),

        # --- NPS PTFE covering with named outer ring ---
        (nps_new('8"', '600#', 4.5, 'SS316L', 'PTFE', outer_ring='SS316L'),
         'SIZE : 8" X 600# X 4.5MM THK, KAMMPROFILE SS316L GROOOVED METAL GASKET WITH PTFE COVERING LAYER ON BOTH SIDES, SS316L OUTER RING, ASME B16.20'),
    ]

    for i, (item, expected) in enumerate(cases):
        result = format_description(item)
        assert result == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {expected}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} new KAMM format cases passed ✓')


def test_kamm_regex_extraction():
    """Test regex extraction of new KAMM fields: covering layer, rib, core_thk, integral ring."""
    from core.regex_extractor import regex_extract

    # Case 1: FG covering layer → normalized to GRAPHITE; WITH RIB
    r1 = regex_extract('KAMMPROFILE 0.5" 150# SS316 FG WITH RIB ASME B16.20')
    assert r1['gasket_type'] == 'KAMM', f'Expected KAMM, got {r1["gasket_type"]}'
    assert r1['kamm_covering_layer'] == 'GRAPHITE', f'Expected GRAPHITE, got {r1["kamm_covering_layer"]}'
    assert r1['kamm_rib'] == 'WITH RIB', f'Expected WITH RIB, got {r1["kamm_rib"]}'

    # Case 2: Core thickness annotation
    r2 = regex_extract('KAMMPROFILE OD 988MM ID 956MM 4.5MM THK SS316L GRAPHITE (3.3MM CORE THK)')
    assert r2['gasket_type'] == 'KAMM', f'Expected KAMM, got {r2["gasket_type"]}'
    assert r2['kamm_core_thk'] == 3.3, f'Expected 3.3, got {r2["kamm_core_thk"]}'
    assert r2['kamm_covering_layer'] == 'GRAPHITE'

    # Case 3: INTEGRAL OUTER RING detection
    r3 = regex_extract('24" 300# KAMMPROFILE SS316 GRAPHITE WITH INTEGRAL OUTER RING ASME B16.20')
    assert r3['gasket_type'] == 'KAMM', f'Expected KAMM, got {r3["gasket_type"]}'
    assert r3['kamm_integral_outer_ring'] is True, f'Expected True, got {r3["kamm_integral_outer_ring"]}'

    # Case 4: PTFE covering, WITHOUT RIB
    r4 = regex_extract('KAMMPROFILE 6" 150# SS316L PTFE WITHOUT RIB')
    assert r4['kamm_covering_layer'] == 'PTFE', f'Expected PTFE, got {r4["kamm_covering_layer"]}'
    assert r4['kamm_rib'] == 'WITHOUT RIB', f'Expected WITHOUT RIB, got {r4["kamm_rib"]}'

    # Case 5: NON ASB covering
    r5 = regex_extract('KAMMPROFILE 4" 300# SS316 NON ASB')
    assert r5['kamm_covering_layer'] == 'NON ASBESTOS', f'Expected NON ASBESTOS, got {r5["kamm_covering_layer"]}'

    # Case 6: INTEGRAL CENTERING RING → also treated as integral
    r6 = regex_extract('KAMMPROFILE OD 1216MM ID 1184MM 4MM THK SS347 GRAPHITE INTEGRAL CENTERING RING')
    assert r6['kamm_integral_outer_ring'] is True, f'Expected True, got {r6["kamm_integral_outer_ring"]}'

    print('  All 6 KAMM regex extraction cases passed ✓')


def test_softcut_large_bore_rules():
    """Test that apply_rules triggers B16.47 flag for ≥26\" and defaults B16.21 for smaller."""
    # Large bore (48") — B16.47 triggered, series A/B unknown → STATUS_MISSING
    item_lb = {
        'gasket_type': 'SOFT_CUT', 'size': '48"', 'size_norm': '48"',
        'rating': '150#', 'moc': 'REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70',
        'face_type': None, 'standard': None, 'thickness_mm': None, 'quantity': 4,
    }
    result_lb = apply_rules(item_lb)
    assert result_lb['standard'] == 'ASME B16.47', \
        f'Expected ASME B16.47, got {result_lb["standard"]}'
    assert result_lb['status'] == STATUS_MISSING, \
        f'Expected MISSING (series not specified), got {result_lb["status"]}'
    assert any('B16.47' in f and 'Series' in f for f in result_lb['flags']), \
        'Expected B16.47 series flag'

    # Small bore (1.5") — B16.21 defaulted, RF face, 3mm thickness → STATUS_CHECK
    item_sb = {
        'gasket_type': 'SOFT_CUT', 'size': '1.5"', 'size_norm': '1.5"',
        'rating': '150#', 'moc': 'REINFORCED CHLOROPENE RUBBER SHORE A HARDNESS OF 70',
        'face_type': None, 'standard': None, 'thickness_mm': None, 'quantity': 2,
    }
    result_sb = apply_rules(item_sb)
    assert result_sb['standard'] == 'ASME B16.21', \
        f'Expected ASME B16.21, got {result_sb["standard"]}'
    assert result_sb['face_type'] == 'RF', \
        f'Expected RF default for ASME, got {result_sb["face_type"]}'
    assert result_sb['thickness_mm'] == 3, \
        f'Expected 3mm default, got {result_sb["thickness_mm"]}'
    assert result_sb['status'] == STATUS_CHECK, \
        f'Expected CHECK (defaults applied), got {result_sb["status"]}'

    print('  Large bore B16.47 flag ✓  Small bore B16.21 default ✓')


def test_isk_formatter():
    """Test ISK formatter output — STYLE-CS, STYLE-N, FCS, TYPE-D, no-style. No LLM needed."""
    _SET_PGS = ('G10 GASKET WITH UNS S32760 CORE 3MM THK WITH PTFE SPRING ENERGISED SEAL, '
                'G10 SLEEVES, G10 INSULATING WASHER 3MM THK, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK')
    _FCS_SPEC = ('GRE G10 WITH 316 CORE 3MM THK, PRIMARY SEAL PTFE, SECONDARY SEAL MICA, '
                 'SLEEVE GRE G10, INSULATING WASHER G10, METALLIC WASHER 316 3MM THK')
    _TD_SPEC  = ('R24 GRE G10 CORE, SLEEVE GRE G10, INSULATING WASHER G10, '
                 'METALLIC WASHER ZINC PLATED CS WASHER 3MM THK (NON-FIRE SAFE)')

    def cs(size, rating, std):
        return {'gasket_type': 'ISK', 'size': size, 'rating': rating,
                'isk_style': 'STYLE-CS', 'special': _SET_PGS,
                'face_type': 'RF', 'standard': std,
                'isk_standard_explicit': True, 'isk_fire_safety': '', 'moc': None}

    cases = [
        # --- STYLE-CS large bore (PGS COMMANDER EXTREME SET) ---
        # 42" CL150 B16.47 SERIES-A
        (cs('42"', '150#', 'ASME B16.47 (SERIES-A)'),
         'SIZE: 42" X 150#, INSULATING GASKET KIT, STYLE-CS, (SET: G10 GASKET WITH UNS S32760 CORE 3MM THK WITH PTFE SPRING ENERGISED SEAL, G10 SLEEVES, G10 INSULATING WASHER 3MM THK, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK), RF, ASME B16.47 (SERIES-A)'),
        # 42" CL600 B16.47 SERIES-A
        (cs('42"', '600#', 'ASME B16.47 (SERIES-A)'),
         'SIZE: 42" X 600#, INSULATING GASKET KIT, STYLE-CS, (SET: G10 GASKET WITH UNS S32760 CORE 3MM THK WITH PTFE SPRING ENERGISED SEAL, G10 SLEEVES, G10 INSULATING WASHER 3MM THK, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK), RF, ASME B16.47 (SERIES-A)'),
        # 2" CL600 small bore B16.20
        (cs('2"', '600#', 'ASME B16.20'),
         'SIZE: 2" X 600#, INSULATING GASKET KIT, STYLE-CS, (SET: G10 GASKET WITH UNS S32760 CORE 3MM THK WITH PTFE SPRING ENERGISED SEAL, G10 SLEEVES, G10 INSULATING WASHER 3MM THK, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK), RF, ASME B16.20'),
        # 38" B16.47 SERIES-A
        (cs('38"', '150#', 'ASME B16.47 (SERIES-A)'),
         'SIZE: 38" X 150#, INSULATING GASKET KIT, STYLE-CS, (SET: G10 GASKET WITH UNS S32760 CORE 3MM THK WITH PTFE SPRING ENERGISED SEAL, G10 SLEEVES, G10 INSULATING WASHER 3MM THK, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK), RF, ASME B16.47 (SERIES-A)'),
        # 28" B16.47 SERIES-A
        (cs('28"', '150#', 'ASME B16.47 (SERIES-A)'),
         'SIZE: 28" X 150#, INSULATING GASKET KIT, STYLE-CS, (SET: G10 GASKET WITH UNS S32760 CORE 3MM THK WITH PTFE SPRING ENERGISED SEAL, G10 SLEEVES, G10 INSULATING WASHER 3MM THK, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK), RF, ASME B16.47 (SERIES-A)'),
        # 26" B16.47 SERIES-A
        (cs('26"', '150#', 'ASME B16.47 (SERIES-A)'),
         'SIZE: 26" X 150#, INSULATING GASKET KIT, STYLE-CS, (SET: G10 GASKET WITH UNS S32760 CORE 3MM THK WITH PTFE SPRING ENERGISED SEAL, G10 SLEEVES, G10 INSULATING WASHER 3MM THK, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK), RF, ASME B16.47 (SERIES-A)'),
        # 1" no standard (standard=None filtered out)
        (cs('1"', '150#', None),
         'SIZE: 1" X 150#, INSULATING GASKET KIT, STYLE-CS, (SET: G10 GASKET WITH UNS S32760 CORE 3MM THK WITH PTFE SPRING ENERGISED SEAL, G10 SLEEVES, G10 INSULATING WASHER 3MM THK, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK), RF'),
        # --- STYLE-CS with fire safety (GRE G-11 set) ---
        ({'gasket_type': 'ISK', 'size': '42"', 'rating': '150#',
          'isk_style': 'STYLE-CS', 'special': 'GRE (G-11)',
          'face_type': 'RF', 'standard': 'ASME B16.47 (SERIES-A)',
          'isk_standard_explicit': True, 'isk_fire_safety': 'NON FIRE SAFE', 'moc': None},
         'SIZE: 42" X 150#, INSULATING GASKET KIT, STYLE-CS, (SET: GRE (G-11)), RF, ASME B16.47 (SERIES-A), (NON-FIRE SAFE)'),
        # --- STYLE-N ---
        ({'gasket_type': 'ISK', 'size': '8"', 'rating': '300#',
          'isk_style': 'STYLE-N', 'special': 'GRE (G-10)',
          'face_type': 'RF', 'standard': 'ASME B16.5',
          'isk_standard_explicit': False, 'isk_fire_safety': '', 'moc': None},
         'SIZE: 8" X 300#, INSULATING GASKET KIT (STYLE-N) GRE (G-10), RF'),
        # --- FCS style (VCFS TYPE-F pattern — parens like STYLE-N) ---
        ({'gasket_type': 'ISK', 'size': '2"', 'rating': '900#',
          'isk_style': 'FCS', 'special': _FCS_SPEC,
          'face_type': 'RF', 'standard': None,
          'isk_standard_explicit': False, 'isk_fire_safety': 'FIRE SAFE', 'moc': None},
         'SIZE: 2" X 900#, INSULATING GASKET KIT (FCS) GRE G10 WITH 316 CORE 3MM THK, PRIMARY SEAL PTFE, SECONDARY SEAL MICA, SLEEVE GRE G10, INSULATING WASHER G10, METALLIC WASHER 316 3MM THK, RF (FIRE SAFE)'),
        ({'gasket_type': 'ISK', 'size': '3"', 'rating': '1500#',
          'isk_style': 'FCS', 'special': _FCS_SPEC,
          'face_type': 'RF', 'standard': None,
          'isk_standard_explicit': False, 'isk_fire_safety': 'FIRE SAFE', 'moc': None},
         'SIZE: 3" X 1500#, INSULATING GASKET KIT (FCS) GRE G10 WITH 316 CORE 3MM THK, PRIMARY SEAL PTFE, SECONDARY SEAL MICA, SLEEVE GRE G10, INSULATING WASHER G10, METALLIC WASHER 316 3MM THK, RF (FIRE SAFE)'),
        ({'gasket_type': 'ISK', 'size': '6"', 'rating': '900#',
          'isk_style': 'FCS', 'special': _FCS_SPEC,
          'face_type': 'RF', 'standard': None,
          'isk_standard_explicit': False, 'isk_fire_safety': 'FIRE SAFE', 'moc': None},
         'SIZE: 6" X 900#, INSULATING GASKET KIT (FCS) GRE G10 WITH 316 CORE 3MM THK, PRIMARY SEAL PTFE, SECONDARY SEAL MICA, SLEEVE GRE G10, INSULATING WASHER G10, METALLIC WASHER 316 3MM THK, RF (FIRE SAFE)'),
        # --- TYPE-D style — NON-FIRE SAFE embedded in special string ---
        ({'gasket_type': 'ISK', 'size': '2"', 'rating': '1500#',
          'isk_style': 'TYPE-D', 'special': _TD_SPEC,
          'face_type': None, 'standard': None,
          'isk_standard_explicit': False, 'isk_fire_safety': '', 'moc': None},
         'SIZE: 2" X 1500#, INSULATING GASKET KIT (TYPE-D) R24 GRE G10 CORE, SLEEVE GRE G10, INSULATING WASHER G10, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK (NON-FIRE SAFE)'),
        ({'gasket_type': 'ISK', 'size': '2.1/16"', 'rating': '3000#',
          'isk_style': 'TYPE-D', 'special': _TD_SPEC,
          'face_type': None, 'standard': None,
          'isk_standard_explicit': False, 'isk_fire_safety': '', 'moc': None},
         'SIZE: 2.1/16" X 3000#, INSULATING GASKET KIT (TYPE-D) R24 GRE G10 CORE, SLEEVE GRE G10, INSULATING WASHER G10, METALLIC WASHER ZINC PLATED CS WASHER 3MM THK (NON-FIRE SAFE)'),
        # --- No style, NON FIRE SAFE (fire safety attaches to face with space) ---
        ({'gasket_type': 'ISK', 'size': '32"', 'rating': '150#',
          'isk_style': '', 'special': 'GRE (G-11)',
          'face_type': 'RF', 'standard': '',
          'isk_standard_explicit': False, 'isk_fire_safety': 'NON FIRE SAFE', 'moc': None},
         'SIZE: 32" X 150#, INSULATING GASKET KIT, GRE (G-11), RF (NON-FIRE SAFE)'),
        # --- No style, special starts with WITH — space join, no comma ---
        ({'gasket_type': 'ISK', 'size': '1-1/2"', 'rating': '900#',
          'isk_style': '', 'special': 'WITH WASHER & SLEEVE (G-10/11) WITH SS316 CORE, PTFE SS PRESSURE ENERGIZED SPIRAL SPRING',
          'face_type': 'RF', 'standard': '',
          'isk_standard_explicit': False, 'isk_fire_safety': 'NON FIRE SAFE', 'moc': None},
         'SIZE: 1-1/2" X 900#, INSULATING GASKET KIT WITH WASHER & SLEEVE (G-10/11) WITH SS316 CORE, PTFE SS PRESSURE ENERGIZED SPIRAL SPRING, RF (NON-FIRE SAFE)'),
    ]

    for i, (item, expected) in enumerate(cases):
        result = format_description(item)
        assert result == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {expected}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} ISK formatter cases passed ✓')


def test_isk_rtj_formatter():
    """Test ISK_RTJ formatter — STYLE-N with SET spec and TO SUIT standard. No LLM needed."""
    _SET = ('SET:G10 GASKET CORE 4 MM THK WITH PRIMARY SEAL PTFE SPRING ENERGISED RING, '
            'G10 WASHER 3 MM THK & SLEEVES, ZINC PLATED CS WASHER 3 MM THK')

    def isk_rtj(size, rating):
        return {'gasket_type': 'ISK_RTJ', 'size': size, 'rating': rating,
                'isk_style': 'STYLE-N', 'special': _SET,
                'face_type': 'RF', 'standard': 'ASME B16.5',
                'isk_standard_explicit': True, 'isk_fire_safety': '', 'moc': None}

    _suffix = ('(SET:G10 GASKET CORE 4 MM THK WITH PRIMARY SEAL PTFE SPRING ENERGISED RING, '
               'G10 WASHER 3 MM THK & SLEEVES, ZINC PLATED CS WASHER 3 MM THK) '
               'TO SUIT ASME B16.5 (TYPE-RTJ)')

    cases = [
        (isk_rtj('24"', '1500#'),
         f'SIZE: 24" X 1500#, ISK STYLE-N (TYPE F - RF) {_suffix}'),
        (isk_rtj('6"',  '1500#'),
         f'SIZE: 6" X 1500#, ISK STYLE-N (TYPE F - RF) {_suffix}'),
    ]

    for i, (item, expected) in enumerate(cases):
        result = format_description(item)
        assert result == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {expected}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} ISK-RTJ formatter cases passed ✓')


def test_dji_formatter():
    """Test DJI formatter — all patterns: drawing (with/without moc), corrugated,
    ID-first mineral fiber, ID-first face type. No LLM needed."""
    from core.formatter import format_description

    def dji(od, id_, thk, moc, filler='GRAPHITE', special=''):
        return {'gasket_type': 'DJI', 'od_mm': od, 'id_mm': id_,
                'thickness_mm': thk, 'moc': moc, 'dji_filler': filler, 'special': special,
                'dji_face_type': None, 'dji_id_first': False}

    cases = [
        # Drawing-based cases (AS PER DRAWING pattern, OD-first)
        (dji(1430, 1404, 3,   'SOFT IRON',  'GRAPHITE',  'AS PER DRAWING'),
         'SIZE : 1430MM OD X 1404MM ID X 3MM THK, DOUBLE JACKETED, SOFT IRON WITH GRAPHITE FILLER (AS PER DRAWING)'),
        (dji(1310, 1272, 3,   'SOFT IRON',  'GRAPHITE',  'AS PER DRAWING'),
         'SIZE : 1310MM OD X 1272MM ID X 3MM THK, DOUBLE JACKETED, SOFT IRON WITH GRAPHITE FILLER (AS PER DRAWING)'),
        (dji(870,  838,  3,   'SOFT IRON',  'GRAPHITE',  'AS PER DRAWING'),
         'SIZE : 870MM OD X 838MM ID X 3MM THK, DOUBLE JACKETED, SOFT IRON WITH GRAPHITE FILLER (AS PER DRAWING)'),
        (dji(762,  730,  3,   'SOFT IRON',  'GRAPHITE',  'AS PER DRAWING'),
         'SIZE : 762MM OD X 730MM ID X 3MM THK, DOUBLE JACKETED, SOFT IRON WITH GRAPHITE FILLER (AS PER DRAWING)'),
        (dji(610,  578,  3,   'SOFT IRON',  'GRAPHITE',  'AS PER DRAWING'),
         'SIZE : 610MM OD X 578MM ID X 3MM THK, DOUBLE JACKETED, SOFT IRON WITH GRAPHITE FILLER (AS PER DRAWING)'),
        (dji(508,  476,  3,   'SOFT IRON',  'GRAPHITE',  'AS PER DRAWING'),
         'SIZE : 508MM OD X 476MM ID X 3MM THK, DOUBLE JACKETED, SOFT IRON WITH GRAPHITE FILLER (AS PER DRAWING)'),
        # Corrugated type (no drawing reference, OD-first)
        (dji(367,  341,  3.2, 'SS304L', 'CORRUGATED TYPE GRAPHITE', ''),
         'SIZE : 367MM OD X 341MM ID X 3.2MM THK, SS304L DOUBLE JACKETED GASKET WITH CORRUGATED TYPE GRAPHITE FILLER'),
        # Drawing with no moc — filler-only (ASBESTOS FREE material, no explicit jacket)
        ({'gasket_type': 'DJI', 'od_mm': 958, 'id_mm': 858, 'thickness_mm': 3, 'moc': None,
          'dji_filler': 'ASBESTOS FREE', 'special': 'AS PER DRAWING',
          'dji_face_type': None, 'dji_id_first': False},
         'SIZE : 958MM OD X 858MM ID X 3MM THK, DOUBLE JACKETED WITH ASBESTOS FREE (AS PER DRAWING)'),
        # ID-first format — TYPE 3 / mineral fiber configuration (heat exchanger pattern)
        ({'gasket_type': 'DJI', 'od_mm': 300, 'id_mm': 280, 'thickness_mm': 10, 'moc': 'SOFT IRON',
          'dji_filler': 'MINERAL FIBER', 'special': '',
          'dji_face_type': None, 'dji_id_first': True},
         'SIZE : 280MM ID X 300MM OD X 10MM THK, DOUBLE JACKETED,SOFT IRON + MINERAL FIBER FILLER'),
        # ID-first with RF face type (TEFLON jacket / RUBBER filler → roles swapped in GGPL output)
        ({'gasket_type': 'DJI', 'od_mm': 153, 'id_mm': 54, 'thickness_mm': 3, 'moc': 'TEFLON',
          'dji_filler': 'RUBBER', 'special': '',
          'dji_face_type': 'RF', 'dji_id_first': True},
         'SIZE : 54MM ID X 153MM OD X 3MM THK, RUBBER DOUBLE JACKETED GASKET WITH TEFLON FILLER ,RF'),
    ]

    for i, (item, expected) in enumerate(cases):
        result = format_description(item)
        assert result == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {expected}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} DJI formatter cases passed ✓')


def test_dji_regex_extraction():
    """Test regex extraction of new DJI fields: rib, face type, filler normalization,
    structured JACKET/FILLER MATERIAL labels, and ID-first/TYPE 3 detection."""
    from core.regex_extractor import regex_extract

    # Case 1: WITH RIB detection
    r1 = regex_extract('DOUBLE JACKETED GASKET 2" 150# SS316L GRAPHITE WITH RIB ASME B16.20')
    assert r1['gasket_type'] == 'DJI', f'Expected DJI, got {r1["gasket_type"]}'
    assert r1['dji_rib'] == 'WITH RIB', f'Expected WITH RIB, got {r1["dji_rib"]}'

    # Case 2: FG → GRAPHITE normalization + WITHOUT RIB + COPPER jacket
    r2 = regex_extract('DOUBLE JACKET GASKET OD110MM ID101MM 1.5MM THK COPPER FG WITHOUT RIB')
    assert r2['gasket_type'] == 'DJI', f'Expected DJI, got {r2["gasket_type"]}'
    assert r2['dji_filler'] == 'GRAPHITE', f'Expected GRAPHITE (from FG), got {r2["dji_filler"]}'
    assert r2['dji_rib'] == 'WITHOUT RIB', f'Expected WITHOUT RIB, got {r2["dji_rib"]}'
    assert r2['moc'] == 'COPPER', f'Expected COPPER, got {r2["moc"]}'

    # Case 3: Structured JACKET MATERIAL / FILLER MATERIAL labels
    r3 = regex_extract(
        'DOUBLE JACKETED GASKET; JACKET MATERIAL: TEFLON, FILLER MATERIAL: RUBBER, '
        'ID 54MM OD 153MM THK 3.0 MM'
    )
    assert r3['gasket_type'] == 'DJI', f'Expected DJI, got {r3["gasket_type"]}'
    assert r3['moc'] == 'TEFLON', f'Expected TEFLON, got {r3["moc"]}'
    assert r3['dji_filler'] == 'RUBBER', f'Expected RUBBER, got {r3["dji_filler"]}'

    # Case 4: ID-first keyword order → dji_id_first = True
    r4 = regex_extract(
        'DOUBLE JACKETED GASKET ID 280MM OD 300MM THK 3.2MM SOFT IRON AND GRAPHITE'
    )
    assert r4['gasket_type'] == 'DJI', f'Expected DJI, got {r4["gasket_type"]}'
    assert r4['dji_id_first'] is True, f'Expected True (ID before OD), got {r4["dji_id_first"]}'
    assert r4['moc'] == 'SOFT IRON', f'Expected SOFT IRON, got {r4["moc"]}'
    assert r4['dji_filler'] == 'GRAPHITE', f'Expected GRAPHITE, got {r4["dji_filler"]}'

    # Case 5: TYPE 3 marker → dji_id_first = True; FILLER: label extraction
    r5 = regex_extract(
        'DOUBLE JACKETED GASKET OD 300MM ID 280MM THK 10MM TYPE 3 SOFT IRON FILLER: MINERAL FIBER'
    )
    assert r5['gasket_type'] == 'DJI', f'Expected DJI, got {r5["gasket_type"]}'
    assert r5['dji_id_first'] is True, f'Expected True (TYPE 3), got {r5["dji_id_first"]}'
    assert r5['dji_filler'] == 'MINERAL FIBER', f'Expected MINERAL FIBER, got {r5["dji_filler"]}'

    # Case 6: RF face type extraction for DJI
    r6 = regex_extract(
        'DOUBLE JACKETED GASKET ID 54MM OD 153MM THK 3.0MM RUBBER WITH TEFLON FILLER RF'
    )
    assert r6['gasket_type'] == 'DJI', f'Expected DJI, got {r6["gasket_type"]}'
    assert r6['dji_face_type'] == 'RF', f'Expected RF, got {r6["dji_face_type"]}'

    # Case 7: MINERAL FIBER via FILLER: colon-label format
    r7 = regex_extract(
        'DOUBLE JACKETED; OD 300MM ID 280MM 10MM THK; SOFT IRON + FILLER: MINERAL FIBER'
    )
    assert r7['gasket_type'] == 'DJI', f'Expected DJI, got {r7["gasket_type"]}'
    assert r7['dji_filler'] == 'MINERAL FIBER', f'Expected MINERAL FIBER, got {r7["dji_filler"]}'
    assert r7['moc'] == 'SOFT IRON', f'Expected SOFT IRON, got {r7["moc"]}'

    print('  All 7 DJI regex extraction cases passed ✓')


def test_spw_nps_class_format():
    """Regex+rules pipeline for 'N NPS x CLASS R x THK+THK (OUTER & INNER RING)' format.
    No LLM — tests: NPS-suffix size, dual-layer thickness suppression, ring material extraction,
    large-bore B16.47 override, mixed-fraction size decimal conversion.
    Note: filler defaults to GRAPHITE (regex+rules only). LLM may determine FLEXIBLE GRAPHITE
    for SS304 winding per GGPL convention.
    """
    from core.regex_extractor import regex_extract

    def _run(desc):
        rx = regex_extract(desc)
        item = dict(rx)
        item['description'] = desc
        item['quantity'] = 1
        item['uom'] = 'NOS'
        processed = apply_rules(item)
        return format_description(processed)

    cases = [
        # SS316 inner & CS outer — CLASS 150
        ('2 NPS x CLASS 150 x 4.45 THK + 3.2 THK (CS OUTER RING & SS316 INNER RING) ASME B16.20',
         'SIZE : 2" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316 INNER RING & CS OUTER RING, ASME B16.20'),
        # SS316 inner & CS outer — CLASS 600
        ('3 NPS x CLASS 600 x 4.45 THK + 3.2 THK (CS OUTER RING & SS316 INNER RING) ASME B16.20',
         'SIZE : 3" X 600# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316 INNER RING & CS OUTER RING, ASME B16.20'),
        # SS316 inner & outer — CLASS 150
        ('2 NPS x CLASS 150 x 4.45 THK + 3.2 THK (SS316 OUTER RING & SS316 INNER RING) ASME B16.20',
         'SIZE : 2" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
        # SS316 inner & outer — CLASS 300
        ('2 NPS x CLASS 300 x 4.45 THK + 3.2 THK (SS316 OUTER RING & SS316 INNER RING) ASME B16.20',
         'SIZE : 2" X 300# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316 INNER RING & SS316 OUTER RING, ASME B16.20'),
        # SS304 inner & CS outer — CLASS 300 (filler defaults to GRAPHITE without LLM)
        ('2 NPS x CLASS 300 x 4.45 THK + 3.2 THK (CS OUTER RING & SS304 INNER RING) ASME B16.20',
         'SIZE : 2" X 300# X 4.5MM THK, SS304 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS304 INNER RING & CS OUTER RING, ASME B16.20'),
        # SS316L inner & outer — CLASS 300
        ('4 NPS x CLASS 300 x 4.45 THK + 3.2 THK (SS316L OUTER RING & SS316L INNER RING) ASME B16.20',
         'SIZE : 4" X 300# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316L INNER RING & SS316L OUTER RING, ASME B16.20'),
        # SS316L inner & CS outer — CLASS 300
        ('3 NPS x CLASS 300 x 4.45 THK + 3.2 THK (CS OUTER RING & SS316L INNER RING) ASME B16.20',
         'SIZE : 3" X 300# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316L INNER RING & CS OUTER RING, ASME B16.20'),
        # SS321 inner & outer — CLASS 900 (large bore 30" → B16.47)
        ('30 NPS x CLASS 900 x 4.45 THK + 3.2 THK (SS321 OUTER RING & SS321 INNER RING) ASME B16.20',
         'SIZE : 30" X 900# X 4.5MM THK, SS321 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS321 INNER RING & SS321 OUTER RING, ASME B16.47'),
        # SS321 inner & outer — CLASS 900 (16" < 26" → B16.20)
        ('16 NPS x CLASS 900 x 4.45 THK + 3.2 THK (SS321 OUTER RING & SS321 INNER RING) ASME B16.20',
         'SIZE : 16" X 900# X 4.5MM THK, SS321 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS321 INNER RING & SS321 OUTER RING, ASME B16.20'),
        # Mixed fraction size: 1 1/2 NPS → 1.5"
        ('1 1/2 NPS x CLASS 150 x 4.45 THK + 3.2 THK (CS OUTER RING & SS 304 INNER RING) ASME B16.20',
         'SIZE : 1.5" X 150# X 4.5MM THK, SS304 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS304 INNER RING & CS OUTER RING, ASME B16.20'),
        # SS304L inner & CS outer — CLASS 300
        ('2 NPS x CLASS 300 x 4.45 THK + 3.2 THK (CS OUTER RING & SS304L INNER RING) ASME B16.20',
         'SIZE : 2" X 300# X 4.5MM THK, SS304L SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS304L INNER RING & CS OUTER RING, ASME B16.20'),
        # 6 NPS CLASS 150 SS316 inner & CS outer
        ('6 NPS x CLASS 150 x 4.45 THK + 3.2 THK (CS OUTER RING & SS316 INNER RING) ASME B16.20',
         'SIZE : 6" X 150# X 4.5MM THK, SS316 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316 INNER RING & CS OUTER RING, ASME B16.20'),
    ]

    for i, (desc, expected) in enumerate(cases):
        got = _run(desc)
        assert got == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Input:    {desc}'
            f'\n  Expected: {expected}'
            f'\n  Got:      {got}'
        )
    print(f'  All {len(cases)} SPW NPS×CLASS format cases passed ✓')


def test_spw_compact_formats():
    """Compact/abbreviated SPW descriptions: bare decimal size, FLEXICARB brand,
    EPOXY COATED special, CR/IR shared ring material, 300RF rating format."""
    from core.regex_extractor import regex_extract

    def _run(desc):
        rx = regex_extract(desc)
        item = dict(rx)
        item['description'] = desc
        item['quantity'] = 1
        item['uom'] = 'NOS'
        processed = apply_rules(item)
        return format_description(processed), processed

    cases = [
        # Bare decimal size 0.875 → 7/8", FLEXICARB brand → FLEXIBLE GRAPHITE,
        # EPOXY COATED → special, OUTER RING <material after keyword>
        (
            "600 RF ,0.875,API 601 600 # SPIRAL WOUND GRAPHITE FILL 'FLEXICARB'"
            "INNER RING 304 SS OUTER RING CARBON STEEL (EPOXY COATED)",
            'SIZE : 7/8" X 600# X 4.5MM THK, SS304 SPIRAL WOUND GASKET WITH FLEXIBLE GRAPHITE FILLER'
            ' + SS304 INNER RING & CS OUTER RING, EPOXY COATED, ASME B16.20',
        ),
        # CR/IR shared material, 300RF → 300#, large bore 28" → B16.47
        (
            'JOINT SPIRALE 28" 300RF SW CR/IR 316L GRAPHITE ASME B16.20',
            'SIZE : 28" X 300# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH GRAPHITE FILLER'
            ' + SS316L INNER RING & SS316L OUTER RING, ASME B16.47',
        ),
    ]

    for i, (desc, expected) in enumerate(cases):
        got, processed = _run(desc)
        assert got == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Input:    {desc}'
            f'\n  Expected: {expected}'
            f'\n  Got:      {got}'
        )
    print(f'  All {len(cases)} compact SPW format cases passed ✓')


def test_spw_special_egalv():
    """E.GALV / electro-galvanising abbreviation extracted into special field
    and rendered between MOC string and standard in GGPL description."""
    from core.regex_extractor import regex_extract

    def _run(desc):
        rx = regex_extract(desc)
        item = dict(rx)
        item['description'] = desc
        item['quantity'] = 1
        item['uom'] = 'NOS'
        processed = apply_rules(item)
        return format_description(processed), processed

    cases = [
        # Compact customer abbreviation E.GALV
        ('4", GSKT SPIR WND 300# 4.5T, 316L/GRAPH INOUT=316L/CS E.GALV',
         'SIZE : 4" X 300# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316L INNER RING & CS OUTER RING, E.GALV, ASME B16.20'),
        # Written out in full
        ('4" SPW 300# GRAPHITE SS316L/SS316L OUTER RING ELECTRO GALVANIZED',
         'SIZE : 4" X 300# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316L OUTER RING, E.GALV, ASME B16.20'),
        # Hyphenated form
        ('4" SPIRAL WOUND 300# SS316L/GRAPHITE, INNER RING SS316L, ELECTRO-GALVANISED',
         'SIZE : 4" X 300# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH GRAPHITE FILLER + SS316L INNER RING, E.GALV, ASME B16.20'),
    ]

    for i, (desc, expected) in enumerate(cases):
        got, processed = _run(desc)
        assert processed.get('special') == 'E.GALV', (
            f'\nCase {i+1}: special field not set to E.GALV'
            f'\n  Input: {desc}'
            f'\n  Got special: {processed.get("special")!r}'
        )
        assert got == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Input:    {desc}'
            f'\n  Expected: {expected}'
            f'\n  Got:      {got}'
        )
    print(f'  All {len(cases)} E.GALV special-field cases passed ✓')


def test_spw_matl_labels():
    """MATL: field labels, structured catalog descriptions, and inch thickness rounding."""
    from core.regex_extractor import regex_extract

    def _run(desc):
        rx = regex_extract(desc)
        item = dict(rx)
        item['description'] = desc
        item['quantity'] = 1
        item['uom'] = 'NOS'
        processed = apply_rules(item)
        return format_description(processed), processed

    cases = [
        # Structured MATL: labels with FLEX INHIB filler and inch thickness
        (
            '3.GASKET:SPIRAL WOUNDTYPE:SPIRAL WOUND PIPE SIZE:2 IN CLASS:150LB SPIRAL WOUND '
            'THCK:0.175 IN WINDING MATL:316L SS FILLER MATL:GRAPHITE CENTERING RING MATL:316L SS '
            'INNERING RING MATL:316L SS STYLE:FLEXITALLIC SPEC:ASM E B 16.21 SIZE:2 IN 2 IN GASKET '
            '150 CLASS FF SPWD 316L WINDINGS W/FLEX INHIB GRAPHITE FILLER 316L INNER CENTERING RING '
            'ASME B16.5 & B16.20 Manufacturer(MA) - RML',
            'SIZE : 2" X 150# X 4.5MM THK, SS316L SPIRAL WOUND GASKET WITH FLEXIBLE INHIBITED GRAPHITE FILLER + SS316L INNER RING & SS316L OUTER RING, ASME B16.20',
        ),
        # Catalog colon-label style with S-150 rating, zinc-plated inner ring
        (
            'SPIRAL WOUND GASKET CWR S-150 4", Filler: graphite or PTFE, winding: AISI 304 , Inner Ring: zinc-plated carbon steel',
            'SIZE : 4" X 150# X 4.5MM THK, SS304 SPIRAL WOUND GASKET WITH GRAPHITE FILLER + ZINC PLATED CARBON STEEL INNER RING, ASME B16.20',
        ),
    ]

    for i, (desc, expected) in enumerate(cases):
        got, processed = _run(desc)
        assert got == expected, (
            f'\nCase {i+1} failed:'
            f'\n  Input:    {desc[:80]}...'
            f'\n  Expected: {expected}'
            f'\n  Got:      {got}'
        )
    print(f'  All {len(cases)} MATL-label / catalog-label cases passed ✓')


if __name__ == '__main__':
    print('\nRunning pipeline tests...\n')
    tests = [
        test_email_parsing,
        test_rubber_flagged_as_missing,
        test_neoprene_items_ready_or_check,
        test_description_format,
        test_softcut_formatter,
        test_softcut_large_bore_rules,
        test_spw_formatter,
        test_spw_nps_class_format,
        test_spw_compact_formats,
        test_spw_special_egalv,
        test_spw_matl_labels,
        test_rtj_formatter,
        test_kamm_formatter,
        test_kamm_new_formats,
        test_kamm_regex_extraction,
        test_isk_formatter,
        test_isk_rtj_formatter,
        test_dji_formatter,
        test_dji_regex_extraction,
        test_excel_wabag,
        test_lt_excel,
    ]
    passed = 0
    for t in tests:
        try:
            print(f'[TEST] {t.__name__}')
            t()
            passed += 1
        except Exception as e:
            print(f'  FAIL: {e}')
    print(f'\n{passed}/{len(tests)} tests passed')
