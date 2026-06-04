from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from core.formatter import format_description
from core.rules import apply_rules

from app.db import repo
from app.deps import CurrentUser, can_approve, can_role, get_current_user, require_capability
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
from app.services.quote_rules import (
    QuoteConflictError,
    QuoteValidationError,
    normalize_identity,
    po_snapshot,
    quote_summary,
    workflow_transition_blockers,
)

router = APIRouter(prefix="/api/v1", tags=["quotes"])


READ_CAPABILITIES = {"view_enquiry", "view_material_planning", "view_quotation", "view_purchase_orders", "view_history"}
SALES_QUOTE_DATA_FIELDS = {
    "buyer_name_address",
    "buyer_name",
    "buyer_address_line1",
    "buyer_address_line2",
    "buyer_city",
    "buyer_state",
    "buyer_pin_code",
    "buyer_country",
    "customer_enq_no",
    "attention",
    "designation",
    "contact_no",
    "mobile_no",
    "telephone_no",
    "email",
    "sales_notes",
    "technical_notes",
}
SALES_STAGE_META_FIELDS = {
    "sales_notes",
    "country",
    "city",
    "epc_name",
    "bid_type",
    "market_type",
    "outlook_thread",
    "activity_log",
}
OWNER_STAGE_META_FIELDS = {"owner_id", "owner_name", "owner_email", "owner_role"}
MATERIAL_PHASE1_FIELDS = {"material_breakdown", "material_inputs", "material_breakdown_updated_at"}
MATERIAL_PHASE2_FIELDS = {
    "material_plan",
    "material_plan_status",
    "material_plan_started_at",
    "material_plan_started_by",
    "material_plan_updated_at",
    "material_plan_submitted_at",
    "material_plan_submitted_by",
    "material_plan_finished_at",
    "material_plan_finished_by",
}
EXTRACTION_SUMMARY_FIELDS = {"extraction_summary", "extraction_summary_rows", "extraction_summary_notes"}
SYSTEM_STAGE_META_FIELDS = {"material_plan_stale", "material_plan_stale_at"}


def _repo_visibility_kwargs(user: CurrentUser) -> dict:
    return {
        "viewer_id": user.user_id,
        "viewer_name": user.name,
        "viewer_email": user.email,
        "is_admin": user.role == "admin",
    }


def _can_read_quote(user: CurrentUser, quote: QuoteRead) -> bool:
    if quote.stage == "po":
        return any(can_role(user, capability) for capability in {"view_purchase_orders", "view_quotation", "view_history"})
    if quote.stage in {"quote_prep", "repricing", "sent"}:
        return any(can_role(user, capability) for capability in {"view_quotation", "view_purchase_orders", "view_history"})
    return any(can_role(user, capability) for capability in {"view_enquiry", "view_material_planning", "view_history"})


def _visible_quotes(user: CurrentUser) -> list[QuoteRead]:
    _require_any_capability(user, READ_CAPABILITIES)
    return [
        quote
        for quote in repo.list_quotes(user.org_id, **_repo_visibility_kwargs(user))
        if _can_read_quote(user, quote)
    ]


def _quote_or_404(user: CurrentUser, quote_id: str, *, require_read: bool = True) -> QuoteRead:
    quote = repo.get_quote(user.org_id, quote_id, **_repo_visibility_kwargs(user))
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if require_read and not _can_read_quote(user, quote):
        raise HTTPException(status_code=403, detail="You do not have permission to view this record")
    return quote


def _changed_keys(current: dict, proposed: dict) -> set[str]:
    return {key for key in set(current) | set(proposed) if current.get(key) != proposed.get(key)}


def _canonical_owner_metadata(stage_meta: dict, current: QuoteRead | None, user: CurrentUser) -> dict:
    result = dict(stage_meta or {})
    owner_id = normalize_identity(result.get("owner_id"))
    current_owner_id = normalize_identity((current.stage_meta or {}).get("owner_id")) if current else ""
    if not owner_id:
        if "owner_id" in result:
            for key in OWNER_STAGE_META_FIELDS:
                result.pop(key, None)
        return result
    owner_changed = owner_id != current_owner_id
    if owner_changed and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can assign or reassign records")
    users = repo.list_app_users(user.org_id)
    owner = next(
        (
            row
            for row in users
            if row.active and owner_id in {normalize_identity(row.id), normalize_identity(row.email)}
        ),
        None,
    )
    if not owner:
        if owner_changed:
            raise HTTPException(status_code=400, detail="Assign the record to an active app user")
        result["owner_id"] = owner_id
        return result
    result.update({"owner_id": owner.id, "owner_name": owner.name, "owner_email": owner.email, "owner_role": owner.role})
    return result


def _normalize_create_payload(payload: QuoteCreate, user: CurrentUser) -> QuoteCreate:
    stage_meta = dict(payload.stage_meta or {})
    source_id = str(stage_meta.get("source_enquiry_id") or "").strip()
    if source_id:
        _quote_or_404(user, source_id)
        return payload.model_copy(update={"stage_meta": stage_meta})
    if stage_meta.get("owner_id"):
        requested_owner = normalize_identity(stage_meta.get("owner_id"))
        current_aliases = {normalize_identity(user.user_id), normalize_identity(user.email), normalize_identity(user.name)}
        if user.role != "admin" and requested_owner not in current_aliases:
            raise HTTPException(status_code=403, detail="Only admin users can assign a new record to another user")
        if user.role != "admin":
            stage_meta["owner_id"] = user.user_id
            return payload.model_copy(update={"stage_meta": stage_meta})
        stage_meta = _canonical_owner_metadata(stage_meta, None, user)
    return payload.model_copy(update={"stage_meta": stage_meta})


def _require_patch_capabilities(user: CurrentUser, current: QuoteRead, payload: QuotePatch) -> QuotePatch:
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if "stage" in changes:
        raise HTTPException(status_code=400, detail="Use the workflow stage endpoint to change stage")
    for field in {"customer", "project_ref", "custom_label", "quote_no"} & changes.keys():
        _require_any_capability(user, {"edit_sales_details", "edit_quotation"})
    if "items" in changes:
        if current.stage == "po" and (changes["items"] or []) != current.items:
            raise HTTPException(status_code=409, detail="Purchase order line items are locked after PO receipt")
        require_capability(user, "edit_line_items")
    if "quote_data" in changes:
        changed_quote_data = _changed_keys(current.quote_data or {}, changes["quote_data"] or {})
        if changed_quote_data - SALES_QUOTE_DATA_FIELDS:
            require_capability(user, "edit_quotation")
        elif changed_quote_data:
            _require_any_capability(user, {"edit_sales_details", "edit_quotation"})
    if "stage_meta" not in changes:
        return payload
    submitted_meta = dict(changes["stage_meta"] or {})
    next_meta = {**(current.stage_meta or {}), **submitted_meta}
    for key in SYSTEM_STAGE_META_FIELDS:
        if key in (current.stage_meta or {}):
            next_meta[key] = (current.stage_meta or {})[key]
        else:
            next_meta.pop(key, None)
    next_meta = _canonical_owner_metadata(next_meta, current, user)
    changed_meta = _changed_keys(current.stage_meta or {}, next_meta)
    if changed_meta & EXTRACTION_SUMMARY_FIELDS:
        require_capability(user, "edit_line_items")
    if changed_meta & OWNER_STAGE_META_FIELDS and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can assign or reassign records")
    if changed_meta & MATERIAL_PHASE1_FIELDS:
        require_capability(user, "edit_workflow")
    if changed_meta & MATERIAL_PHASE2_FIELDS:
        require_capability(user, "edit_material_phase2")
    approval_changed = "approval" in changed_meta
    if approval_changed:
        approval = next_meta.get("approval") if isinstance(next_meta.get("approval"), dict) else {}
        if approval.get("status") in {"approved", "rejected"}:
            if not can_approve(user):
                raise HTTPException(status_code=403, detail="Only approvers can approve or reject quotations")
        else:
            require_capability(user, "edit_quotation")
    handled = (
        SALES_STAGE_META_FIELDS
        | OWNER_STAGE_META_FIELDS
        | MATERIAL_PHASE1_FIELDS
        | MATERIAL_PHASE2_FIELDS
        | EXTRACTION_SUMMARY_FIELDS
        | SYSTEM_STAGE_META_FIELDS
        | {"approval"}
    )
    if changed_meta - handled:
        require_capability(user, "edit_workflow")
    elif changed_meta & SALES_STAGE_META_FIELDS:
        _require_any_capability(user, {"edit_sales_details", "edit_workflow", "edit_quotation"})
    return payload.model_copy(update={"stage_meta": next_meta})


def _raise_repo_error(exc: Exception) -> None:
    if isinstance(exc, QuoteConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, QuoteValidationError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


def _is_quote_approved(quote: QuoteRead) -> bool:
    approval = (quote.stage_meta or {}).get("approval") or {}
    return isinstance(approval, dict) and approval.get("status") == "approved"


def _commercial_approval_reasons(quote: QuoteRead) -> list[str]:
    data = quote.quote_data or {}
    unit_prices = data.get("unit_prices") if isinstance(data.get("unit_prices"), list) else []
    cost_prices = data.get("cost_prices") if isinstance(data.get("cost_prices"), list) else []
    minimum_margin = data.get("minimum_margin_pct")
    try:
        minimum_margin_pct = float(minimum_margin)
    except (TypeError, ValueError):
        minimum_margin_pct = 0
    reasons: list[str] = []
    if minimum_margin_pct > 0:
        for index, cost in enumerate(cost_prices):
            try:
                cost_value = float(cost or 0)
                unit_value = float(unit_prices[index] or 0) if index < len(unit_prices) else 0
            except (TypeError, ValueError):
                continue
            if cost_value > 0 and unit_value > 0:
                margin_pct = ((unit_value - cost_value) / unit_value) * 100
                if margin_pct < minimum_margin_pct:
                    reasons.append(f"Line {index + 1} margin {margin_pct:.1f}% is below {minimum_margin_pct:.1f}%")
    return reasons


def _require_export_allowed(quote: QuoteRead, user: CurrentUser) -> None:
    require_capability(user, "export_quotes")
    if can_approve(user) or _is_quote_approved(quote):
        return
    if not _commercial_approval_reasons(quote):
        return
    raise HTTPException(status_code=403, detail="Quotation must be approved before export")


def _require_any_capability(user: CurrentUser, capabilities: set[str]) -> None:
    if not any(can_role(user, capability) for capability in capabilities):
        raise HTTPException(status_code=403, detail="You do not have permission for this action")


@router.get("/quotes", response_model=list[QuoteRead])
def list_quotes(summary: bool = False, user: CurrentUser = Depends(get_current_user)) -> list[QuoteRead]:
    quotes = _visible_quotes(user)
    if summary:
        return [quote_summary(quote) for quote in quotes]
    return quotes


@router.get("/quotes/search", response_model=list[QuoteRead])
def search_quotes(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    include_item_descriptions: bool = False,
    user: CurrentUser = Depends(get_current_user),
) -> list[QuoteRead]:
    term = q.strip().lower()
    if not term:
        return []
    matches: list[QuoteRead] = []
    for quote in _visible_quotes(user):
        stage_meta = quote.stage_meta or {}
        values = [
            quote.quote_no,
            quote.customer,
            quote.project_ref,
            quote.custom_label,
            stage_meta.get("owner_id"),
            stage_meta.get("owner_name"),
            stage_meta.get("owner_email"),
            stage_meta.get("enquiry_stage"),
            quote.stage,
            quote.quote_data.get("quote_no"),
            quote.quote_data.get("customer_enq_no"),
            quote.quote_data.get("po_no"),
        ]
        if include_item_descriptions:
            values.extend(item.get("raw_description") for item in quote.items)
            values.extend(item.get("ggpl_description") for item in quote.items)
        if any(term in str(value or "").lower() for value in values):
            matches.append(quote_summary(quote))
        if len(matches) >= limit:
            break
    return matches


@router.post("/quotes", response_model=QuoteRead, status_code=201)
def create_quote(payload: QuoteCreate, user: CurrentUser = Depends(get_current_user)) -> QuoteRead:
    require_capability(user, "create_enquiry")
    try:
        return repo.create_quote(user.org_id, user.user_id, _normalize_create_payload(payload, user))
    except (QuoteConflictError, QuoteValidationError) as exc:
        _raise_repo_error(exc)
        raise


@router.get("/quotes/{quote_id}", response_model=QuoteRead)
def get_quote(quote_id: str, user: CurrentUser = Depends(get_current_user)) -> QuoteRead:
    return _quote_or_404(user, quote_id)


@router.patch("/quotes/{quote_id}", response_model=QuoteRead)
def patch_quote(
    quote_id: str,
    payload: QuotePatch,
    user: CurrentUser = Depends(get_current_user),
) -> QuoteRead:
    current = _quote_or_404(user, quote_id)
    authorized_payload = _require_patch_capabilities(user, current, payload)
    try:
        quote = repo.update_quote(user.org_id, quote_id, authorized_payload, actor_id=user.user_id)
    except (QuoteConflictError, QuoteValidationError) as exc:
        _raise_repo_error(exc)
        raise
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


@router.delete("/quotes/{quote_id}", response_model=APIMessage)
def delete_quote(quote_id: str, user: CurrentUser = Depends(get_current_user)) -> APIMessage:
    _require_any_capability(user, {"edit_workflow", "edit_quotation"})
    quote = _quote_or_404(user, quote_id)
    if (quote.stage_meta or {}).get("linked_quote_id") or (quote.stage_meta or {}).get("source_enquiry_id"):
        raise HTTPException(status_code=409, detail="Linked workflow records cannot be hard-deleted")
    if quote.stage not in {"initial", "review"}:
        raise HTTPException(status_code=409, detail="Only unlinked enquiry drafts can be hard-deleted")
    if not repo.delete_quote(user.org_id, quote_id):
        raise HTTPException(status_code=404, detail="Quote not found")
    return APIMessage(message="deleted")


@router.post("/quotes/{quote_id}/items/bulk", response_model=QuoteRead)
def bulk_items(
    quote_id: str,
    payload: BulkItemsRequest,
    user: CurrentUser = Depends(get_current_user),
) -> QuoteRead:
    require_capability(user, "edit_line_items")
    quote = _quote_or_404(user, quote_id)
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
    try:
        updated = repo.update_quote(
            user.org_id,
            quote_id,
            QuotePatch(items=items, expected_version=payload.expected_version),
            actor_id=user.user_id,
        )
    except (QuoteConflictError, QuoteValidationError) as exc:
        _raise_repo_error(exc)
        raise
    if not updated:
        raise HTTPException(status_code=404, detail="Quote not found")
    return updated


@router.post("/quotes/{quote_id}/items/bulk-recompute", response_model=list[dict])
def bulk_recompute(
    quote_id: str,
    payload: BulkRecomputeRequest,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    require_capability(user, "edit_line_items")
    quote = _quote_or_404(user, quote_id)
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
        try:
            repo.update_quote(
                user.org_id,
                quote_id,
                QuotePatch(items=items, expected_version=payload.expected_version),
                actor_id=user.user_id,
            )
        except (QuoteConflictError, QuoteValidationError) as exc:
            _raise_repo_error(exc)
            raise
    return recomputed


@router.post("/quotes/{quote_id}/items/reprocess-text", response_model=list[dict])
def reprocess_text(
    quote_id: str,
    payload: ReprocessTextRequest,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    require_capability(user, "edit_line_items")
    _quote_or_404(user, quote_id)
    if not payload.descriptions:
        return []
    from app.services.extraction_runner import run_extraction_job

    job = repo.create_job(user.org_id, payload.source_type, quote_id=quote_id, created_by=user.user_id)
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
    _require_any_capability(user, {"view_enquiry", "view_quotation"})
    quote = _quote_or_404(user, quote_id)
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
    quote = _quote_or_404(user, quote_id)
    _require_export_allowed(quote, user)
    content = build_pdf(quote.items, quote.quote_data)
    visible_quote_no = str(quote.quote_data.get("quote_no") or "").strip()
    filename = f"{(visible_quote_no or quote.quote_no or 'quotation').replace('/', '-')}.pdf"
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
    quote = _quote_or_404(user, quote_id)
    _require_export_allowed(quote, user)
    content = build_xlsx(quote.items, quote.quote_data)
    visible_quote_no = str(quote.quote_data.get("quote_no") or "").strip()
    filename = f"{(visible_quote_no or quote.quote_no or 'quotation').replace('/', '-')}.xlsx"
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
    require_capability(user, "edit_workflow")
    current = _quote_or_404(user, quote_id)
    metadata_patch = _require_patch_capabilities(
        user,
        current,
        QuotePatch(stage_meta={**(current.stage_meta or {}), **payload.metadata}),
    )
    metadata = metadata_patch.stage_meta or {}
    blockers = workflow_transition_blockers(current, payload.stage)
    if blockers:
        raise HTTPException(status_code=409, detail={"message": "Workflow transition blocked", "blockers": blockers})
    if payload.stage == "sent" and not (can_approve(user) or _is_quote_approved(current)):
        raise HTTPException(status_code=403, detail="Quotation must be approved before it can be marked sent")
    if payload.stage == "po":
        metadata = {
            **metadata,
            "po_snapshot": po_snapshot(current, user_id=user.user_id),
        }
    try:
        quote = repo.advance_stage(
            user.org_id,
            quote_id,
            payload.stage,
            user.user_id,
            reason=payload.reason,
            metadata=metadata,
            expected_version=payload.expected_version,
        )
    except (QuoteConflictError, QuoteValidationError) as exc:
        _raise_repo_error(exc)
        raise
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.stage == "po":
        cache_final_approved_quote(quote)
    return quote


@router.get("/quotes/{quote_id}/history", response_model=list[StageHistoryEntry])
def quote_history(quote_id: str, user: CurrentUser = Depends(get_current_user)) -> list[StageHistoryEntry]:
    require_capability(user, "view_history")
    return _quote_or_404(user, quote_id).stage_history
