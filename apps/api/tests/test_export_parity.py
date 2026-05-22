from __future__ import annotations

import io
import sys
from pathlib import Path

import openpyxl

from core.quote_exporter import build_quotation_excel
from core.quote_pdf import build_quotation_pdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("app", None)

from app.services.export_parity import compare_excel, compare_pdf_text, extract_pdf_text
from app.services.export_service import _logo_path, build_pdf, build_xlsx


def _sample_items() -> list[dict]:
    return [
        {
            "line_no": 1,
            "customer_sl_no": "C-10",
            "customer_item_code": "ITEM-777",
            "quantity": 2,
            "uom": "NOS",
            "raw_description": '4" 150# CNAF RF gasket 3mm ASME B16.21',
            "ggpl_description": 'GASKET, SIZE : 4", RATING : 150#, TYPE : SOFT CUT, MOC : CNAF, THK : 3 MM',
            "gasket_type": "SOFT_CUT",
            "moc": "CNAF",
            "rating": "150#",
            "status": "ready",
        },
        {
            "line_no": 2,
            "customer_sl_no": "C-11",
            "customer_item_code": "ITEM-888",
            "quantity": 1,
            "uom": "NOS",
            "raw_description": '8" 300# RTJ R45 SS316',
            "ggpl_description": "REGRET - CANNOT PRODUCE",
            "gasket_type": "RTJ",
            "moc": "SS316",
            "rating": "300#",
            "status": "regret",
        },
    ]


def _sample_quote_data(currency: str = "INR") -> dict:
    return {
        "quote_no": f"PARITY-{currency}",
        "quote_date": "16 May 2026",
        "rev_no": "0",
        "rev_date": "",
        "include_customer_sl_no": True,
        "include_customer_item_code": True,
        "buyer_name_address": "ACME Industries\nMumbai",
        "customer_enq_no": "ENQ-123",
        "attention": "Procurement",
        "designation": "Manager",
        "contact_no": "9999999999",
        "email": "buyer@example.com",
        "rep_name": "GGPL Sales",
        "rep_designation": "Sales",
        "rep_contact": "8888888888",
        "rep_email": "sales@goodrichgasket.com",
        "currency": currency,
        "fx_rate": 83 if currency == "USD" else 1,
        "unit_prices": [1000, 0],
        "discount_pct": 5,
        "gst_type": "IGST",
        "gst_pct": 18,
        "price_basis": "FOR BASIS",
        "validity_days": "7",
        "packing": "INCLUSIVE",
        "freight": "INCLUSIVE",
        "payment_terms": "30% ADVANCE & 70% BALANCE BEFORE DISPATCH OF MATERIAL",
        "bank_charges": "TO YOUR ACCOUNT",
        "delivery": "2 weeks",
        "inspection": "Not Applicable",
        "insurance": "TO YOUR ACCOUNT",
        "hsn_code": "84841010",
        "ld_clause": "Not Applicable",
        "cancellation": "Products are manufactured on order.",
        "min_order_value": "Minimum Order Value is INR 10,000.",
        "technical_notes": "Technical note line one.\nTechnical note line two.",
    }


def test_excel_export_service_matches_current_python_exporter():
    items = _sample_items()
    quote_data = _sample_quote_data()
    direct = build_quotation_excel(items, quote_data, logo_path=_logo_path())
    wrapped = build_xlsx(items, quote_data)
    diffs = compare_excel(direct, wrapped)
    assert diffs == []
    workbook = openpyxl.load_workbook(io.BytesIO(direct), data_only=True)
    values = [cell for row in workbook.active.iter_rows(values_only=True) for cell in row]
    assert "C-10" in values
    assert "ITEM-777" in values


def test_pdf_export_service_text_matches_current_python_exporter():
    items = _sample_items()
    quote_data = _sample_quote_data("USD")
    direct = build_quotation_pdf(items, quote_data, logo_path=_logo_path())
    wrapped = build_pdf(items, quote_data)
    matched, expected, actual = compare_pdf_text(direct, wrapped)
    assert matched, f"Expected PDF text:\n{expected}\n\nActual PDF text:\n{actual}"
    text = extract_pdf_text(direct)
    assert "C-10" in text
    assert "ITEM-777" in text
