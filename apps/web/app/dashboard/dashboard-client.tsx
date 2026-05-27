"use client";

import * as React from "react";
import { AlertTriangle, CalendarClock, ClipboardList, FileText, History, RefreshCw, Users } from "lucide-react";
import { toast } from "sonner";

import { DashboardMetrics, Quote, getDashboardMetrics, listQuotes } from "@/lib/api";
import { canEditQuotes, getAppUsers, getCurrentAppUser, resolveAppUserName, USERS_CHANGED_EVENT } from "@/lib/auth/users";
import { formatCurrencyValue, quoteAgeDays, quoteDueState, quoteEstimatedValue, quoteNextAction } from "@/components/quotes/queue-utils";
import { stageLabel } from "@/components/quotes/stage-utils";
import { EmptyState } from "@/components/app-shell/empty-state";
import { MetricCard } from "@/components/app-shell/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const finalStages = new Set(["quote_prep", "repricing", "sent", "po"]);

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function quoteHref(quote: Quote) {
  if (quote.stage === "po") return `/purchase-orders?quote=${quote.id}`;
  return finalStages.has(quote.stage) ? `/quotes/final?quote=${quote.id}` : `/quotes?quote=${quote.id}`;
}

function dueLabel(quote: Quote) {
  const state = quoteDueState(quote);
  if (state === "delayed") return "Delayed";
  if (state === "today") return "Today";
  return String(quote.stage_meta?.due_date || "-");
}

export function DashboardClient() {
  const [metrics, setMetrics] = React.useState<DashboardMetrics | null>(null);
  const [quotes, setQuotes] = React.useState<Quote[]>([]);
  const [currentUser, setCurrentUser] = React.useState(() => getCurrentAppUser());
  const [appUsers, setAppUsers] = React.useState(() => getAppUsers());

  async function refresh() {
    try {
      const [metricData, quoteData] = await Promise.all([getDashboardMetrics(), listQuotes()]);
      setMetrics(metricData);
      setQuotes(quoteData);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Dashboard load failed");
    }
  }

  React.useEffect(() => {
    refresh();
  }, []);

  React.useEffect(() => {
    const refreshUser = () => {
      setCurrentUser(getCurrentAppUser());
      setAppUsers(getAppUsers());
    };
    window.addEventListener(USERS_CHANGED_EVENT, refreshUser);
    window.addEventListener("storage", refreshUser);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refreshUser);
      window.removeEventListener("storage", refreshUser);
    };
  }, []);

  const openQuotes = quotes.filter((quote) => !["sent", "po"].includes(quote.stage));
  const urgent = [...openQuotes]
    .sort((left, right) => {
      const dueRank = { delayed: 0, today: 1, future: 2, none: 3 };
      const leftRank = dueRank[quoteDueState(left)];
      const rightRank = dueRank[quoteDueState(right)];
      if (leftRank !== rightRank) return leftRank - rightRank;
      return quoteEstimatedValue(right) - quoteEstimatedValue(left);
    })
    .slice(0, 8);
  const stageMax = Math.max(1, ...Object.values(metrics?.stage_counts ?? {}));

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-background">
              <ClipboardList className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-normal">Operations dashboard</h1>
              <div className="text-xs text-muted-foreground">
                {metrics?.generated_at ? `Updated ${new Date(metrics.generated_at).toLocaleString("en-GB")}` : "Quote control room"}
              </div>
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={refresh}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Intake" value={String(metrics?.new_enquiries_today ?? 0)} hint="New enquiries today" />
        <MetricCard label="Review" value={String(metrics?.pending_review ?? 0)} hint="Pending technical review" />
        <MetricCard label="Blocked" value={String(metrics?.clarification_required ?? 0)} hint="Clarifications required" />
        <MetricCard label="Delayed" value={String(metrics?.delayed_enquiries ?? 0)} hint={`${metrics?.due_today ?? 0} due today`} />
        <MetricCard label="Open value" value={formatCurrencyValue(metrics?.open_quote_value ?? metrics?.total_quote_value ?? 0)} hint={`${metrics?.high_value_enquiries ?? 0} high-value enquiries`} />
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        {urgent.length ? (
          <Card>
            <CardHeader className="border-b px-4 py-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <CalendarClock className="h-4 w-4" />
                Urgent work
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Customer / enquiry</TableHead>
                    <TableHead>Sales rep</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Age</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Next action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {urgent.map((quote) => (
                    <TableRow key={quote.id}>
                      <TableCell>
                        <a href={quoteHref(quote)} className="font-medium hover:underline">{quote.customer || "Untitled customer"}</a>
                        <div className="text-xs text-muted-foreground">{quote.project_ref || quote.quote_no || quote.id}</div>
                      </TableCell>
                      <TableCell>{resolveAppUserName([quote.stage_meta?.owner_name, quote.stage_meta?.owner_email, quote.stage_meta?.owner_id], appUsers, "Unassigned")}</TableCell>
                      <TableCell><Badge variant="outline">{stageLabel(quote.stage)}</Badge></TableCell>
                      <TableCell>{quoteAgeDays(quote)}d</TableCell>
                      <TableCell>
                        <Badge variant={quoteDueState(quote) === "delayed" ? "warning" : quoteDueState(quote) === "today" ? "secondary" : "outline"}>{dueLabel(quote)}</Badge>
                      </TableCell>
                      <TableCell>{formatCurrencyValue(quoteEstimatedValue(quote))}</TableCell>
                      <TableCell className="text-sm">{quoteNextAction(quote)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        ) : (
          <EmptyState
            icon={ClipboardList}
            title="No active quotations"
            body="Create a quote workspace when the first enquiry is ready for intake."
            action={canEditQuotes(currentUser.role) ? { label: "New enquiry", href: "/quotes?new=1" } : undefined}
          />
        )}

        <Card>
          <CardHeader className="border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4" />
              Team workload
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(metrics?.owner_workload ?? []).map((owner) => (
              <div key={owner.owner_id} className="rounded-md border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">{resolveAppUserName([owner.owner_name, owner.owner_id], appUsers, "Unassigned")}</div>
                  <Badge variant={owner.delayed_count ? "warning" : "outline"}>{owner.open_count} open</Badge>
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {owner.delayed_count} delayed / {formatCurrencyValue(owner.value)} open value
                </div>
              </div>
            ))}
            {!(metrics?.owner_workload ?? []).length && <div className="text-sm text-muted-foreground">No open sales rep workload yet.</div>}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Card>
          <CardHeader className="border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base"><ClipboardList className="h-4 w-4" />Stage funnel</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(metrics?.stage_counts ?? {}).map(([stage, count]) => (
              <div key={stage} className="flex items-center gap-3">
                <div className="w-32 truncate text-sm">{stageLabel(stage)}</div>
                <div className="h-2 flex-1 overflow-hidden rounded bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${Math.max(4, (count / stageMax) * 100)}%` }} />
                </div>
                <div className="w-10 text-right text-sm text-muted-foreground">{count}</div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4" />Gasket type distribution</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(metrics?.gasket_type_distribution ?? {}).map(([type, count]) => (
              <div key={type} className="flex items-center gap-3">
                <div className="w-40 truncate text-sm">{type}</div>
                <div className="h-2 flex-1 overflow-hidden rounded bg-muted">
                  <div className="h-full bg-secondary" style={{ width: `${Math.min(100, count * 12)}%` }} />
                </div>
                <div className="w-10 text-right text-sm text-muted-foreground">{count}</div>
              </div>
            ))}
            {!Object.keys(metrics?.gasket_type_distribution ?? {}).length && <div className="text-sm text-muted-foreground">No item data yet.</div>}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <EmptyState
          icon={FileText}
          title="Quote preparation"
          body={`${quotes.filter((quote) => quote.stage === "quote_prep").length} quotation(s) are in quote preparation.`}
        />
        <EmptyState
          icon={AlertTriangle}
          title="Approvals"
          body={`${metrics?.pending_approval ?? 0} quotation(s) are waiting for approval.`}
        />
        <EmptyState
          icon={History}
          title="Average time to sent"
          body={`${(metrics?.avg_time_to_sent_days ?? 0).toFixed(1)} days across sent quotations. Win rate ${pct(metrics?.win_rate ?? 0)}.`}
        />
      </div>
    </div>
  );
}
