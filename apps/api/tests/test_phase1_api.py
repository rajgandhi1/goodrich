import io
import sys
import uuid
from pathlib import Path

import pytest
import pdfplumber
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("app", None)

from app.main import app


def test_quote_workflow_exports_and_tenant_isolation():
    client = TestClient(app)
    org_id = f"org-workflow-{uuid.uuid4().hex}"
    headers = {"X-Org-Id": org_id, "X-User-Id": "user-a"}
    item = {
        "line_no": 1,
        "quantity": 2,
        "uom": "NOS",
        "raw_description": '4" 150# CNAF RF gasket 3mm ASME B16.21',
        "size": '4"',
        "rating": "150#",
        "moc": "CNAF",
        "gasket_type": "SOFT_CUT",
    }

    created = client.post(
        "/api/v1/quotes",
        headers=headers,
        json={
            "customer": "ACME",
            "project_ref": "P1",
            "items": [item],
            "quote_data": {
                "quote_no": "Q-1",
                "quote_date": "15 May 2026",
                "unit_prices": [100],
            },
        },
    )
    assert created.status_code == 201
    quote_id = created.json()["id"]

    recomputed = client.post(
        f"/api/v1/quotes/{quote_id}/items/bulk-recompute",
        headers=headers,
        json={"indices": [0]},
    )
    assert recomputed.status_code == 200
    assert "SIZE : 4\"" in recomputed.json()[0]["ggpl_description"]

    unapproved_pdf = client.post(f"/api/v1/quotes/{quote_id}/exports/pdf", headers=headers)
    assert unapproved_pdf.status_code == 200

    locked = client.post(
        "/api/v1/quotes",
        headers=headers,
        json={
            "customer": "ACME",
            "project_ref": "P1",
            "items": [{**item, "quantity": 1}],
            "quote_data": {
                "quote_no": "Q-LOW-MARGIN",
                "quote_date": "15 May 2026",
                "unit_prices": [100],
                "cost_prices": [95],
                "minimum_margin_pct": 15,
            },
        },
    )
    assert locked.status_code == 201
    locked_pdf = client.post(f"/api/v1/quotes/{locked.json()['id']}/exports/pdf", headers=headers)
    assert locked_pdf.status_code == 403

    approved = client.patch(
        f"/api/v1/quotes/{quote_id}",
        headers=headers,
        json={"stage_meta": {"approval": {"status": "approved", "decided_by": "approver"}}},
    )
    assert approved.status_code == 200

    pdf = client.post(f"/api/v1/quotes/{quote_id}/exports/pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.json()["content_type"] == "application/pdf"
    preview = client.get(pdf.json()["signed_url"], headers=headers)
    assert preview.status_code == 200
    assert preview.headers["content-disposition"].startswith("attachment")
    with pdfplumber.open(io.BytesIO(preview.content)) as parsed_pdf:
        assert parsed_pdf.pages[0].images
    inline_preview = client.get(f'{pdf.json()["signed_url"]}?disposition=inline', headers=headers)
    assert inline_preview.status_code == 200
    assert inline_preview.headers["content-disposition"].startswith("inline")

    xlsx = client.post(f"/api/v1/quotes/{quote_id}/exports/xlsx", headers=headers)
    assert xlsx.status_code == 200
    assert "spreadsheetml" in xlsx.json()["content_type"]

    advanced = client.post(
        f"/api/v1/quotes/{quote_id}/stage",
        headers=headers,
        json={"stage": "po", "reason": "approved"},
    )
    assert advanced.status_code == 200
    assert advanced.json()["stage"] == "po"

    cross_org = client.get(
        f"/api/v1/quotes/{quote_id}",
        headers={"X-Org-Id": f"{org_id}-other", "X-User-Id": "user-b"},
    )
    assert cross_org.status_code == 404


def test_converter_endpoint_uses_core_converter():
    client = TestClient(app)
    response = client.post(
        "/api/v1/converter/length",
        json={"from_unit": "in", "to_unit": "mm", "value": 2},
    )
    assert response.status_code == 200
    assert response.json()["result"] == 50.8

    rating = client.post(
        "/api/v1/converter/rating",
        json={"from_unit": "class", "to_unit": "pn", "value": 150},
    )
    assert rating.status_code == 200
    assert rating.json()["display"] == "PN 20"


def test_user_roles_are_persisted_and_not_trusted_from_header():
    client = TestClient(app)
    org_id = f"org-users-{uuid.uuid4().hex}"
    user_email = f"estimator-{uuid.uuid4().hex}@example.com"
    spoofed_admin = {"X-Org-Id": org_id, "X-User-Id": "not-admin", "X-User-Role": "admin"}
    denied = client.post(
        "/api/v1/users",
        headers=spoofed_admin,
        json={"name": "Bad Admin", "email": "bad@example.com", "role": "admin", "active": True},
    )
    assert denied.status_code == 403

    admin_headers = {"X-Org-Id": org_id, "X-User-Id": "shashnam@flosil.com"}
    created = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"name": "Estimator", "email": user_email, "role": "sales", "active": True},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "sales"

    promoted = client.patch(
        f"/api/v1/users/{user_email}",
        headers=admin_headers,
        json={"role": "approver"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "approver"


def test_access_settings_are_admin_managed_and_persisted():
    client = TestClient(app)
    org_id = f"org-access-{uuid.uuid4().hex}"
    user_headers = {"X-Org-Id": org_id, "X-User-Id": "not-admin", "X-User-Role": "admin"}
    denied = client.put(
        "/api/v1/access-settings",
        headers=user_headers,
        json={"with_whom_options": ["Sales"], "role_permissions": {"sales": {"view_dashboard": True}}},
    )
    assert denied.status_code == 403

    admin_headers = {"X-Org-Id": org_id, "X-User-Id": "shashnam@flosil.com"}
    saved = client.put(
        "/api/v1/access-settings",
        headers=admin_headers,
        json={
            "with_whom_options": ["Sales", "Technical"],
            "role_permissions": {"sales": {"view_dashboard": True, "edit_quotation": False}},
        },
    )
    assert saved.status_code == 200
    assert saved.json()["with_whom_options"] == ["Sales", "Technical"]

    restored = client.get("/api/v1/access-settings", headers={"X-Org-Id": org_id, "X-User-Id": "sales-user"})
    assert restored.status_code == 200
    assert restored.json()["role_permissions"]["sales"]["view_dashboard"] is True


def test_doc_assistant_upload_session_extracts_txt():
    pytest.importorskip("multipart")
    client = TestClient(app)
    response = client.post(
        "/api/v1/doc-assistant/sessions/upload",
        headers={"X-Org-Id": "org-doc", "X-User-Id": "user-doc"},
        files={"files": ("note.txt", b"Goodrich gasket enquiry text", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["document_names"] == ["note.txt"]

    removed = client.delete(
        f"/api/v1/doc-assistant/sessions/{body['id']}/documents/note.txt",
        headers={"X-Org-Id": "org-doc", "X-User-Id": "user-doc"},
    )
    assert removed.status_code == 200
    assert removed.json()["document_names"] == []


def test_extraction_rejects_pdf_input():
    client = TestClient(app)
    created = client.post(
        "/api/v1/quotes",
        headers={"X-Org-Id": "org-pdf-off", "X-User-Id": "user-pdf-off"},
        json={"customer": "ACME", "project_ref": "P1", "items": [], "quote_data": {}},
    )
    assert created.status_code == 201

    response = client.post(
        "/api/v1/extractions",
        headers={"X-Org-Id": "org-pdf-off", "X-User-Id": "user-pdf-off"},
        json={
            "source_type": "pdf",
            "quote_id": created.json()["id"],
            "text": "pretend pdf text",
        },
    )
    assert response.status_code == 400
    assert "email text and Excel" in response.json()["detail"]
