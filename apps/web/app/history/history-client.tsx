"use client";

import * as React from "react";
import { Clock3, Download, FileText, ListFilter, RefreshCw, Search, Workflow } from "lucide-react";
import { toast } from "sonner";

import { API_BASE, Quote, QuoteStage, listQuotes } from "@/lib/api";
import { readActivityLog } from "@/components/quotes/activity-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const stages: QuoteStage[] = ["initial", "review", "quote_prep", "repricing", "sent", "po"];
const finalStages = new Set<QuoteStage>(["quote_prep", "repricing", "sent", "po"]);

type ExportEntry = {
  token?: string;
  filename?: string;
  content_type?: string;
  export_type?: string;
  created_at?: string;
};

type HistoryEvent = {
  id: string;
  quote: Quote;
  at: string;
  kind: "stage" | "export" | "activity" | "vendor";
  stage?: QuoteStage;
  title: string;
  detail: string;
  token?: string;
  exportType?: string;
  filename?: string;
};

function quoteHref(quote: Quote) {
  return finalStages.has(quote.stage) ? `/quotes/final?quote=${quote.id}` : `/quotes?quote=${quote.id}`;
}

function stageLabel(stage: QuoteStage) {
  if (stage === "initial") return "Enquiry";
  if (stage === "quote_prep") return "Quote prep";
  return stage.replace("_", " ");
}

function exportEntries(quote: Quote): ExportEntry[] {
  const value = quote.stage_meta?.exports;
  return Array.isArray(value) ? (value as ExportEntry[]) : [];
}

function metadataText(value: Record<string, unknown> | undefined) {
  const entries = Object.entries(value ?? {}).filter(([, item]) => item !== "" && item !== null && item !== undefined);
  return entries.map(([key, item]) => `${key.replaceAll("_", " ")}: ${String(item)}`).join(", ");
}

function eventsForQuote(quote: Quote): HistoryEvent[] {
  const stageEvents = quote.stage_history.map((entry, index) => {
    const meta = metadataText(entry.metadata);
    return {
      id: `${quote.id}-stage-${index}-${entry.at}`,
      quote,
      at: entry.at,
      kind: "stage" as const,
      stage: entry.stage,
      title: `Moved to ${stageLabel(entry.stage)}`,
      detail: [entry.reason, meta].filter(Boolean).join(" | "),
    };
  });

  const exportEvents = exportEntries(quote).map((entry, index) => ({
    id: `${quote.id}-export-${index}-${entry.token ?? entry.created_at ?? entry.filename}`,
    quote,
    at: entry.created_at ?? quote.updated_at,
    kind: "export" as const,
    title: `${(entry.export_type || "export").toUpperCase()} generated`,
    detail: entry.filename ?? "Generated quotation file",
    token: entry.token,
    exportType: entry.export_type,
    filename: entry.filename,
  }));

  const activityEvents = readActivityLog(quote).map((entry) => ({
    id: `${quote.id}-activity-${entry.id}`,
    quote,
    at: entry.at,
    kind: "activity" as const,
    title: entry.title,
    detail: [entry.detail, entry.user].filter(Boolean).join(" | "),
  }));

  const vendorValue = quote.stage_meta?.vendor_enquiries;
  const vendorEvents = Array.isArray(vendorValue) ? vendorValue.map((entry: Record<string, unknown>, index) => ({
    id: `${quote.id}-vendor-${getString(entry.id) || index}`,
    quote,
    at: getString(entry.updated_at || entry.created_at) || quote.updated_at,
    kind: "vendor" as const,
    title: `Vendor ${getString(entry.status || "enquiry")}`,
    detail: [entry.vendor_name, entry.material_group, entry.remarks].map((value) => getString(value)).filter(Boolean).join(" | "),
  })) : [];

  return [...stageEvents, ...exportEvents, ...activityEvents, ...vendorEvents];
}

function getString(value: unknown): string {
  return String(value ?? "").trim();
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function HistoryClient() {
  const [quotes, setQuotes] = React.useState<Quote[]>([]);
  const [query, setQuery] = React.useState("");
  const [kind, setKind] = React.useState("all");
  const [stage, setStage] = React.useState("all");

  async function refresh() {
    try {
      setQuotes(await listQuotes());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not load history");
    }
  }

  React.useEffect(() => {
    refresh();
  }, []);

  const events = React.useMemo(
    () => quotes.flatMap(eventsForQuote).sort((left, right) => new Date(right.at).getTime() - new Date(left.at).getTime()),
    [quotes],
  );

  const visible = events.filter((event) => {
    const term = query.toLowerCase();
    const quote = event.quote;
    const matchesQuery =
      !term ||
      [quote.customer, quote.project_ref, quote.quote_no, quote.custom_label, event.title, event.detail, event.filename ?? ""]
        .some((value) => value.toLowerCase().includes(term));
    const matchesKind = kind === "all" || event.kind === kind;
    const matchesStage = stage === "all" || event.stage === stage || event.quote.stage === stage;
    return matchesQuery && matchesKind && matchesStage;
  });

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-background">
              <Clock3 className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-normal">Activity history</h1>
              <div className="text-xs text-muted-foreground">{visible.length} visible event(s) from {events.length} total</div>
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={refresh}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_180px_180px]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search customer, project, quote no, activity" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger><ListFilter className="h-4 w-4" /><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All activity</SelectItem>
              <SelectItem value="stage">Stage changes</SelectItem>
              <SelectItem value="export">Exports</SelectItem>
              <SelectItem value="activity">Workflow activity</SelectItem>
              <SelectItem value="vendor">Vendor enquiries</SelectItem>
            </SelectContent>
          </Select>
          <Select value={stage} onValueChange={setStage}>
            <SelectTrigger><Workflow className="h-4 w-4" /><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All stages</SelectItem>
              {stages.map((item) => <SelectItem key={item} value={item}>{stageLabel(item)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        <div className="rounded-md border bg-background p-3">
          <div className="text-xs text-muted-foreground">Activity events</div>
          <div className="text-lg font-semibold">{events.length}</div>
        </div>
        <div className="rounded-md border bg-background p-3">
          <div className="text-xs text-muted-foreground">Stage changes</div>
          <div className="text-lg font-semibold">{events.filter((event) => event.kind === "stage").length}</div>
        </div>
        <div className="rounded-md border bg-background p-3">
          <div className="text-xs text-muted-foreground">Workflow events</div>
          <div className="text-lg font-semibold">{events.filter((event) => event.kind === "activity" || event.kind === "vendor").length}</div>
        </div>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base"><Clock3 className="h-4 w-4" />Timeline</CardTitle>
          <Badge variant="outline">{visible.length} events</Badge>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-44">Time</TableHead>
                  <TableHead className="min-w-48">Activity</TableHead>
                  <TableHead className="min-w-64">Quote</TableHead>
                  <TableHead className="w-36">Status</TableHead>
                  <TableHead className="min-w-72">Details</TableHead>
                  <TableHead className="w-44 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(event.at)}</TableCell>
                    <TableCell>
                      <div className="font-medium">{event.title}</div>
                      <Badge variant="outline" className="mt-1">{event.kind === "export" ? "Export" : event.kind === "vendor" ? "Vendor" : event.kind === "activity" ? "Workflow" : "Stage"}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">{event.quote.custom_label || event.quote.customer || "Untitled customer"}</div>
                      <div className="text-xs text-muted-foreground">{event.quote.project_ref || event.quote.quote_no || event.quote.id}</div>
                    </TableCell>
                    <TableCell><Badge variant={event.quote.stage === "po" ? "secondary" : "outline"}>{stageLabel(event.quote.stage)}</Badge></TableCell>
                    <TableCell className="text-sm text-muted-foreground">{event.detail || "No note recorded."}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        <Button variant="secondary" size="sm" asChild>
                          <a href={quoteHref(event.quote)}><FileText className="h-4 w-4" />Open</a>
                        </Button>
                        {event.kind === "export" && event.token && event.exportType === "pdf" && (
                          <Button variant="secondary" size="sm" asChild>
                            <a href={`${API_BASE}/api/v1/exports/${event.token}`} target="_blank" rel="noreferrer">
                              <Download className="h-4 w-4" />
                              PDF
                            </a>
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!visible.length && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">No activity matches the current filters.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
