import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("app", None)

from app.db.repositories import LocalJsonRepository
from app.schemas.quotes import QuoteCreate, QuotePatch


def test_local_repository_persists_quotes_jobs_and_exports(tmp_path):
    path = tmp_path / "repo.json"
    repo = LocalJsonRepository(path)

    quote = repo.create_quote(
        "org-a",
        "user-a",
        QuoteCreate(
            customer="ACME",
            project_ref="P1",
            items=[{"status": "ready", "line_no": 1}],
            quote_data={"quote_no": "Q-1"},
        ),
    )
    repo.update_quote("org-a", quote.id, QuotePatch(custom_label="Saved workspace"))
    token = repo.save_export(
        "org-a",
        b"pdf-bytes",
        "Q-1.pdf",
        "application/pdf",
        quote_id=quote.id,
        export_type="pdf",
    )
    job = repo.create_job("org-a", "email", quote_id=quote.id)
    repo.update_job("org-a", job.id, status="succeeded", items=[{"line_no": 1}], progress=1)

    restarted = LocalJsonRepository(path)
    restored = restarted.get_quote("org-a", quote.id)
    assert restored is not None
    assert restored.custom_label == "Saved workspace"
    assert restored.stage_meta["exports"][0]["filename"] == "Q-1.pdf"
    assert restarted.get_export(token) == (b"pdf-bytes", "Q-1.pdf", "application/pdf")
    assert restarted.get_job("org-a", job.id).status == "succeeded"


def test_internal_quote_no_does_not_fill_visible_quote_no(tmp_path):
    path = tmp_path / "repo.json"
    repo = LocalJsonRepository(path)

    quote = repo.create_quote(
        "org-a",
        "user-a",
        QuoteCreate(customer="ACME", project_ref="P1", items=[], quote_data={}),
    )

    assert quote.quote_no.startswith("enq-")
    assert quote.quote_data.get("quote_no") is None
