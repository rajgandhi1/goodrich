import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from core.document_reader import read_document_smart
from core.formatter import format_description
from core.rules import apply_rules


def test_e2e_customer_enquiry_through_smart_parse():
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    assert api_key, 'OPENAI_API_KEY must be present in .env or environment'

    client = OpenAI(api_key=api_key, timeout=180.0)
    enquiry = """
    Please quote the below gasket items:
    1. 24" 150# EPDM full face soft cut gasket, 7mm thick, ASME B16.21, qty 2 Nos.
    2. 6" 900# spiral wound gasket, SS316L winding, exfoliated expanded graphite filler,
       SS316L inner ring and CS outer ring, ASME B16.20, qty 4 Nos.
    3. BX-155 ring joint gasket, SS316, octagonal, qty 1 Nos.
    """

    extracted, skipped = read_document_smart(enquiry, 'email', client)
    assert skipped == 0
    assert len(extracted) == 3

    processed = []
    for raw in extracted:
        item = apply_rules(raw)
        item['ggpl_description'] = format_description(item)
        processed.append(item)

    descriptions = '\n'.join(item['ggpl_description'] for item in processed)

    assert 'EPDM' in descriptions
    assert 'FF' in descriptions
    assert 'SPIRAL WOUND GASKET' in descriptions
    assert 'SS316L INNER RING' in descriptions
    assert 'CS OUTER RING' in descriptions
    assert 'BX-155' in descriptions
    assert 'SS316' in descriptions
