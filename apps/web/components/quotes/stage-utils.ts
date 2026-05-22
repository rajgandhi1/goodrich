import { Quote } from "@/lib/api";

import { getString } from "./item-validation";

export type QuoteSection = "drafts" | "material" | "final" | "po";

export const DRAFT_STAGES = new Set(["initial", "review"]);
export const MATERIAL_STAGES = new Set(["initial", "review", "quote_prep", "repricing"]);
export const FINAL_STAGES = new Set(["quote_prep", "repricing", "sent", "po"]);
export const PO_STAGES = new Set(["po"]);

export function revisionLabel(quote: Quote): string {
  const revNo = getString(quote.quote_data?.rev_no);
  return revNo ? `Rev ${revNo}` : "";
}

export function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    initial: "Enquiry",
    review: "Review",
    quote_prep: "Quotation prep",
    repricing: "Repricing",
    sent: "Sent",
    po: "PO",
  };
  return labels[stage] ?? stage.replace("_", " ");
}
