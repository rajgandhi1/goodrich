import io
import os
import sys

import pytest
from dotenv import load_dotenv
from openai import OpenAI
from openpyxl import Workbook

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from core.document_reader import _excel_to_text, _split_into_chunks, read_document_smart
from core.formatter import format_description
from core.rules import STATUS_CHECK, STATUS_MISSING, STATUS_READY, apply_rules


@pytest.fixture(scope='session')
def openai_client():
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    assert api_key, 'OPENAI_API_KEY must be present in .env or environment'
    return OpenAI(api_key=api_key, timeout=180.0)


def _run_pipeline(source, source_type, openai_client):
    extracted, skipped = read_document_smart(source, source_type, openai_client)
    assert skipped == 0
    assert extracted

    processed = []
    for raw in extracted:
        item = apply_rules(raw)
        item['ggpl_description'] = format_description(item)
        processed.append(item)
    return processed


def _first(items, gasket_type):
    return next((item for item in items if item.get('gasket_type') == gasket_type), None)


def test_smart_parse_email_pipeline_extracts_and_formats(openai_client):
    enquiry = """
    Sl No | Description | Qty | UOM
    1 | 4" 150# CNAF RF gasket 3mm thick ASME B16.21 | 2 | Nos
    2 | 2" Class 300 spiral wound gasket, SS316 winding, graphite filler, SS316 inner ring, CS outer ring, ASME B16.20 | 3 | Nos
    3 | Ring joint gasket R-46 octagonal, MOC: Inconel 625, ASME B16.20 | 1 | Nos
    4 | Double jacketed gasket OD 300mm ID 280mm 3mm thick, soft iron jacket with graphite filler | 2 | Nos
    5 | 2" 600# insulating gasket kit STYLE-CS RF GRE G10 with PTFE seal | 1 | Set
    """

    items = _run_pipeline(enquiry, 'email', openai_client)

    assert len(items) == 5
    assert all(item['status'] in (STATUS_READY, STATUS_CHECK, STATUS_MISSING) for item in items)

    soft_cut = _first(items, 'SOFT_CUT')
    assert soft_cut is not None
    assert soft_cut['moc'] == 'CNAF'
    assert 'SIZE : 4" X 150#' in soft_cut['ggpl_description']
    assert 'ASME B16.21' in soft_cut['ggpl_description']

    spiral = _first(items, 'SPIRAL_WOUND')
    assert spiral is not None
    assert spiral['sw_winding_material'] == 'SS316'
    assert spiral['sw_inner_ring'] == 'SS316'
    assert spiral['sw_outer_ring'] == 'CS'
    assert 'SPIRAL WOUND GASKET' in spiral['ggpl_description']
    assert 'ASME B16.20' in spiral['ggpl_description']

    rtj = _first(items, 'RTJ')
    assert rtj is not None
    assert rtj['ring_no'] == 'R-46'
    assert 'INCONEL 625' in rtj['ggpl_description']

    dji = _first(items, 'DJI')
    assert dji is not None
    assert dji['od_mm'] == 300
    assert dji['id_mm'] == 280
    assert 'DOUBLE JACKET' in dji['ggpl_description']

    isk = _first(items, 'ISK')
    assert isk is not None
    assert 'INSULATING GASKET KIT' in isk['ggpl_description']


def test_smart_parse_flags_ambiguous_rubber(openai_client):
    enquiry = 'Gasket - Rubber - 6" PN10, Qty 4 Nos'

    items = _run_pipeline(enquiry, 'email', openai_client)

    assert len(items) == 1
    item = items[0]
    assert item['gasket_type'] == 'SOFT_CUT'
    assert item['status'] == STATUS_MISSING
    assert any('rubber' in flag.lower() or 'moc' in flag.lower() for flag in item['flags'])


def test_plug_gasket_does_not_default_or_print_face_type():
    item = apply_rules({
        'raw_description': '2" 150# plug gasket SS316 4.5mm',
        'gasket_type': 'SOFT_CUT',
        'size': '2"',
        'rating': '150#',
        'moc': 'SS316',
        'thickness_mm': 4.5,
        'quantity': 1,
    })
    item['ggpl_description'] = format_description(item)

    assert item['gasket_type'] == 'PLUG_GASKET'
    assert 'PLUG GASKET' in item['ggpl_description']
    assert 'RF' not in item['ggpl_description']
    assert 'FF' not in item['ggpl_description']


def test_smart_parse_excel_pipeline(openai_client):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Enquiry'
    ws.append(['Line', 'Description', 'Quantity', 'UOM'])
    ws.append([1, '1" 150# neoprene RF gasket 3mm ASME B16.21', 10, 'Nos'])
    ws.append([2, '6" 300# spiral wound gasket SS316 winding graphite filler CS outer ring ASME B16.20', 5, 'Nos'])

    buf = io.BytesIO()
    wb.save(buf)

    items = _run_pipeline(buf.getvalue(), 'excel', openai_client)

    assert len(items) == 2
    assert any(item.get('gasket_type') == 'SOFT_CUT' and item.get('moc') == 'NEOPRENE' for item in items)
    assert any(item.get('gasket_type') == 'SPIRAL_WOUND' and item.get('sw_outer_ring') == 'CS' for item in items)


def test_excel_2000_rows_are_not_truncated_before_llm():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Large Enquiry'
    ws.append(['Line', 'Description', 'Quantity', 'UOM'])
    for i in range(1, 2001):
        ws.append([i, f'{i % 24 + 1}" 150# CNAF RF gasket 3mm ASME B16.21', 1, 'Nos'])

    buf = io.BytesIO()
    wb.save(buf)

    text, was_truncated, row_count = _excel_to_text(buf.getvalue())
    chunks = _split_into_chunks(text)

    assert row_count == 2000
    assert was_truncated is False
    assert len(chunks) >= 67
    assert 'source_sheet' in chunks[0]
    assert 'source_row' in chunks[0]
    assert 'source_index' in chunks[0]
