from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from services.extraction import process_document

from app.db import repo
from app.schemas.quotes import QuotePatch


def run_extraction_job(
    *,
    org_id: str,
    job_id: str,
    source: Any,
    source_type: str,
    api_key: str | None,
    quote_id: str | None = None,
) -> None:
    key = (api_key or os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        repo.update_job(
            org_id,
            job_id,
            status="failed",
            progress=1.0,
            error="OPENAI_API_KEY is required for Smart Parse extraction.",
            message="missing OpenAI API key",
        )
        return

    def progress_cb(done: int, total: int) -> None:
        progress = done / total if total else 0.0
        repo.update_job(org_id, job_id, status="running", progress=progress, message=f"{done}/{total}")

    def on_chunk_items(_chunk_items: list[dict]) -> None:
        # Keep in-flight job records small. Large enquiries can produce thousands
        # of rows, and rewriting that growing JSON payload on every chunk makes
        # both polling and database writes expensive.
        return None

    repo.update_job(org_id, job_id, status="running", progress=0.0, message="Smart Parse started")
    client = OpenAI(api_key=key, timeout=180.0)
    items, skipped_count, error = process_document(
        source,
        source_type,
        client,
        progress_cb=progress_cb,
        on_chunk_items=on_chunk_items,
    )
    if error:
        repo.update_job(
            org_id,
            job_id,
            status="failed",
            progress=1.0,
            skipped_count=skipped_count,
            error=error,
            message="Smart Parse failed",
        )
        return

    if quote_id:
        quote = repo.get_quote(org_id, quote_id)
        if quote:
            repo.update_quote(
                org_id,
                quote_id,
                QuotePatch(items=[*quote.items, *items]),
            )
    repo.update_job(
        org_id,
        job_id,
        status="succeeded",
        progress=1.0,
        items=items,
        skipped_count=skipped_count,
        message="Smart Parse completed",
    )
