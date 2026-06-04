from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.schemas.quotes import QuoteRead


ACTIVE_CLARIFICATION_STATUSES = {"required", "drafted", "requested"}
CLARIFICATION_STATUSES = {"none", *ACTIVE_CLARIFICATION_STATUSES, "resolved"}
COMPLETED_STAGES = {"sent", "po"}
MATERIAL_PLAN_FINAL_STATUSES = {"submitted", "finished"}


class QuoteConflictError(Exception):
    pass


class QuoteValidationError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_identity(value: Any) -> str:
    return str(value or "").strip().lower()


def append_activity(stage_meta: dict[str, Any], *, kind: str, title: str, detail: str, user: str) -> dict[str, Any]:
    existing = stage_meta.get("activity_log")
    activity_log = list(existing) if isinstance(existing, list) else []
    event = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "title": title,
        "detail": detail,
        "at": now_iso(),
        "user": user,
    }
    return {**stage_meta, "activity_log": [event, *activity_log][:100]}


def normalize_clarification_status(stage_meta: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    result = dict(stage_meta or {})
    raw_status = normalize_identity(result.get("clarification_status"))
    has_note = bool(str(result.get("clarification_note") or "").strip()) or any(
        str(item.get("clarification_note") or "").strip() for item in items
    )
    if raw_status not in CLARIFICATION_STATUSES:
        raw_status = "required" if has_note else "none"
    elif raw_status == "none" and has_note:
        raw_status = "required"
    result["clarification_status"] = raw_status
    return result


def quote_has_clarification(quote: QuoteRead) -> bool:
    status = normalize_identity((quote.stage_meta or {}).get("clarification_status"))
    if status in ACTIVE_CLARIFICATION_STATUSES:
        return True
    return bool(str((quote.stage_meta or {}).get("clarification_note") or "").strip()) or any(
        str(item.get("clarification_note") or "").strip() for item in quote.items
    )


def quote_owner_matches(
    quote: QuoteRead,
    *,
    user_id: str,
    user_name: str = "",
    user_email: str = "",
) -> bool:
    stage_meta = quote.stage_meta or {}
    owners = {
        normalize_identity(stage_meta.get("owner_id")),
        normalize_identity(stage_meta.get("owner_email")),
        normalize_identity(stage_meta.get("owner_name")),
    }
    aliases = {normalize_identity(user_id), normalize_identity(user_name), normalize_identity(user_email)}
    owners.discard("")
    aliases.discard("")
    return bool(owners & aliases)


def quote_opportunity_id(quote: QuoteRead) -> str:
    stage_meta = quote.stage_meta or {}
    return str(stage_meta.get("opportunity_id") or stage_meta.get("source_enquiry_id") or quote.id)


def quote_estimated_value(quote: QuoteRead) -> float:
    stage_meta = quote.stage_meta or {}
    try:
        meta_value = float(stage_meta.get("estimated_quote_value"))
    except (TypeError, ValueError):
        meta_value = -1
    if meta_value >= 0:
        return meta_value
    unit_prices = quote.quote_data.get("unit_prices")
    prices = unit_prices if isinstance(unit_prices, list) else []
    total = 0.0
    for index, item in enumerate(quote.items):
        if item.get("status") == "regret":
            continue
        try:
            quantity = float(item.get("quantity") or 0)
            unit_price = float(prices[index] or 0) if index < len(prices) else 0
        except (TypeError, ValueError):
            continue
        total += quantity * unit_price
    return total


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _item_has_size(item: dict[str, Any]) -> bool:
    return any(_has_text(item.get(key)) for key in ("size", "size_norm", "od_mm", "id_mm", "ring_no"))


def quote_high_risk_count(quote: QuoteRead) -> int:
    risks: set[str] = set()
    if not quote.items:
        risks.add("no_items")
    if quote.n_missing:
        risks.add("missing_fields")
    for index, item in enumerate(quote.items):
        row = str(index + 1)
        gasket_type = str(item.get("gasket_type") or "").strip().upper()
        text = " ".join(str(item.get(key) or "") for key in ("raw_description", "standard", "rating", "special")).upper()
        if not gasket_type:
            risks.add(f"unknown_type:{row}")
        if not _item_has_size(item):
            risks.add(f"missing_size:{row}")
        try:
            quantity = float(item.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0
        if quantity <= 0:
            risks.add(f"invalid_quantity:{row}")
        if ("ASME" in text or "ANSI" in text) and ("DIN" in text or "EN 1092" in text):
            risks.add(f"standard_mismatch:{row}")
    return len(risks)


def quote_next_action(quote: QuoteRead) -> str:
    stage_meta = quote.stage_meta or {}
    explicit = str(stage_meta.get("next_action") or "").strip()
    if explicit:
        return explicit
    status = normalize_identity(stage_meta.get("clarification_status"))
    if status == "requested":
        return "Follow up customer"
    if status in {"required", "drafted"}:
        return "Resolve clarification"
    if stage_meta.get("material_plan_stale") is True:
        return "Recalculate material needed"
    if not quote.items:
        return "Add customer enquiry"
    if quote.n_missing or quote.n_check:
        return "Review items"
    if quote_high_risk_count(quote):
        return "Technical review"
    approval = stage_meta.get("approval") if isinstance(stage_meta.get("approval"), dict) else {}
    if approval.get("status") == "pending":
        return "Follow up approval"
    if quote.stage in {"initial", "review"} and stage_meta.get("material_planning_enabled") is True:
        return "Plan material"
    if quote.stage in {"initial", "review"}:
        return "Continue enquiry review"
    if quote.stage in {"quote_prep", "repricing"}:
        return "Prepare quotation"
    if quote.stage == "sent":
        return "Follow up customer"
    return "Monitor order"


def quote_summary(quote: QuoteRead) -> QuoteRead:
    estimated_value = quote_estimated_value(quote)
    high_risk_count = quote_high_risk_count(quote)
    has_clarification = quote_has_clarification(quote)
    next_action = quote_next_action(quote)
    stage_meta = {
        **(quote.stage_meta or {}),
        "estimated_quote_value": estimated_value,
        "high_risk_count": high_risk_count,
        "has_clarification": has_clarification,
        "next_action": next_action,
        "opportunity_id": quote_opportunity_id(quote),
    }
    return quote.model_copy(
        update={
            "items": [],
            "stage_meta": stage_meta,
            "estimated_quote_value": estimated_value,
            "high_risk_count": high_risk_count,
            "has_clarification": has_clarification,
            "next_action": next_action,
            "opportunity_id": quote_opportunity_id(quote),
        }
    )


def _summary_key(item: dict[str, Any]) -> str:
    if item.get("status") == "regret":
        return ""
    gasket_type = str(item.get("gasket_type") or "SOFT_CUT").upper()
    if gasket_type == "RTJ":
        values = [
            "RTJ",
            item.get("rtj_groove_type"),
            item.get("moc"),
            f"{item['rtj_hardness_bhn']} BHN HARDNESS MAX" if item.get("rtj_hardness_bhn") else "",
            "API-6A TYPE" if "API 6A" in str(item.get("standard") or "").upper() else "",
        ]
    elif gasket_type == "SPIRAL_WOUND":
        material = "/".join(str(value) for value in (item.get("sw_winding_material"), item.get("sw_filler")) if value)
        inner_ring = f"+{item.get('sw_inner_ring')}IR" if item.get("sw_inner_ring") else ""
        outer_ring = f"&{item.get('sw_outer_ring')}OR" if item.get("sw_outer_ring") else ""
        rings = f"{inner_ring}{outer_ring}"
        values = [f"{material}{rings}", item.get("rating")]
    elif gasket_type == "KAMM":
        values = [
            "KAMMPROFILE",
            f"CORE: {item.get('kamm_core_material')}" if item.get("kamm_core_material") else "",
            f"SURFACE: {item.get('kamm_surface_material')}" if item.get("kamm_surface_material") else "",
        ]
    elif gasket_type == "DJI":
        values = ["DOUBLE JACKET", item.get("dji_filler")]
    elif gasket_type in {"ISK", "ISK_RTJ"}:
        values = ["ISK", item.get("isk_type"), item.get("isk_gasket_material")]
    else:
        values = ["SOFT CUT", item.get("moc"), item.get("face_type"), item.get("rating")]
    separator = "," if gasket_type == "SPIRAL_WOUND" else " ,"
    return separator.join(str(value) for value in values if value)


def extraction_summary(items: list[dict[str, Any]], version: int, stage_meta: dict[str, Any]) -> dict[str, Any]:
    notes = stage_meta.get("extraction_summary_notes")
    notes_by_key = notes if isinstance(notes, dict) else {}
    counts: dict[str, int] = {}
    unmatched: list[int] = []
    for index, item in enumerate(items, start=1):
        key = _summary_key(item)
        if key:
            counts[key] = counts.get(key, 0) + 1
        elif item.get("status") != "regret":
            unmatched.append(index)
    rows = []
    for key, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
        note = notes_by_key.get(key) if isinstance(notes_by_key.get(key), dict) else {}
        rows.append({"item": key, "count": count, "note1": str(note.get("note1") or ""), "note2": str(note.get("note2") or "")})
    item_signature = json.dumps(
        [[(key, item[key]) for key in sorted(item)] for item in items],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return {
        "source_quote_version": version,
        "generated_at": now_iso(),
        "item_signature": item_signature,
        "rows": rows,
        "unmatched_item_rows": unmatched,
    }


def prepare_created_metadata(
    stage_meta: dict[str, Any],
    *,
    quote_id: str,
    user_id: str,
    items: list[dict[str, Any]],
    source_quote: QuoteRead | None = None,
) -> dict[str, Any]:
    result = dict(stage_meta or {})
    result.setdefault("created_by_username", user_id)
    if source_quote:
        source_meta = source_quote.stage_meta or {}
        for key in ("owner_id", "owner_name", "owner_email", "owner_role"):
            if source_meta.get(key):
                result[key] = source_meta[key]
        result["opportunity_id"] = quote_opportunity_id(source_quote)
    else:
        result["owner_id"] = normalize_identity(result.get("owner_id") or user_id)
        result.setdefault("opportunity_id", quote_id)
    if result.get("owner_id"):
        result["owner_id"] = normalize_identity(result["owner_id"])
    result = normalize_clarification_status(result, items)
    result["extraction_summary"] = extraction_summary(items, 1, result)
    return result


def apply_update_invariants(current: QuoteRead, data: dict[str, Any], *, actor_id: str = "") -> dict[str, Any]:
    next_version = current.version + 1
    old_items = current.items
    new_items = data.get("items") or []
    if current.stage == "po" and old_items != new_items:
        raise QuoteValidationError("Purchase order line items are locked after PO receipt")
    old_meta = dict(current.stage_meta or {})
    stage_meta = dict(data.get("stage_meta") or {})
    owner_before = normalize_identity(old_meta.get("owner_id"))
    owner_after = normalize_identity(stage_meta.get("owner_id"))
    if owner_after:
        stage_meta["owner_id"] = owner_after
    items_changed = old_items != new_items
    planning_data_exists = any(
        key in old_meta or key in stage_meta
        for key in ("material_breakdown", "material_plan", "material_plan_status")
    )
    breakdown_changed = old_meta.get("material_breakdown") != stage_meta.get("material_breakdown")
    material_status_changed = old_meta.get("material_plan_status") != stage_meta.get("material_plan_status")
    if items_changed:
        if planning_data_exists:
            stage_meta["material_plan_stale"] = True
            stage_meta["material_plan_stale_at"] = now_iso()
        stage_meta["extraction_summary"] = extraction_summary(new_items, next_version, stage_meta)
    elif old_meta.get("material_plan_stale") is True:
        if breakdown_changed:
            stage_meta["material_plan_stale"] = False
            stage_meta.pop("material_plan_stale_at", None)
        else:
            stage_meta["material_plan_stale"] = True
            stage_meta["material_plan_stale_at"] = old_meta.get("material_plan_stale_at") or now_iso()
    if material_status_changed and stage_meta.get("material_plan_status") in MATERIAL_PLAN_FINAL_STATUSES and stage_meta.get("material_plan_stale") is True:
        raise QuoteValidationError("Recalculate material needed before submitting or finishing the material plan")
    stage_meta = normalize_clarification_status(stage_meta, new_items)
    if owner_before != owner_after and actor_id:
        stage_meta = append_activity(
            stage_meta,
            kind="owner",
            title="Assignment updated",
            detail=f"Owner changed from {owner_before or 'unassigned'} to {owner_after or 'unassigned'}",
            user=actor_id,
        )
    data["stage_meta"] = stage_meta
    return data


def workflow_transition_blockers(quote: QuoteRead, target_stage: str) -> list[str]:
    if target_stage == quote.stage:
        return []
    allowed = {
        "initial": {"review"},
        "review": {"initial", "quote_prep"},
        "quote_prep": {"review", "repricing", "sent"},
        "repricing": {"quote_prep", "sent"},
        "sent": {"repricing", "po"},
        "po": set(),
    }
    if target_stage not in allowed.get(quote.stage, set()):
        return [f"Workflow cannot move directly from {quote.stage} to {target_stage}"]
    stage_meta = quote.stage_meta or {}
    blockers: list[str] = []
    if target_stage in {"review", "quote_prep", "sent"} and not quote.items:
        blockers.append("Add at least one enquiry item before moving forward")
    if target_stage in {"quote_prep", "sent"}:
        if (quote.n_missing or quote.n_check) and stage_meta.get("technical_review_waived") is not True:
            blockers.append("Resolve item review issues or explicitly waive technical review before moving forward")
        if quote_has_clarification(quote):
            blockers.append("Resolve the active customer clarification before moving forward")
        if stage_meta.get("material_plan_stale") is True:
            blockers.append("Recalculate material needed before moving forward")
    if target_stage == "quote_prep" and stage_meta.get("material_planning_enabled") is True:
        if stage_meta.get("material_plan_status") != "finished":
            blockers.append("Finish material planning before preparing the quotation")
    if target_stage == "sent":
        prices = quote.quote_data.get("unit_prices")
        unit_prices = prices if isinstance(prices, list) else []
        for index, item in enumerate(quote.items):
            if item.get("status") == "regret":
                continue
            try:
                unit_price = float(unit_prices[index] or 0) if index < len(unit_prices) else 0
            except (TypeError, ValueError):
                unit_price = 0
            if unit_price <= 0:
                blockers.append("Enter a positive unit price for every quoted item before marking the quotation sent")
                break
    return blockers


def clone_quote_data(quote: QuoteRead) -> dict[str, Any]:
    return deepcopy(quote.model_dump())


def po_snapshot(quote: QuoteRead, *, user_id: str = "") -> dict[str, Any]:
    return {
        "captured_at": now_iso(),
        "captured_by": user_id,
        "source_quote_id": quote.id,
        "source_quote_no": quote.quote_no,
        "source_quote_version": quote.version,
        "source_enquiry_id": str((quote.stage_meta or {}).get("source_enquiry_id") or ""),
        "source_enquiry_version": (quote.stage_meta or {}).get("source_enquiry_version"),
        "items": deepcopy(quote.items),
        "quote_data": deepcopy(quote.quote_data or {}),
        "item_signature": extraction_summary(quote.items, quote.version, quote.stage_meta or {})["item_signature"],
    }
