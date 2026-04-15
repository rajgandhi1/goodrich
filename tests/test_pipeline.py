"""
End-to-end pipeline tests using the WABAG email and L&T Excel as inputs.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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
    '0.5"':  'SIZE : 0.5" X 150# X 3MM THK ,NEOPRENE ,RF ,ASME B16.21',
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


def test_isk_formatter():
    """Test ISK formatter output for common patterns — no LLM needed."""
    cases = [
        # STYLE-CS large bore with fire safety
        {
            'item': {
                'gasket_type': 'ISK', 'size': '42"', 'rating': '150#',
                'isk_style': 'STYLE-CS', 'special': 'GRE (G-11)',
                'face_type': 'RF', 'standard': 'ASME B16.47 (SERIES-A)',
                'isk_standard_explicit': True, 'isk_fire_safety': 'NON FIRE SAFE',
                'moc': None, 'quantity': 1,
            },
            'expected': 'SIZE: 42" X 150#, INSULATING GASKET KIT, STYLE-CS, (SET: GRE (G-11)), RF, ASME B16.47 (SERIES-A), (NON FIRE SAFE)',
        },
        # STYLE-N with spec and no standard (not explicit)
        {
            'item': {
                'gasket_type': 'ISK', 'size': '8"', 'rating': '300#',
                'isk_style': 'STYLE-N', 'special': 'GRE (G-10)',
                'face_type': 'RF', 'standard': 'ASME B16.5',
                'isk_standard_explicit': False, 'isk_fire_safety': '',
                'moc': None, 'quantity': 2,
            },
            'expected': 'SIZE: 8" X 300#, INSULATING GASKET KIT (STYLE-N) GRE (G-10), RF',
        },
        # No style, NON FIRE SAFE (fire safety attaches to face with space, not comma)
        {
            'item': {
                'gasket_type': 'ISK', 'size': '32"', 'rating': '150#',
                'isk_style': '', 'special': 'GRE (G-11)',
                'face_type': 'RF', 'standard': '',
                'isk_standard_explicit': False, 'isk_fire_safety': 'NON FIRE SAFE',
                'moc': None, 'quantity': 4,
            },
            'expected': 'SIZE: 32" X 150#, INSULATING GASKET KIT, GRE (G-11), RF (NON FIRE SAFE)',
        },
    ]

    for i, case in enumerate(cases):
        item = case['item']
        result = format_description(item)
        assert result == case['expected'], (
            f'\nCase {i+1} failed:'
            f'\n  Expected: {case["expected"]}'
            f'\n  Got:      {result}'
        )
    print(f'  All {len(cases)} ISK formatter cases passed ✓')


if __name__ == '__main__':
    print('\nRunning pipeline tests...\n')
    tests = [
        test_email_parsing,
        test_rubber_flagged_as_missing,
        test_neoprene_items_ready_or_check,
        test_description_format,
        test_isk_formatter,
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
