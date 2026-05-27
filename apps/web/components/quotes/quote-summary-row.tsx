"use client";

import { ArrowRight, ClipboardList, FileSpreadsheet, Layers3, ShoppingCart, Trash2 } from "lucide-react";

import { Quote } from "@/lib/api";
import type { AppUser } from "@/lib/auth/users";
import { resolveAppUserName } from "@/lib/auth/users";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TableCell, TableRow } from "@/components/ui/table";

import { evaluateQuoteQuality } from "./quality-utils";
import { formatCurrencyValue, quoteAgeDays, quoteEstimatedValue, quoteNextAction } from "./queue-utils";
import { enquiryStageLabel, QuoteSection, stageLabel } from "./stage-utils";

export function QuoteSummaryRow({
  quote,
  section,
  onOpen,
  onDelete,
  appUsers,
  canDelete = true,
}: {
  quote: Quote;
  section: QuoteSection;
  onOpen: (quote: Quote) => void;
  onDelete: (quote: Quote) => void;
  onMetaChange: (quote: Quote, patch: Record<string, unknown>) => void;
  appUsers: AppUser[];
  canDelete?: boolean;
}) {
  const isFinalSection = section === "final";
  const isPoSection = section === "po";
  const isMaterialSection = section === "material";
  const showsCommercialValue = isFinalSection || isPoSection;
  const rowQuality = evaluateQuoteQuality(quote, quote.items, quote.quote_data ?? {});
  const highRisks = rowQuality.risks.filter((risk) => risk.severity === "high").length;
  const reviewCount = quote.n_missing + quote.n_check;
  const nextAction = quoteNextAction(quote);
  const priority = String(quote.stage_meta?.priority || "normal");
  const workflowLabel = isFinalSection || isPoSection ? stageLabel(quote.stage) : enquiryStageLabel(quote);
  const ageLabel = isPoSection ? "PO" : isFinalSection ? "quote" : "old";
  const salesRepLabel = resolveAppUserName([
    quote.stage_meta?.owner_name,
    quote.stage_meta?.owner_email,
    quote.stage_meta?.owner_id,
    quote.quote_data?.rep_name,
    quote.quote_data?.rep_email,
    quote.quote_data?.sales_rep_user_id,
  ], appUsers, "Unassigned");

  return (
    <TableRow className="cursor-pointer hover:bg-muted/40" onClick={() => onOpen(quote)}>
      <TableCell className="py-2">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-background">
            {isPoSection ? <ShoppingCart className="h-4 w-4" /> : isFinalSection ? <FileSpreadsheet className="h-4 w-4" /> : isMaterialSection ? <Layers3 className="h-4 w-4" /> : <ClipboardList className="h-4 w-4" />}
          </div>
          <div className="min-w-0 max-w-[320px]">
            <div className="flex min-w-0 items-center gap-2">
              <span className="font-mono text-sm font-semibold text-primary">{quote.quote_no || "enq-pending"}</span>
              {priority !== "normal" ? <Badge variant={priority === "urgent" || priority === "high" ? "warning" : "outline"}>{priority}</Badge> : null}
            </div>
            <div className="truncate text-sm font-medium">{quote.customer || quote.custom_label || "No customer"}</div>
            {quote.project_ref ? <div className="truncate text-xs text-muted-foreground">{quote.project_ref}</div> : null}
            <div className="truncate text-xs text-muted-foreground">Sales rep: {salesRepLabel}</div>
          </div>
        </div>
      </TableCell>
      <TableCell className="py-2">
        <div className="space-y-1">
          <div className="text-sm font-medium">{workflowLabel}</div>
          <div className="text-xs text-muted-foreground">{quoteAgeDays(quote)}d {ageLabel}</div>
        </div>
      </TableCell>
      <TableCell className="py-2">
        <div className="flex flex-wrap gap-1">
          <Badge variant={reviewCount ? "outline" : "secondary"}>{reviewCount ? `${reviewCount} review` : "Ready"}</Badge>
          {highRisks ? <Badge variant="warning">{highRisks} risk</Badge> : null}
          <Badge variant="muted">{rowQuality.score}% RFQ</Badge>
        </div>
      </TableCell>
      <TableCell className="py-2">
        <div className="text-sm">{quote.n_items} item{quote.n_items === 1 ? "" : "s"}</div>
        {showsCommercialValue ? <div className="font-medium">{formatCurrencyValue(quoteEstimatedValue(quote))}</div> : null}
        {nextAction ? <div className="max-w-48 truncate text-xs text-muted-foreground">{nextAction}</div> : null}
      </TableCell>
      <TableCell className="py-2 text-sm text-muted-foreground">{new Date(quote.updated_at).toLocaleString("en-GB", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</TableCell>
      <TableCell className="py-2 text-right">
        <div className="flex justify-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={(event) => {
              event.stopPropagation();
              onOpen(quote);
            }}
          >
            <ArrowRight className="h-4 w-4" />
          </Button>
          {canDelete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={(event) => {
                event.stopPropagation();
                onDelete(quote);
              }}
              aria-label={`Delete ${quote.customer || quote.quote_no || quote.id}`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
