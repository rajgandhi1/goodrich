"use client";

import { ArrowRight, ClipboardList, FileSpreadsheet, Layers3, ShoppingCart, Trash2 } from "lucide-react";

import { Quote } from "@/lib/api";
import { getAppUsers, roleLabels } from "@/lib/auth/users";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TableCell, TableRow } from "@/components/ui/table";

import { evaluateQuoteQuality } from "./quality-utils";
import { formatCurrencyValue, quoteAgeDays, quoteDueState, quoteEstimatedValue, quoteNextAction } from "./queue-utils";
import { QuoteSection, revisionLabel, stageLabel } from "./stage-utils";

const CUSTOM_SALES_REP_VALUE = "__custom_sales_rep__";

function ProgressBar({ value }: { value: number }) {
  const width = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="h-2 overflow-hidden rounded-full bg-muted">
      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${width}%` }} />
    </div>
  );
}

export function QuoteSummaryRow({
  quote,
  section,
  onOpen,
  onDelete,
  onMetaChange,
}: {
  quote: Quote;
  section: QuoteSection;
  onOpen: (quote: Quote) => void;
  onDelete: (quote: Quote) => void;
  onMetaChange: (quote: Quote, patch: Record<string, unknown>) => void;
}) {
  const isFinalSection = section === "final";
  const isPoSection = section === "po";
  const isMaterialSection = section === "material";
  const rowQuality = evaluateQuoteQuality(quote, quote.items, quote.quote_data ?? {});
  const highRisks = rowQuality.risks.filter((risk) => risk.severity === "high").length;
  const salesRepUsers = getAppUsers()
    .filter((user) => user.active)
    .sort((left, right) => {
      const leftRank = left.role === "sales" ? 0 : 1;
      const rightRank = right.role === "sales" ? 0 : 1;
      return leftRank - rightRank || left.name.localeCompare(right.name);
    });
  const selectedOwnerId = String(quote.stage_meta?.owner_id || "");
  const selectedOwnerValue = salesRepUsers.some((user) => user.id === selectedOwnerId) ? selectedOwnerId : CUSTOM_SALES_REP_VALUE;

  return (
    <TableRow className="cursor-pointer hover:bg-muted/60" onClick={() => onOpen(quote)}>
      <TableCell>
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background">
            {isPoSection ? <ShoppingCart className="h-4 w-4" /> : isFinalSection ? <FileSpreadsheet className="h-4 w-4" /> : isMaterialSection ? <Layers3 className="h-4 w-4" /> : <ClipboardList className="h-4 w-4" />}
          </div>
          <div className="min-w-0">
            <div className="truncate font-medium">{quote.custom_label || quote.customer || quote.quote_no || "Untitled quote"}</div>
            <div className="truncate text-xs text-muted-foreground">{quote.project_ref || quote.quote_no || quote.id}</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant={quote.stage === "po" ? "secondary" : "outline"}>{stageLabel(quote.stage)}</Badge>
              {revisionLabel(quote) && <Badge variant="outline">{revisionLabel(quote)}</Badge>}
              <Badge variant="outline">Version {quote.version}</Badge>
            </div>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <Select
          value={selectedOwnerValue}
          onValueChange={(value) => {
            if (value === CUSTOM_SALES_REP_VALUE) return;
            const user = salesRepUsers.find((row) => row.id === value);
            if (!user) return;
            onMetaChange(quote, {
              owner_id: user.id,
              owner_name: user.name,
              owner_email: user.email,
              owner_role: user.role,
            });
          }}
        >
          <SelectTrigger className="h-8 w-40" onClick={(event) => event.stopPropagation()}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {salesRepUsers.map((user) => (
              <SelectItem key={user.id} value={user.id}>
                {user.name} - {roleLabels[user.role]}
              </SelectItem>
            ))}
            <SelectItem value={CUSTOM_SALES_REP_VALUE}>{String(quote.stage_meta?.owner_name || "Unassigned")}</SelectItem>
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>
        <Select value={String(quote.stage_meta?.priority || "normal")} onValueChange={(value) => onMetaChange(quote, { priority: value })}>
          <SelectTrigger className="h-8 w-28" onClick={(event) => event.stopPropagation()}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="urgent">Urgent</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="normal">Normal</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>
        <div className="space-y-1">
          <Input
            type="date"
            className="h-8 w-36"
            defaultValue={String(quote.stage_meta?.due_date || "")}
            onClick={(event) => event.stopPropagation()}
            onBlur={(event) => onMetaChange(quote, { due_date: event.target.value })}
          />
          <Badge variant={quoteDueState(quote) === "delayed" ? "warning" : quoteDueState(quote) === "today" ? "secondary" : "outline"}>{quoteAgeDays(quote)}d old</Badge>
        </div>
      </TableCell>
      <TableCell>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">RFQ score</span>
            <span className="font-medium">{rowQuality.score}%</span>
          </div>
          <ProgressBar value={rowQuality.score} />
          <div className="flex flex-wrap gap-1">
            <Badge variant={highRisks ? "warning" : "muted"}>{highRisks} high risk</Badge>
            <Badge variant="outline">{rowQuality.readiness}% ready</Badge>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <div className="font-medium">{quote.n_items}</div>
        <div className="text-xs text-muted-foreground">{quote.n_missing + quote.n_check} need review</div>
      </TableCell>
      <TableCell>
        <div className="font-medium">{formatCurrencyValue(quoteEstimatedValue(quote))}</div>
        <div className="text-xs text-muted-foreground">{quoteNextAction(quote)}</div>
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">{new Date(quote.updated_at).toLocaleString("en-GB")}</TableCell>
      <TableCell className="text-right">
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
        </div>
      </TableCell>
    </TableRow>
  );
}
