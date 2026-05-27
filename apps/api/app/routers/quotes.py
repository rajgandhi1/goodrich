from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from core.formatter import format_description
from core.rules import apply_rules

from app.db import repo
from app.deps import CurrentUser, can_approve, get_current_user
from app.schemas.common import APIMessage, SignedUrlResponse, StageHistoryEntry
from app.schemas.quotes import (
    BulkItemsRequest,
    BulkRecomputeRequest,
    QuoteCreate,
    QuotePatch,
    QuoteRead,
    ReprocessTextRequest,
    RfiDraftResponse,
    StageAdvanceRequest,
)
from app.services.approved_quote_cache import cache_final_approved_quote
from app.services.export_service import build_pdf, build_xlsx

router = APIRouter(prefix="/api/v1", tags=["quotes"])


def _quote_or_404(org_id: str, quote_id: str) -> QuoteRead:
    quote = repo.get_quote(org_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


def _is_quote_approved(quote: QuoteRead) -> bool:
    approval = (quote.stage_meta or {}).get("approval") or {}
    return isinstance(approval, dict) and approval.get("status") == "approved"


def _commercial_approval_reasons(quote: QuoteRead) -> list[str]:
    return []


def _require_export_allowed(quote: QuoteRead, user: CurrentUser) -> None:
    if can_approve(user) or _is_quote_approved(quote):
        return
    if not _commercial_approval_reasons(quote):
        return
    raise HTTPException(status_code=403, detail="Quotation must be approved before export")


@router.get("/quotes", response_model=list[QuoteRead])
def list_quotes(summary: bool = False, user: CurrentUser = Depends(get_current_user)) -> list[QuoteRead]:
    quotes = repo.list_quotes(user.org_id)
    if summary:
        return [quote.model_copy(update={"items": []}) for quote in quotes]
    return quotes


@router.post("/quotes", response_model=QuoteRead, status_code=201)
def create_quote(payload: QuoteCreate, user: CurrentUser = Depends(get_current_user)) -> QuoteRead:
    return repo.create_quote(user.org_id, user.user_id, payload)


@router.get("/quotes/{quote_id}", response_model=QuoteRead)
def get_quote(quote_id: str, user: CurrentUser = Depends(get_current_user)) -> QuoteRead:
    return _quote_or_404(user.org_id, quote_id)


@router.patch("/quotes/{quote_id}", response_model=QuoteRead)
def patch_quote(
    quote_id: str,
    payload: QuotePatch,
    user: CurrentUser = Depends(get_current_user),
) -> QuoteRead:
    quote = repo.update_quote(user.org_id, quote_id, payload)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


@router.delete("/quotes/{quote_id}", response_model=APIMessage)
def delete_quote(quote_id: str, user: CurrentUser = Depends(get_current_user)) -> APIMessage:
    if not repo.delete_quote(user.org_id, quote_id):
        raise HTTPException(status_code=404, detail="Quote not found")
    return APIMessage(message="deleted")


@router.post("/quotes/{quote_id}/items/bulk", response_model=QuoteRead)
def bulk_items(
    quote_id: str,
    payload: BulkItemsRequest,
    user: CurrentUser = Depends(get_current_user),
) -> QuoteRead:
    quote = _quote_or_404(user.org_id, quote_id)
    items = [dict(item) for item in quote.items]
    for index in sorted(set(payload.delete_indices), reverse=True):
        if 0 <= index < len(items):
            items.pop(index)
    for patch in payload.patches:
        if patch.index < 0:
            raise HTTPException(status_code=400, detail="Patch index cannot be negative")
        while patch.index >= len(items):
            items.append({})
        items[patch.index].update(patch.values)
    updated = repo.update_quote(user.org_id, quote_id, QuotePatch(items=items))
    if not updated:
        raise HTTPException(status_code=404, detail="Quote not found")
    return updated


@router.post("/quotes/{quote_id}/items/bulk-recompute", response_model=list[dict])
def bulk_recompute(
    quote_id: str,
    payload: BulkRecomputeRequest,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    quote = _quote_or_404(user.org_id, quote_id)
    items = [dict(item) for item in quote.items]
    if payload.rows is not None:
        target_indices = list(range(len(payload.rows)))
        source_rows = payload.rows
    else:
        target_indices = payload.indices if payload.indices is not None else list(range(len(items)))
        source_rows = [items[i] for i in target_indices if 0 <= i < len(items)]

    recomputed: list[dict] = []
    for row in source_rows:
        item = apply_rules(dict(row))
        item["ggpl_description"] = format_description(item)
        recomputed.append(item)

    if payload.rows is None:
        for index, item in zip(target_indices, recomputed):
            if 0 <= index < len(items):
                items[index] = item
        repo.update_quote(user.org_id, quote_id, QuotePatch(items=items))
    return recomputed


@router.post("/quotes/{quote_id}/items/reprocess-text", response_model=list[dict])
def reprocess_text(
    quote_id: str,
    payload: ReprocessTextRequest,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    _quote_or_404(user.org_id, quote_id)
    if not payload.descriptions:
        return []
    from app.services.extraction_runner import run_extraction_job

    job = repo.create_job(user.org_id, payload.source_type, quote_id=quote_id)
    run_extraction_job(
        org_id=user.org_id,
        job_id=job.id,
        source="\n".join(payload.descriptions),
        source_type=payload.source_type,
        api_key=payload.api_key,
        quote_id=None,
    )
    finished = repo.get_job(user.org_id, job.id)
    if not finished or finished.status == "failed":
        raise HTTPException(status_code=400, detail=(finished.error if finished else "Reprocess failed"))
    return finished.items


@router.post("/quotes/{quote_id}/rfi-draft", response_model=RfiDraftResponse)
def rfi_draft(quote_id: str, user: CurrentUser = Depends(get_current_user)) -> RfiDraftResponse:
    quote = _quote_or_404(user.org_id, quote_id)
    groups: dict[str, list[int]] = {}
    for idx, item in enumerate(quote.items, start=1):
        for flag in item.get("flags") or []:
            groups.setdefault(str(flag), []).append(idx)
    lines = ["To proceed with the quote, kindly clarify:", ""]
    for flag, indices in groups.items():
        lines.append(f"- Lines {', '.join(map(str, indices))}: {flag}")
    return RfiDraftResponse(text="\n".join(lines).strip(), groups=groups)


@router.post("/quotes/{quote_id}/exports/pdf", response_model=SignedUrlResponse)
def export_pdf(
    quote_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> SignedUrlResponse:
    quote = _quote_or_404(user.org_id, quote_id)
    _require_export_allowed(quote, user)
    content = build_pdf(quote.items, quote.quote_data)
    filename = f"{(quote.quote_no or 'quotation').replace('/', '-')}.pdf"
    token = repo.save_export(user.org_id, content, filename, "application/pdf", quote_id=quote_id, export_type="pdf")
    return SignedUrlResponse(
        signed_url=str(request.url_for("download_export", token=token)),
        filename=filename,
        content_type="application/pdf",
    )


@router.post("/quotes/{quote_id}/exports/xlsx", response_model=SignedUrlResponse)
def export_xlsx(
    quote_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> SignedUrlResponse:
    quote = _quote_or_404(user.org_id, quote_id)
    _require_export_allowed(quote, user)
    content = build_xlsx(quote.items, quote.quote_data)
    filename = f"{(quote.quote_no or 'quotation').replace('/', '-')}.xlsx"
    token = repo.save_export(
        user.org_id,
        content,
        filename,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        quote_id=quote_id,
        export_type="xlsx",
    )
    return SignedUrlResponse(
        signed_url=str(request.url_for("download_export", token=token)),
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/exports/{token}", name="download_export")
def download_export(token: str, disposition: str = "attachment") -> Response:
    row = repo.get_export(token)
    if not row:
        raise HTTPException(status_code=404, detail="Export not found")
    content, filename, content_type = row
    content_disposition = "inline" if disposition == "inline" else "attachment"
    return Response(
        content,
        media_type=content_type,
        headers={"Content-Disposition": f'{content_disposition}; filename="{filename}"'},
    )


@router.post("/quotes/{quote_id}/stage", response_model=QuoteRead)
def advance_stage(
    quote_id: str,
    payload: StageAdvanceRequest,
    user: CurrentUser = Depends(get_current_user),
) -> QuoteRead:
    current = _quote_or_404(user.org_id, quote_id)
    if payload.stage == "sent" and not (can_approve(user) or _is_quote_approved(current)):
        raise HTTPException(status_code=403, detail="Quotation must be approved before it can be marked sent")
    quote = repo.advance_stage(
        user.org_id,
        quote_id,
        payload.stage,
        user.user_id,
        reason=payload.reason,
        metadata=payload.metadata,
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.stage == "po":
        cache_final_approved_quote(quote)
    return quote


@router.get("/quotes/{quote_id}/history", response_model=list[StageHistoryEntry])
def quote_history(quote_id: str, user: CurrentUser = Depends(get_current_user)) -> list[StageHistoryEntry]:
    return _quote_or_404(user.org_id, quote_id).stage_history
