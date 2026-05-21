import type { Quote, QuoteStage } from "@/lib/api";

export type QuoteActivityEvent = {
  id: string;
  kind: "owner" | "priority" | "due_date" | "clarification" | "approval" | "vendor" | "items" | "workflow";
  title: string;
  detail: string;
  at: string;
  user: string;
};

export function readActivityLog(quote: Quote | null): QuoteActivityEvent[] {
  const value = quote?.stage_meta?.activity_log;
  return Array.isArray(value) ? value as QuoteActivityEvent[] : [];
}

export function appendActivity(
  stageMeta: Record<string, unknown>,
  event: Omit<QuoteActivityEvent, "id" | "at"> & { at?: string },
) {
  const existing = Array.isArray(stageMeta.activity_log) ? stageMeta.activity_log as QuoteActivityEvent[] : [];
  const nextEvent: QuoteActivityEvent = {
    ...event,
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    at: event.at ?? new Date().toISOString(),
  };
  return {
    ...stageMeta,
    activity_log: [nextEvent, ...existing].slice(0, 100),
  };
}

export function quoteTimelineEvents(quote: Quote | null) {
  if (!quote) return [];
  const stageEvents = quote.stage_history.map((entry, index) => ({
    id: `${quote.id}-stage-${index}-${entry.at}`,
    at: entry.at,
    title: `Stage: ${stageLabel(entry.stage)}`,
    detail: entry.reason || "Stage changed",
    kind: "Stage",
  }));
  const activityEvents = readActivityLog(quote).map((entry) => ({
    id: entry.id,
    at: entry.at,
    title: entry.title,
    detail: [entry.detail, entry.user].filter(Boolean).join(" - "),
    kind: "Activity",
  }));
  return [...stageEvents, ...activityEvents].sort((left, right) => new Date(right.at).getTime() - new Date(left.at).getTime());
}

function stageLabel(stage: QuoteStage) {
  if (stage === "initial") return "Enquiry";
  if (stage === "quote_prep") return "Quote prep";
  return stage.replace("_", " ");
}
