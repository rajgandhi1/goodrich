"use client";

import * as React from "react";
import { CheckCircle2, RefreshCw, Save, Send } from "lucide-react";
import { toast } from "sonner";

import { getString } from "@/components/quotes/item-validation";
import { appendActivity } from "@/components/quotes/activity-utils";
import { stageLabel } from "@/components/quotes/stage-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Quote, VendorEnquiry, VendorEnquiryStatus, getQuote, listQuotes, patchQuote, toNumber } from "@/lib/api";

const statuses: VendorEnquiryStatus[] = ["draft", "sent", "replied", "selected", "rejected"];

function newId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `ve-${Date.now()}`;
}

function readVendorEnquiries(quote: Quote | null): VendorEnquiry[] {
  const value = quote?.stage_meta?.vendor_enquiries;
  return Array.isArray(value) ? value as VendorEnquiry[] : [];
}

function materialRows(quote: Quote | null) {
  const plan = quote?.stage_meta?.material_plan;
  if (!plan || typeof plan !== "object" || !Array.isArray((plan as { rows?: unknown[] }).rows)) return [];
  return (plan as { rows: Array<Record<string, unknown>> }).rows;
}

function defaultMaterialGroup(quote: Quote | null, source: VendorEnquiry["source"]) {
  if (source === "material_plan") {
    const row = materialRows(quote)[0];
    if (row) return getString(row.type);
  }
  const item = quote?.items?.find((row) => row.status !== "regret");
  return [item?.gasket_type, item?.moc, item?.size].filter(Boolean).join(" / ");
}

function defaultQuantity(quote: Quote | null, source: VendorEnquiry["source"]) {
  if (source === "material_plan") {
    const row = materialRows(quote)[0];
    return toNumber(row?.suggested_purchase_qty ?? row?.reqd_qty_sheets ?? row?.reqd_qty_kg, 0);
  }
  return quote?.items?.reduce((sum, row) => row.status === "regret" ? sum : sum + toNumber(row.quantity, 0), 0) ?? 0;
}

function emptyDraft(quote: Quote | null, source: VendorEnquiry["source"] = "material_plan"): VendorEnquiry {
  return {
    id: newId(),
    quote_id: quote?.id ?? "",
    quote_no: quote?.quote_no ?? "",
    customer: quote?.customer ?? "",
    vendor_name: "",
    contact: "",
    material_group: defaultMaterialGroup(quote, source),
    quantity: defaultQuantity(quote, source),
    required_date: "",
    status: "draft",
    quoted_price: 0,
    lead_time_days: 0,
    remarks: "",
    source,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export function VendorEnquiriesClient() {
  const [quotes, setQuotes] = React.useState<Quote[]>([]);
  const [quote, setQuote] = React.useState<Quote | null>(null);
  const [draft, setDraft] = React.useState<VendorEnquiry>(() => emptyDraft(null));
  const [saving, setSaving] = React.useState(false);
  const enquiries = readVendorEnquiries(quote);

  async function refresh(selectedId?: string) {
    const rows = await listQuotes();
    setQuotes(rows);
    const activeId = selectedId ?? quote?.id ?? rows[0]?.id;
    if (activeId) {
      const active = await getQuote(activeId);
      setQuote(active);
      setDraft(emptyDraft(active));
    }
  }

  React.useEffect(() => {
    refresh().catch((error) => toast.error(error instanceof Error ? error.message : "Could not load vendor enquiries"));
    // Initial load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function selectQuote(id: string) {
    const active = await getQuote(id);
    setQuote(active);
    setDraft(emptyDraft(active));
  }

  function updateDraft(patch: Partial<VendorEnquiry>) {
    setDraft((current) => {
      const sourceChanged = patch.source && patch.source !== current.source;
      const next = { ...current, ...patch };
      if (sourceChanged) {
        next.material_group = defaultMaterialGroup(quote, patch.source ?? current.source);
        next.quantity = defaultQuantity(quote, patch.source ?? current.source);
      }
      return next;
    });
  }

  async function saveEnquiry(enquiry: VendorEnquiry = draft) {
    if (!quote) return;
    if (!enquiry.vendor_name.trim()) {
      toast.error("Vendor name is required");
      return;
    }
    setSaving(true);
    try {
      const now = new Date().toISOString();
      const current = readVendorEnquiries(quote);
      const nextEnquiry = {
        ...enquiry,
        quote_id: quote.id,
        quote_no: quote.quote_no,
        customer: quote.customer,
        updated_at: now,
        created_at: enquiry.created_at || now,
      };
      const nextList = current.some((row) => row.id === nextEnquiry.id)
        ? current.map((row) => row.id === nextEnquiry.id ? nextEnquiry : row)
        : [...current, nextEnquiry];
      const updated = await patchQuote(quote.id, {
        stage_meta: appendActivity({
          ...(quote.stage_meta ?? {}),
          vendor_enquiries: nextList,
          vendor_enquiries_updated_at: now,
        }, {
          kind: "vendor",
          title: `Vendor enquiry ${nextEnquiry.status}`,
          detail: [nextEnquiry.vendor_name, nextEnquiry.material_group].filter(Boolean).join(" - "),
          user: "Purchase",
        }),
      } as Partial<Quote>);
      setQuote(updated);
      setDraft(emptyDraft(updated, draft.source));
      toast.success("Vendor enquiry saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save vendor enquiry");
    } finally {
      setSaving(false);
    }
  }

  async function updateEnquiry(enquiry: VendorEnquiry, patch: Partial<VendorEnquiry>) {
    await saveEnquiry({ ...enquiry, ...patch });
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="gap-3 border-b md:flex-row md:items-center md:justify-between md:space-y-0">
          <div>
            <CardTitle>Vendor enquiry workflow</CardTitle>
            <div className="mt-1 text-sm text-muted-foreground">Create supplier enquiries from quote items or saved material plan rows.</div>
          </div>
          <Button variant="secondary" onClick={() => refresh().catch((error) => toast.error(error.message))}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="grid gap-4 pt-5 lg:grid-cols-[320px_1fr]">
          <div className="space-y-2">
            <Label>Quote workspace</Label>
            <Select value={quote?.id ?? ""} onValueChange={(value) => selectQuote(value).catch((error) => toast.error(error.message))}>
              <SelectTrigger><SelectValue placeholder="Select quote" /></SelectTrigger>
              <SelectContent>
                {quotes.map((row) => (
                  <SelectItem key={row.id} value={row.id}>{row.customer || row.quote_no || row.id}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {quote && (
              <div className="rounded-md border p-3 text-sm">
                <div className="font-medium">{quote.customer || quote.quote_no || "Untitled enquiry"}</div>
                <div className="mt-1 text-xs text-muted-foreground">{quote.project_ref || quote.id}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant="outline">{stageLabel(quote.stage)}</Badge>
                  <Badge variant="muted">{quote.n_items} item(s)</Badge>
                  <Badge variant={materialRows(quote).length ? "secondary" : "outline"}>{materialRows(quote).length} material row(s)</Badge>
                </div>
              </div>
            )}
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="space-y-1.5">
              <Label>Source</Label>
              <Select value={draft.source} onValueChange={(value) => updateDraft({ source: value as VendorEnquiry["source"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="material_plan">Material plan</SelectItem>
                  <SelectItem value="quote_items">Quote items</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Vendor name</Label>
              <Input value={draft.vendor_name} onChange={(event) => updateDraft({ vendor_name: event.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Contact</Label>
              <Input value={draft.contact} onChange={(event) => updateDraft({ contact: event.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={draft.status} onValueChange={(value) => updateDraft({ status: value as VendorEnquiryStatus })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{statuses.map((status) => <SelectItem key={status} value={status}>{status}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label>Material / group</Label>
              <Input value={draft.material_group} onChange={(event) => updateDraft({ material_group: event.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Quantity</Label>
              <Input type="number" value={getString(draft.quantity)} onChange={(event) => updateDraft({ quantity: Number(event.target.value) })} />
            </div>
            <div className="space-y-1.5">
              <Label>Required date</Label>
              <Input type="date" value={draft.required_date} onChange={(event) => updateDraft({ required_date: event.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Quoted price</Label>
              <Input type="number" value={getString(draft.quoted_price)} onChange={(event) => updateDraft({ quoted_price: Number(event.target.value) })} />
            </div>
            <div className="space-y-1.5">
              <Label>Lead time days</Label>
              <Input type="number" value={getString(draft.lead_time_days)} onChange={(event) => updateDraft({ lead_time_days: Number(event.target.value) })} />
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label>Remarks</Label>
              <Input value={draft.remarks} onChange={(event) => updateDraft({ remarks: event.target.value })} />
            </div>
            <div className="flex items-end">
              <Button onClick={() => saveEnquiry()} disabled={!quote || saving}>
                <Save className="h-4 w-4" />
                Save enquiry
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b">
          <CardTitle>Vendor comparison</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Material / group</TableHead>
                  <TableHead className="w-28">Quantity</TableHead>
                  <TableHead className="w-32">Required</TableHead>
                  <TableHead className="w-32">Status</TableHead>
                  <TableHead className="w-36">Price</TableHead>
                  <TableHead className="w-32">Lead days</TableHead>
                  <TableHead>Remarks</TableHead>
                  <TableHead className="w-40 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {enquiries.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.vendor_name}</TableCell>
                    <TableCell>{row.material_group}</TableCell>
                    <TableCell>{row.quantity}</TableCell>
                    <TableCell>{row.required_date || "-"}</TableCell>
                    <TableCell><Badge variant={row.status === "selected" ? "secondary" : "outline"}>{row.status}</Badge></TableCell>
                    <TableCell>{row.quoted_price ? row.quoted_price.toFixed(2) : "-"}</TableCell>
                    <TableCell>{row.lead_time_days || "-"}</TableCell>
                    <TableCell className="min-w-64 text-sm text-muted-foreground">{row.remarks || "-"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="secondary" onClick={() => updateEnquiry(row, { status: "sent" })}>
                          <Send className="h-4 w-4" />
                          Sent
                        </Button>
                        <Button size="sm" onClick={() => updateEnquiry(row, { status: "selected" })}>
                          <CheckCircle2 className="h-4 w-4" />
                          Select
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!enquiries.length && (
                  <TableRow>
                    <TableCell colSpan={9} className="py-12 text-center text-sm text-muted-foreground">
                      No vendor enquiries saved for this quote.
                    </TableCell>
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
