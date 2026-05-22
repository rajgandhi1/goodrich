import { Quote, toNumber } from "@/lib/api";

import { evaluateQuoteQuality } from "./quality-utils";
import { getString, hasText, itemHasMaterial, itemHasSize } from "./item-validation";

const HIGH_VALUE_THRESHOLD = 500000;

export type DueState = "none" | "future" | "today" | "delayed";

function parseDate(value: unknown): Date | null {
  const raw = getString(value);
  if (!raw) return null;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function quoteAgeDays(quote: Quote): number {
  const created = parseDate(quote.created_at);
  if (!created) return 0;
  return Math.max(0, Math.floor((Date.now() - created.getTime()) / 86400000));
}

export function quoteDueState(quote: Quote): DueState {
  const due = parseDate(quote.stage_meta?.due_date);
  if (!due) return "none";
  const today = startOfDay(new Date()).getTime();
  const dueDay = startOfDay(due).getTime();
  if (dueDay < today) return "delayed";
  if (dueDay === today) return "today";
  return "future";
}

export function quoteEstimatedValue(quote: Quote): number {
  const metaValue = toNumber(quote.stage_meta?.estimated_quote_value, NaN);
  if (Number.isFinite(metaValue) && metaValue > 0) return metaValue;
  const unitPrices = Array.isArray(quote.quote_data?.unit_prices) ? quote.quote_data.unit_prices : [];
  return quote.items.reduce((sum, item, index) => {
    if (item.status === "regret") return sum;
    return sum + toNumber(item.quantity, 0) * toNumber(unitPrices[index], 0);
  }, 0);
}

export function quoteNextAction(quote: Quote): string {
  const explicit = getString(quote.stage_meta?.next_action).trim();
  if (explicit) return explicit;
  const quality = evaluateQuoteQuality(quote, quote.items, quote.quote_data ?? {});
  const due = quoteDueState(quote);
  if (quote.stage_meta?.clarification_status === "required") return "Resolve clarification";
  if (quality.risks.some((risk) => risk.severity === "high")) return "Technical review";
  if (quote.stage === "initial" || quote.stage === "review") return "Complete enquiry review";
  if (quote.stage === "quote_prep" || quote.stage === "repricing") return "Prepare quotation";
  if (quote.stage === "sent") return "Follow up customer";
  if (due === "delayed") return "Recover delay";
  return "Monitor";
}

export function quoteHasClarification(quote: Quote): boolean {
  return quote.stage_meta?.clarification_status === "required" || quote.items.some((item) => hasText(item.clarification_note));
}

export function quoteIsHighRisk(quote: Quote): boolean {
  return evaluateQuoteQuality(quote, quote.items, quote.quote_data ?? {}).risks.some((risk) => risk.severity === "high");
}

export function quoteIsHighValue(quote: Quote): boolean {
  return quoteEstimatedValue(quote) >= HIGH_VALUE_THRESHOLD;
}

export function formatCurrencyValue(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "-";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(value);
}

export function itemMatchesSmartFilter(item: Record<string, unknown>, filter: string): boolean {
  const text = [item.raw_description, item.standard, item.rating, item.special, item.ggpl_description].map(getString).join(" ").toUpperCase();
  if (filter === "missing_size") return !itemHasSize(item);
  if (filter === "missing_material") return !itemHasMaterial(item);
  if (filter === "missing_rating") return !hasText(item.rating) && !hasText(item.standard) && getString(item.gasket_type).toUpperCase() !== "RTJ";
  if (filter === "low_confidence") return toNumber(item.confidence, 1) < 0.65;
  if (filter === "drawing_required") return item.drawing_required === true || text.includes("DRAWING");
  if (filter === "duplicate_likely") return hasText(item.duplicate_group_id);
  if (filter === "non_gasket") return item.is_non_gasket === true || item.is_gasket === false;
  return false;
}
