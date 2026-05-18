"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Circle,
  ClipboardList,
  Download,
  FileUp,
  FileSpreadsheet,
  FileText,
  Inbox,
  Loader2,
  Mail,
  Layers3,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";

import {
  API_BASE,
  GasketItem,
  ITEM_FIELDS,
  Quote,
  advanceQuoteStage,
  bulkRecompute,
  createExtraction,
  createQuote,
  deleteQuote,
  exportQuote,
  getJob,
  getQuote,
  listQuotes,
  patchQuote,
  reprocessText,
  rfiDraft,
  toNumber,
} from "@/lib/api";
import { buildMaterialPlan, MaterialPlan, DEFAULT_NESTING_EFFICIENCY, DEFAULT_SHEET_LENGTH_MM, DEFAULT_SHEET_WIDTH_MM } from "@/lib/material-planning";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const statusIcon: Record<string, React.ReactNode> = {
  ready: <Check className="h-4 w-4 text-emerald-600" />,
  check: <AlertCircle className="h-4 w-4 text-amber-600" />,
  missing: <X className="h-4 w-4 text-red-600" />,
  regret: <Circle className="h-4 w-4 text-muted-foreground" />,
};

const currencies = ["INR", "USD", "EUR", "GBP", "AED", "SAR", "QAR", "KWD", "OMR", "BHD", "SGD", "JPY"];
const TYPE_OPTIONS = ["SOFT_CUT", "SPIRAL_WOUND", "RTJ", "KAMM", "DJI", "ISK", "ISK_RTJ"];
const FACE_OPTIONS = ["RF", "FF", ""];
const UOM_OPTIONS = ["NOS", "M"];
const GROOVE_OPTIONS = ["OCT", "OVAL", ""];
const DRAFT_STAGES = new Set(["initial", "review"]);
const MATERIAL_STAGES = new Set(["initial", "review", "quote_prep", "repricing"]);
const FINAL_STAGES = new Set(["quote_prep", "repricing", "sent", "po"]);

const defaultFx: Record<string, number> = {
  INR: 1,
  USD: 83,
  EUR: 90,
  GBP: 105,
  AED: 22.6,
  SAR: 22.1,
  QAR: 22.8,
  KWD: 270,
  OMR: 216,
  BHD: 220,
  SGD: 62,
  JPY: 0.56,
};

const quoteDefaults: Record<string, unknown> = {
  quote_no: "",
  quote_date: new Date().toLocaleDateString("en-GB"),
  rev_no: "0",
  rev_date: "",
  buyer_name_address: "",
  customer_enq_no: "",
  attention: "",
  designation: "",
  contact_no: "",
  email: "",
  rep_name: "",
  rep_designation: "",
  rep_contact: "",
  rep_email: "",
  currency: "INR",
  fx_rate: 1,
  unit_prices: [],
  discount_pct: 0,
  gst_type: "IGST",
  gst_pct: 18,
  price_basis: "FOR BASIS",
  validity_days: "7",
  packing: "INCLUSIVE",
  freight: "INCLUSIVE",
  payment_terms: "30% ADVANCE & 70% BALANCE BEFORE DISPATCH OF MATERIAL",
  bank_charges: "TO YOUR ACCOUNT",
  delivery: "",
  inspection: "Not Applicable",
  insurance: "TO YOUR ACCOUNT",
  hsn_code: "84841010",
  ld_clause: "Not Applicable",
  cancellation: "Products are manufactured on order and hence Goodrich will not be able to accept cancellation of order or reduction in quantity. The product shall to invoiced as per the PO.",
  min_order_value: "Minimum Order Value is INR 10,000,No order can be processed below the same. If processed, INR 3,500 shall be paid extra on document charges.",
  technical_notes: "",
};

type TableColumn = {
  label: string;
  field: string;
  kind?: "text" | "number" | "textarea" | "select" | "checkbox" | "readonly";
  options?: string[];
  width?: string;
};

const TABLE_COLUMNS: TableColumn[] = [
  { label: "#", field: "line_no", kind: "readonly", width: "w-16" },
  { label: "Status", field: "status", kind: "readonly", width: "w-20" },
  { label: "GGPL Description", field: "ggpl_description", kind: "readonly", width: "min-w-96" },
  { label: "Notes / Flags", field: "flags", kind: "readonly", width: "min-w-80" },
  { label: "Qty", field: "quantity", kind: "number", width: "w-24" },
  { label: "UoM", field: "uom", kind: "select", options: UOM_OPTIONS, width: "w-28" },
  { label: "Regret", field: "regret", kind: "checkbox", width: "w-20" },
  { label: "Customer Description", field: "raw_description", kind: "textarea", width: "min-w-96" },
  { label: "Type", field: "gasket_type", kind: "select", options: TYPE_OPTIONS, width: "w-40" },
  { label: "Size", field: "size", width: "w-32" },
  { label: "Size (in)", field: "size_norm", width: "w-32" },
  { label: "OD (mm)", field: "od_mm", kind: "number", width: "w-28" },
  { label: "ID (mm)", field: "id_mm", kind: "number", width: "w-28" },
  { label: "Rating", field: "rating", width: "w-32" },
  { label: "MOC", field: "moc", width: "w-48" },
  { label: "Face", field: "face_type", kind: "select", options: FACE_OPTIONS, width: "w-28" },
  { label: "Thk (mm)", field: "thickness_mm", kind: "number", width: "w-28" },
  { label: "Standard", field: "standard", width: "w-44" },
  { label: "Series", field: "series", kind: "select", options: ["", "A", "B"], width: "w-28" },
  { label: "Special", field: "special", width: "w-56" },
  { label: "Ring No", field: "ring_no", width: "w-28" },
  { label: "Groove", field: "rtj_groove_type", kind: "select", options: GROOVE_OPTIONS, width: "w-28" },
  { label: "BHN", field: "rtj_hardness_bhn", kind: "number", width: "w-24" },
  { label: "SW Winding", field: "sw_winding_material", width: "w-36" },
  { label: "SW Filler", field: "sw_filler", width: "w-36" },
  { label: "SW Outer Ring", field: "sw_outer_ring", width: "w-36" },
  { label: "SW Inner Ring", field: "sw_inner_ring", width: "w-36" },
  { label: "ISK Gasket Mat", field: "isk_gasket_material", width: "w-44" },
  { label: "ISK Core", field: "isk_core_material", width: "w-36" },
  { label: "ISK Sleeves", field: "isk_sleeve_material", width: "w-36" },
  { label: "ISK Washers", field: "isk_washer_material", width: "w-36" },
  { label: "ISK Primary Seal", field: "isk_primary_seal", width: "w-44" },
  { label: "ISK Secondary Seal", field: "isk_secondary_seal", width: "w-44" },
  { label: "ISK Ins Washer", field: "isk_insulating_washer", width: "w-44" },
  { label: "KAMM Core", field: "kamm_core_material", width: "w-36" },
  { label: "KAMM Surface", field: "kamm_surface_material", width: "w-40" },
  { label: "KAMM Covering", field: "kamm_covering_layer", width: "w-40" },
  { label: "KAMM Rib", field: "kamm_rib", width: "w-32" },
  { label: "KAMM Core Thk", field: "kamm_core_thk", kind: "number", width: "w-32" },
  { label: "DJI Filler", field: "dji_filler", width: "w-36" },
  { label: "DJI Rib", field: "dji_rib", width: "w-32" },
  { label: "DJI Face", field: "dji_face_type", kind: "select", options: ["", "RF", "FF"], width: "w-28" },
  { label: "AI", field: "confidence", kind: "readonly", width: "w-28" },
];

const BULK_DEFAULTS = {
  gasket_type: "(no change)",
  moc: "",
  rating: "",
  face_type: "(no change)",
  rtj_groove_type: "(no change)",
  thickness_mm: "",
  rtj_hardness_bhn: "",
  uom: "(no change)",
  sw_winding_material: "",
  sw_filler: "",
  sw_outer_ring: "",
  sw_inner_ring: "",
  standard: "",
};
const BLANK_SELECT_VALUE = "__blank__";

function blankItem(lineNo: number): GasketItem {
  return {
    line_no: lineNo,
    quantity: 1,
    uom: "NOS",
    raw_description: "",
    is_gasket: true,
    gasket_type: "SOFT_CUT",
    status: "missing",
    flags: ["Manual row requires review"],
    ggpl_description: "",
  };
}

function getString(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join("; ");
  return String(value);
}

function setItemValue(item: GasketItem, field: string, value: string): GasketItem {
  if (["line_no", "quantity", "thickness_mm", "rtj_hardness_bhn", "od_mm", "id_mm", "kamm_core_thk"].includes(field)) {
    return { ...item, [field]: value === "" ? null : Number(value) };
  }
  if (field === "is_gasket" || field === "dji_id_first" || field === "isk_standard_explicit") {
    return { ...item, [field]: value === "true" };
  }
  if (field === "flags") {
    return { ...item, flags: value.split(";").map((part) => part.trim()).filter(Boolean) };
  }
  return { ...item, [field]: value };
}

function renumber(items: GasketItem[]): GasketItem[] {
  return items.map((item, index) => ({ ...item, line_no: index + 1 }));
}

function notesFor(item: GasketItem): string {
  const flags = Array.isArray(item.flags) ? item.flags : [];
  const defaults = Array.isArray(item.applied_defaults) ? item.applied_defaults as unknown[] : [];
  return [
    ...flags.map(String),
    ...defaults.map((value) => `[default] ${String(value)}`),
  ].join("; ");
}

function summaryKey(item: GasketItem): string {
  if (item.status === "regret") return "";
  const type = getString(item.gasket_type || "SOFT_CUT").toUpperCase();
  if (type === "RTJ") {
    return ["RTJ", item.rtj_groove_type, item.moc, item.rtj_hardness_bhn ? `${item.rtj_hardness_bhn} BHN HARDNESS MAX` : "", getString(item.standard).toUpperCase().includes("API 6A") ? "API-6A TYPE" : ""].filter(Boolean).join(" ,");
  }
  if (type === "SPIRAL_WOUND") {
    const material = [item.sw_winding_material, item.sw_filler].filter(Boolean).join("/");
    const rings = `${item.sw_inner_ring ? `+${item.sw_inner_ring}IR` : ""}${item.sw_outer_ring ? `&${item.sw_outer_ring}OR` : ""}`;
    return [material + rings, item.rating].filter(Boolean).join(",");
  }
  if (type === "KAMM") return ["KAMMPROFILE", item.kamm_core_material ? `CORE: ${item.kamm_core_material}` : "", item.kamm_surface_material ? `SURFACE: ${item.kamm_surface_material}` : ""].filter(Boolean).join(" ,");
  if (type === "DJI") return ["DOUBLE JACKET", item.dji_filler].filter(Boolean).join(" ,");
  if (type === "ISK" || type === "ISK_RTJ") return ["ISK", item.isk_type, item.isk_gasket_material].filter(Boolean).join(" ,");
  return ["SOFT CUT", item.moc, item.face_type, item.rating].filter(Boolean).join(" ,");
}

function statusClass(status: string | null | undefined) {
  if (status === "ready") return "bg-emerald-50 dark:bg-emerald-950/30";
  if (status === "check") return "bg-amber-50 dark:bg-amber-950/30";
  if (status === "missing") return "bg-red-50 dark:bg-red-950/30";
  if (status === "regret") return "bg-muted text-muted-foreground";
  return "";
}

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    initial: "Draft",
    review: "Review",
    quote_prep: "Quotation prep",
    repricing: "Repricing",
    sent: "Sent",
    po: "PO",
  };
  return labels[stage] ?? stage.replace("_", " ");
}

function Field({
  label,
  value,
  onChange,
  textarea,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  textarea?: boolean;
  type?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {textarea ? (
        <textarea
          className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <Input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
      )}
    </div>
  );
}

function SummaryTile({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "neutral" | "ready" | "check" | "missing";
}) {
  const toneClass =
    tone === "ready"
      ? "border-emerald-200 bg-emerald-50/70 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/25 dark:text-emerald-100"
      : tone === "check"
        ? "border-amber-200 bg-amber-50/70 text-amber-950 dark:border-amber-900 dark:bg-amber-950/25 dark:text-amber-100"
        : tone === "missing"
          ? "border-red-200 bg-red-50/70 text-red-950 dark:border-red-900 dark:bg-red-950/25 dark:text-red-100"
          : "border-border bg-card";
  return (
    <div className={`rounded-md border p-3 ${toneClass}`}>
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold tracking-normal">{value}</div>
      {detail && <div className="mt-1 text-xs text-muted-foreground">{detail}</div>}
    </div>
  );
}

function ProgressBar({ value }: { value: number }) {
  const width = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="h-2 overflow-hidden rounded-full bg-muted">
      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${width}%` }} />
    </div>
  );
}

type QuoteSection = "drafts" | "material" | "final";

export function QuotesClient({ section = "drafts" }: { section?: QuoteSection }) {
  const params = useSearchParams();
  const router = useRouter();
  const [quotes, setQuotes] = React.useState<Quote[]>([]);
  const [quote, setQuote] = React.useState<Quote | null>(null);
  const [search, setSearch] = React.useState("");
  const [emailText, setEmailText] = React.useState("");
  const [excelFile, setExcelFile] = React.useState<File | null>(null);
  const [manualItem, setManualItem] = React.useState<GasketItem>(blankItem(1));
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [jobMessage, setJobMessage] = React.useState("");
  const [jobProgress, setJobProgress] = React.useState(0);
  const [previewUrl, setPreviewUrl] = React.useState("");
  const [selectedRows, setSelectedRows] = React.useState<Set<number>>(new Set());
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [bulkValues, setBulkValues] = React.useState<Record<string, string>>(BULK_DEFAULTS);
  const [rfiText, setRfiText] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [exporting, setExporting] = React.useState<string | null>(null);
  const [intakeCollapsed, setIntakeCollapsed] = React.useState(false);
  const [materialPlan, setMaterialPlan] = React.useState<MaterialPlan | null>(null);
  const [materialConfig, setMaterialConfig] = React.useState({
    sheet_width_mm: DEFAULT_SHEET_WIDTH_MM,
    sheet_length_mm: DEFAULT_SHEET_LENGTH_MM,
    nesting_efficiency: DEFAULT_NESTING_EFFICIENCY,
  });
  const isDraftSection = section === "drafts";
  const isMaterialSection = section === "material";
  const isFinalSection = section === "final";
  const sectionBasePath = isFinalSection ? "/quotes/final" : isMaterialSection ? "/material-planning" : "/quotes";
  const loadedQuoteId = React.useRef<string | null>(null);
  const jobBaseItems = React.useRef<GasketItem[] | null>(null);

  const qd = React.useMemo(() => ({ ...quoteDefaults, ...(quote?.quote_data ?? {}) }), [quote?.quote_data]);
  const items = quote?.items ?? [];
  const displayIndices = items
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => {
      if (statusFilter === "issues") return item.status === "check" || item.status === "missing";
      if (statusFilter === "missing") return item.status === "missing";
      if (statusFilter === "regret") return item.status === "regret";
      return true;
    })
    .map(({ index }) => index);
  const filteredItems = displayIndices.map((index) => items[index]);
  const selectedIndices = selectedRows.size ? Array.from(selectedRows).sort((a, b) => a - b) : [];

  function invalidateMaterialPlan() {
    setMaterialPlan(null);
  }

  async function refreshQuotes(activeId?: string) {
    const data = await listQuotes();
    setQuotes(data);
    const nextId = activeId ?? (quote && data.some((row) => row.id === quote.id) ? quote.id : undefined);
    if (nextId) {
      const active = data.find((row) => row.id === nextId) ?? (await getQuote(nextId));
      setQuote(active);
    } else {
      setQuote(null);
    }
  }

  React.useEffect(() => {
    refreshQuotes(params.get("quote") ?? undefined).catch((error) => toast.error(error.message));
    // The initial quote id is read once from the URL so resume links open deterministically.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    if (quote?.id === loadedQuoteId.current) return;
    loadedQuoteId.current = quote?.id ?? null;
    setIntakeCollapsed(Boolean(quote && !isFinalSection && (quote.items?.length ?? 0) > 0));
  }, [isFinalSection, quote]);

  React.useEffect(() => {
    const hasProgress = Boolean(quote && (items.length > 0 || isFinalSection));
    if (!hasProgress) return undefined;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
      return "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [items.length, quote, isFinalSection]);

  React.useEffect(() => {
    if (!jobId) return;
    const timer = window.setInterval(async () => {
      try {
        const job = await getJob(jobId);
        const parsedCount = job.items?.length ?? 0;
        setJobMessage(job.error || (parsedCount ? `${job.message || job.status} - ${parsedCount} item(s) parsed` : job.message || job.status));
        setJobProgress(job.progress);
        if (parsedCount && quote) {
          const baseItems = jobBaseItems.current ?? [];
          invalidateMaterialPlan();
          setQuote((current) => (
            current && current.id === (job.quote_id ?? quote.id)
              ? { ...current, items: [...baseItems, ...job.items] }
              : current
          ));
        }
        if (job.status === "succeeded" || job.status === "failed") {
          window.clearInterval(timer);
          setJobId(null);
          jobBaseItems.current = null;
          if (job.status === "succeeded") {
            invalidateMaterialPlan();
            await refreshQuotes(job.quote_id ?? quote?.id);
            setIntakeCollapsed(true);
            toast.success(`Smart Parse appended ${job.items.length} item(s)`);
          } else {
            toast.error(job.error ?? "Smart Parse failed");
          }
        }
      } catch (error) {
        window.clearInterval(timer);
        setJobId(null);
        jobBaseItems.current = null;
        toast.error(error instanceof Error ? error.message : "Could not read extraction job");
      }
    }, 1200);
    return () => window.clearInterval(timer);
    // The polling interval intentionally follows only the active job and quote id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, quote?.id]);

  async function startQuote() {
    setSaving(true);
    try {
      invalidateMaterialPlan();
      const created = await createQuote({
        customer: "",
        project_ref: "",
        items: [],
        quote_data: quoteDefaults,
        stage: "initial",
      } as Partial<Quote>);
      setQuote(created);
      await refreshQuotes(created.id);
      setSelectedRows(new Set());
      setRfiText("");
      setIntakeCollapsed(false);
      router.replace(`/quotes?quote=${created.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create quote");
    } finally {
      setSaving(false);
    }
  }

  function clearWorkspace() {
    invalidateMaterialPlan();
    setQuote(null);
    setEmailText("");
    setExcelFile(null);
    setManualItem(blankItem(1));
    setJobId(null);
    setJobMessage("");
    setJobProgress(0);
    setSelectedRows(new Set());
    setPreviewUrl("");
    setStatusFilter("all");
    setBulkValues(BULK_DEFAULTS);
    setRfiText("");
    setSaving(false);
    setExporting(null);
    setIntakeCollapsed(false);
    router.replace(sectionBasePath);
  }

  async function openQuotationScreen() {
    if (!quote) return;
    await savePatch({ items, quote_data: qd, quote_no: getString(qd.quote_no) } as Partial<Quote>);
    const advanced = await advanceQuoteStage(quote.id, "quote_prep", "Moved to final quotation", {});
    setQuote(advanced);
    setQuotes((prev) => prev.map((row) => (row.id === advanced.id ? advanced : row)));
    router.replace(`/quotes/final?quote=${quote.id}`);
  }

  function closeQuotationScreen() {
    if (!quote) {
      router.replace("/quotes");
      return;
    }
    router.replace(`/quotes?quote=${quote.id}`);
  }

  async function removeQuote(row: Quote) {
    if (!window.confirm(`Delete ${row.customer || row.quote_no || row.id}?`)) return;
    try {
      await deleteQuote(row.id);
      const nextQuotes = quotes.filter((item) => item.id !== row.id);
      setQuotes(nextQuotes);
      if (quote?.id === row.id) {
        const nextId = nextQuotes[0]?.id;
        if (nextId) {
          const active = nextQuotes.find((item) => item.id === nextId) ?? await getQuote(nextId);
          setQuote(active);
        } else {
          setQuote(null);
        }
      }
      toast.success("Quote deleted");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Delete failed");
    }
  }

  async function savePatch(payload: Partial<Quote>, success?: string) {
    if (!quote) return;
    setSaving(true);
    try {
      const updated = await patchQuote(quote.id, payload);
      setQuote(updated);
      setQuotes((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
      if (success) toast.success(success);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function updateItems(nextItems: GasketItem[], success?: string) {
    invalidateMaterialPlan();
    await savePatch({ items: nextItems } as Partial<Quote>, success);
  }

  async function runExtraction(sourceType: "email" | "excel", file?: File | null) {
    if (!quote) {
      toast.error("Create a quote workspace first");
      return;
    }
    if (sourceType === "email" && !emailText.trim()) {
      toast.error("Paste enquiry text first");
      return;
    }
    if (sourceType !== "email" && !file) {
      toast.error("Choose a file first");
      return;
    }
    try {
      const accepted = await createExtraction({
        quoteId: quote.id,
        sourceType,
        text: emailText,
        file,
        customer: quote.customer,
        projectRef: quote.project_ref,
      });
      jobBaseItems.current = items;
      setIntakeCollapsed(false);
      setJobId(accepted.job_id);
      setJobMessage("Smart Parse queued");
      setJobProgress(0);
      toast.info("Smart Parse job started");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Extraction failed");
    }
  }

  async function addManualItem() {
    if (!quote) return;
    const [processed] = await bulkRecompute(quote.id, [{ ...manualItem, line_no: items.length + 1 }]);
    await updateItems([...items, processed ?? manualItem], "Manual item added");
    setManualItem(blankItem(items.length + 2));
    setIntakeCollapsed(true);
  }

  async function recomputeRows(indices: number[] = selectedIndices) {
    if (!quote) return;
    const target = indices.length ? indices : items.map((_, idx) => idx);
    const rows = target.map((idx) => items[idx]).filter(Boolean);
    const recomputed = await bulkRecompute(quote.id, rows);
    const next = [...items];
    target.forEach((idx, offset) => {
      if (next[idx] && recomputed[offset]) {
        const wasRegret = next[idx]?.status === "regret" || next[idx]?.regret === true;
        next[idx] = wasRegret ? { ...recomputed[offset], regret: true, status: "regret" } : recomputed[offset];
      }
    });
    await updateItems(next, "Rules and descriptions refreshed");
  }

  async function reprocessRows(indices?: number[]) {
    if (!quote) return;
    const target = indices?.length ? indices : selectedIndices.length ? selectedIndices : displayIndices;
    const rowsWithText = target
      .map((idx) => ({ idx, description: getString(items[idx]?.raw_description).trim() }))
      .filter((row) => row.description);
    if (!rowsWithText.length) {
      toast.error("No customer descriptions selected");
      return;
    }
    const descriptions = rowsWithText.map((row) => row.description);
    const extracted = await reprocessText(quote.id, descriptions);
    const next = [...items];
    rowsWithText.forEach(({ idx }, offset) => {
      if (extracted[offset]) {
        const wasRegret = next[idx]?.status === "regret" || next[idx]?.regret === true;
        next[idx] = {
          ...extracted[offset],
          line_no: next[idx]?.line_no ?? idx + 1,
          regret: wasRegret ? true : extracted[offset].regret,
          status: wasRegret ? "regret" : extracted[offset].status,
        };
      }
    });
    await updateItems(next, "Smart Parse refreshed selected rows");
  }

  async function exportCurrent(type: "pdf", mode: "preview" | "download" = "download") {
    if (!quote) return;
    setExporting(type);
    try {
      await savePatch({ items, quote_data: qd, quote_no: getString(qd.quote_no) } as Partial<Quote>);
      const response = await exportQuote(quote.id, type);
      const url = response.signed_url.startsWith("http") ? response.signed_url : `${API_BASE}${response.signed_url}`;
      if (mode === "preview") {
        const separator = url.includes("?") ? "&" : "?";
        setPreviewUrl(`${url}${separator}disposition=inline#toolbar=0&navpanes=0&view=FitH`);
      } else {
        window.open(url, "_blank");
      }
      await refreshQuotes(quote.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Export failed");
    } finally {
      setExporting(null);
    }
  }

  function updateItem(index: number, field: string, value: string) {
    invalidateMaterialPlan();
    const next = [...items];
    next[index] = setItemValue(next[index] ?? blankItem(index + 1), field, value);
    setQuote((current) => (current ? { ...current, items: next } : current));
  }

  function setBulkValue(field: string, value: string) {
    setBulkValues((current) => ({ ...current, [field]: value }));
  }

  function addBlankRow() {
    invalidateMaterialPlan();
    const next = [...items];
    const selectedVisible = displayIndices.filter((index) => selectedRows.has(index));
    const insertAt = selectedVisible.length === 1 ? selectedVisible[0] + 1 : next.length;
    next.splice(insertAt, 0, blankItem(insertAt + 1));
    setQuote((current) => (current ? { ...current, items: renumber(next) } : current));
    setSelectedRows(new Set());
  }

  async function deleteSelectedRows() {
    invalidateMaterialPlan();
    const selected = new Set(selectedIndices);
    await updateItems(renumber(items.filter((_, index) => !selected.has(index))), "Rows deleted");
    setSelectedRows(new Set());
  }

  async function toggleRegretSelected() {
    invalidateMaterialPlan();
    const selected = new Set(selectedIndices);
    const next = items.map((item, index) => {
      if (!selected.has(index)) return item;
      const isRegret = item.status === "regret" || item.regret === true;
      return { ...item, regret: !isRegret, status: isRegret ? "check" : "regret" };
    });
    await updateItems(next, "Regret status updated");
    setSelectedRows(new Set());
  }

  async function applyBulkEdit() {
    invalidateMaterialPlan();
    const target = selectedIndices.length ? selectedIndices : displayIndices;
    const next = [...items];
    target.forEach((index) => {
      let row = next[index] ?? blankItem(index + 1);
      if (bulkValues.gasket_type !== "(no change)") row = setItemValue(row, "gasket_type", bulkValues.gasket_type);
      if (bulkValues.moc.trim()) row = setItemValue(row, "moc", bulkValues.moc.trim().toUpperCase());
      if (bulkValues.rating.trim()) row = setItemValue(row, "rating", bulkValues.rating.trim());
      if (bulkValues.face_type !== "(no change)") row = setItemValue(row, "face_type", bulkValues.face_type);
      if (bulkValues.rtj_groove_type !== "(no change)") row = setItemValue(row, "rtj_groove_type", bulkValues.rtj_groove_type);
      if (bulkValues.thickness_mm) row = setItemValue(row, "thickness_mm", bulkValues.thickness_mm);
      if (bulkValues.rtj_hardness_bhn) row = setItemValue(row, "rtj_hardness_bhn", bulkValues.rtj_hardness_bhn);
      if (bulkValues.uom !== "(no change)") row = setItemValue(row, "uom", bulkValues.uom);
      if (bulkValues.sw_winding_material.trim()) row = setItemValue(row, "sw_winding_material", bulkValues.sw_winding_material.trim().toUpperCase());
      if (bulkValues.sw_filler.trim()) row = setItemValue(row, "sw_filler", bulkValues.sw_filler.trim().toUpperCase());
      if (bulkValues.sw_outer_ring.trim()) row = setItemValue(row, "sw_outer_ring", bulkValues.sw_outer_ring.trim().toUpperCase());
      if (bulkValues.sw_inner_ring.trim()) row = setItemValue(row, "sw_inner_ring", bulkValues.sw_inner_ring.trim().toUpperCase());
      if (bulkValues.standard.trim()) row = setItemValue(row, "standard", bulkValues.standard.trim());
      next[index] = row;
    });
    await updateItems(next, `Applied bulk edit to ${target.length} row(s)`);
  }

  async function persistInlineEdits() {
    await updateItems(items, "Working list saved");
  }

  async function startNew() {
    invalidateMaterialPlan();
    const created = await createQuote({ items: [], quote_data: quoteDefaults, stage: "initial" } as Partial<Quote>);
    setQuote(created);
    setEmailText("");
    setExcelFile(null);
    setSelectedRows(new Set());
    setRfiText("");
    setIntakeCollapsed(false);
    await refreshQuotes(created.id);
    router.replace(`/quotes?quote=${created.id}`);
  }

  function updateQd(key: string, value: unknown) {
    const next = { ...qd, [key]: value };
    if (key === "currency") {
      next.fx_rate = defaultFx[getString(value)] ?? 1;
    }
    setQuote((current) => (current ? { ...current, quote_data: next, quote_no: getString(next.quote_no) } : current));
  }

  const unitPrices = Array.isArray(qd.unit_prices) ? qd.unit_prices.map((value) => toNumber(value)) : [];
  const currency = getString(qd.currency) || "INR";
  const fxRate = toNumber(qd.fx_rate, defaultFx[currency] ?? 1);
  const discountPct = toNumber(qd.discount_pct);
  const gstPct = currency === "INR" ? toNumber(qd.gst_pct, 18) : 0;
  const subtotal = items.reduce((sum, item, index) => {
    if (item.status === "regret") return sum;
    return sum + toNumber(item.quantity, 0) * (unitPrices[index] ?? 0) / (currency === "INR" ? 1 : fxRate || 1);
  }, 0);
  const discount = subtotal * discountPct / 100;
  const taxable = subtotal - discount;
  const gst = taxable * gstPct / 100;
  const grandTotal = taxable + gst;
  const readyCount = items.filter((item) => item.status === "ready").length;
  const checkCount = items.filter((item) => item.status === "check").length;
  const missingCount = items.filter((item) => item.status === "missing").length;
  const actionCount = checkCount + missingCount;
  const readiness = items.length ? Math.round((readyCount / items.length) * 100) : 0;
  const visibleQuotes = quotes.filter((row) => {
    if (isFinalSection && !FINAL_STAGES.has(row.stage)) return false;
    else if (isMaterialSection && !MATERIAL_STAGES.has(row.stage)) return false;
    else if (!DRAFT_STAGES.has(row.stage)) return false;
    const term = search.toLowerCase();
    return !term || row.customer.toLowerCase().includes(term) || row.project_ref.toLowerCase().includes(term) || row.quote_no.toLowerCase().includes(term);
  });

  async function openQuote(row: Quote) {
    try {
      invalidateMaterialPlan();
      const active = await getQuote(row.id);
      setQuote(active);
      setSelectedRows(new Set());
      setRfiText("");
      router.replace(`${sectionBasePath}?quote=${row.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not open quote");
    }
  }

  function generateMaterialPlan() {
    if (!quote) return;
    setMaterialPlan(buildMaterialPlan(items, materialConfig));
  }

  function updatePlanRow(index: number, patch: Partial<MaterialPlan["rows"][number]>) {
    setMaterialPlan((current) => {
      if (!current) return current;
      const nextRows = current.rows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row));
      return { ...current, rows: nextRows };
    });
  }

  function formatStockSize(row: MaterialPlan["rows"][number]) {
    if (row.length_mm === "COIL") {
      return `${row.width_mm ?? "-"} mm wide coil${row.thickness_mm ? ` x ${row.thickness_mm} mm thk` : ""}`;
    }
    if (row.width_mm === null && row.length_mm === null && row.thickness_mm === null) {
      return "Weight-based stock";
    }
    return `${row.width_mm ?? "-"} x ${row.length_mm ?? "-"} x ${row.thickness_mm ?? "-"} mm`;
  }

  function formatPlanQuantity(row: MaterialPlan["rows"][number]) {
    if (row.reqd_qty_sheets !== null) {
      return `${row.reqd_qty_sheets.toFixed(0)} sheet${row.reqd_qty_sheets === 1 ? "" : "s"}`;
    }
    if (row.reqd_qty_kg !== null) return "Weight based";
    return "Needs dimensions";
  }

  if (!quote) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border bg-card p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                {isFinalSection ? <FileSpreadsheet className="h-4 w-4" /> : isMaterialSection ? <Layers3 className="h-4 w-4" /> : <Inbox className="h-4 w-4" />}
                {isFinalSection ? "Quotation queue" : isMaterialSection ? "Material planning queue" : "Draft queue"}
              </div>
              <div>
                <h2 className="text-2xl font-semibold tracking-normal">{isFinalSection ? "Final quotations" : isMaterialSection ? "Material planning" : "Drafts"}</h2>
                <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                  {isFinalSection
                    ? "Pricing, terms, PDF preview, and final customer quotation output."
                    : isMaterialSection
                      ? "Select a cleaned draft to generate starter stock sizes, estimated weights, and review notes."
                    : "Email and Excel enquiries move through draft cleanup before quotation preparation."}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {isDraftSection && (
                <Button onClick={startQuote}>
                  <Plus className="h-4 w-4" />
                  New draft
                </Button>
              )}
              <Button variant="secondary" onClick={() => refreshQuotes().catch((error) => toast.error(error.message))} aria-label="Refresh quotes">
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
            </div>
          </div>
        </div>

        <Card>
          <CardHeader className="gap-3 border-b md:flex-row md:items-center md:justify-between md:space-y-0">
            <div className="space-y-1">
              <CardTitle>{isFinalSection ? "Final quotation queue" : isMaterialSection ? "Material planning queue" : "Draft queue"}</CardTitle>
              <div className="text-sm text-muted-foreground">{visibleQuotes.length} workspace{visibleQuotes.length === 1 ? "" : "s"}</div>
            </div>
            <div className="relative w-full md:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input className="pl-9" placeholder="Search customer, project, quote no" value={search} onChange={(event) => setSearch(event.target.value)} />
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Workspace</TableHead>
                    <TableHead className="w-48">Readiness</TableHead>
                    <TableHead className="w-28">Items</TableHead>
                    <TableHead className="w-40">Updated</TableHead>
                    <TableHead className="w-28 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleQuotes.map((row) => {
                    const rowReady = row.n_items ? Math.round((row.n_ready / row.n_items) * 100) : 0;
                    return (
                      <TableRow key={row.id} className="cursor-pointer hover:bg-muted/60" onClick={() => openQuote(row)}>
                        <TableCell>
                          <div className="flex items-start gap-3">
                            <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background">
                              {isFinalSection ? <FileSpreadsheet className="h-4 w-4" /> : isMaterialSection ? <Layers3 className="h-4 w-4" /> : <ClipboardList className="h-4 w-4" />}
                            </div>
                            <div className="min-w-0">
                              <div className="truncate font-medium">{row.custom_label || row.customer || row.quote_no || "Untitled quote"}</div>
                              <div className="truncate text-xs text-muted-foreground">{row.project_ref || row.quote_no || row.id}</div>
                              <Badge variant={row.stage === "po" ? "secondary" : "outline"} className="mt-2">{stageLabel(row.stage)}</Badge>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-2">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">Ready</span>
                              <span className="font-medium">{rowReady}%</span>
                            </div>
                            <ProgressBar value={rowReady} />
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="font-medium">{row.n_items}</div>
                          <div className="text-xs text-muted-foreground">{row.n_missing + row.n_check} need review</div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{new Date(row.updated_at).toLocaleDateString()}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="sm" onClick={(event) => { event.stopPropagation(); openQuote(row); }}>
                              <ArrowRight className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                removeQuote(row);
                              }}
                              aria-label={`Delete ${row.customer || row.quote_no || row.id}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {!visibleQuotes.length && (
                    <TableRow>
                      <TableCell colSpan={5} className="py-14 text-center">
                        <div className="mx-auto flex max-w-sm flex-col items-center gap-3 text-sm text-muted-foreground">
                          <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-background">
                            {isMaterialSection ? <Layers3 className="h-5 w-5" /> : <Inbox className="h-5 w-5" />}
                          </div>
                          <div>{isFinalSection ? "No quotes are ready for final quotation yet." : isMaterialSection ? "No drafts are ready for material planning." : "No drafts match the current search."}</div>
                          {isDraftSection && (
                            <Button onClick={startQuote}>
                              <Plus className="h-4 w-4" />
                              New draft
                            </Button>
                          )}
                        </div>
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

  return (
    <div className="space-y-6">
      <div className="rounded-lg border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={quote.stage === "po" ? "secondary" : "outline"}>{stageLabel(quote.stage)}</Badge>
              {saving && <span className="inline-flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving</span>}
            </div>
            <div>
              <h2 className="truncate text-2xl font-semibold tracking-normal">{quote.customer || quote.quote_no || "Untitled draft"}</h2>
              <div className="mt-1 truncate text-sm text-muted-foreground">{quote.project_ref || quote.id}</div>
            </div>
            {!isFinalSection && (
              <div className="grid gap-3 sm:grid-cols-4">
                <SummaryTile label="Items" value={items.length} detail={`${filteredItems.length} visible`} />
                <SummaryTile label="Ready" value={readyCount} detail={`${readiness}% complete`} tone="ready" />
                <SummaryTile label="Review" value={checkCount} detail="Defaults used" tone="check" />
                <SummaryTile label="Missing" value={missingCount} detail="Needs input" tone="missing" />
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-2 xl:justify-end">
            <Button variant="secondary" onClick={clearWorkspace}>
              <RotateCcw className="h-4 w-4" />
              Back to list
            </Button>
            {isDraftSection && (
              <>
                <Button variant="secondary" onClick={startNew}>
                  <Plus className="h-4 w-4" />
                  New draft
                </Button>
                <Button onClick={openQuotationScreen} disabled={!items.length}>
                  <ArrowRight className="h-4 w-4" />
                  Final Quotation
                </Button>
              </>
            )}
          </div>
        </div>

        <div className="mt-5 grid gap-3 border-t pt-5 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <Field label="Customer" value={quote.customer} onChange={(value) => setQuote({ ...quote, customer: value })} />
          <Field label="Project / PO reference" value={quote.project_ref} onChange={(value) => setQuote({ ...quote, project_ref: value })} />
          <Button
            variant="secondary"
            onClick={() => savePatch({ customer: quote.customer, project_ref: quote.project_ref } as Partial<Quote>, "Draft details saved")}
          >
            <Save className="h-4 w-4" />
            Save details
          </Button>
        </div>
      </div>

      {isDraftSection && (
        <Card>
          <CardHeader className="border-b">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <CardTitle>Draft intake</CardTitle>
                <div className="text-sm text-muted-foreground">
                  {intakeCollapsed && !jobId ? `${items.length} item(s) captured. Intake is minimized.` : "Email, Excel, and manual item capture"}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {jobId && (
                  <Badge variant="outline" className="w-fit">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Processing
                  </Badge>
                )}
                {(items.length > 0 || intakeCollapsed) && !jobId && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIntakeCollapsed((value) => !value)}
                    aria-label={intakeCollapsed ? "Expand draft intake" : "Minimize draft intake"}
                    title={intakeCollapsed ? "Expand draft intake" : "Minimize draft intake"}
                  >
                    {intakeCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          {intakeCollapsed && !jobId ? (
            <CardContent className="pt-5">
              <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
                Intake minimized. Review and clean the extracted draft below.
              </div>
            </CardContent>
          ) : (
            <CardContent className="pt-5">
              <Tabs defaultValue="email">
                <TabsList className="flex h-auto flex-wrap justify-start">
                  <TabsTrigger value="email"><Mail className="mr-2 h-4 w-4" />Email</TabsTrigger>
                  <TabsTrigger value="excel"><FileSpreadsheet className="mr-2 h-4 w-4" />Excel</TabsTrigger>
                  <TabsTrigger value="manual"><Plus className="mr-2 h-4 w-4" />Manual</TabsTrigger>
                </TabsList>
                <TabsContent value="email" className="mt-4">
                  <textarea
                    className="min-h-44 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                    value={emailText}
                    onChange={(event) => setEmailText(event.target.value)}
                    placeholder="Paste raw customer enquiry email text"
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button onClick={() => runExtraction("email")}>
                      {jobId ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      Process email draft
                    </Button>
                    <Button variant="secondary" onClick={() => setEmailText("")} disabled={!emailText}>
                      Clear
                    </Button>
                  </div>
                </TabsContent>
                <TabsContent value="excel" className="mt-4">
                  <div className="rounded-md border border-dashed p-5">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-background">
                          <FileUp className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div>
                          <div className="text-sm font-medium">{excelFile?.name || "Choose an Excel file"}</div>
                          <div className="text-xs text-muted-foreground">.xlsx and .xls enquiries</div>
                        </div>
                      </div>
                      <Input className="max-w-sm" type="file" accept=".xlsx,.xls" onChange={(event) => setExcelFile(event.target.files?.[0] ?? null)} />
                    </div>
                  </div>
                  <Button className="mt-3" onClick={() => runExtraction("excel", excelFile)}>
                    <Upload className="h-4 w-4" />
                    Process Excel draft
                  </Button>
                </TabsContent>
                <TabsContent value="manual" className="mt-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="md:col-span-3">
                      <Field label="Customer description" value={getString(manualItem.raw_description)} onChange={(value) => setManualItem({ ...manualItem, raw_description: value })} textarea />
                    </div>
                    <Field label="Quantity" value={getString(manualItem.quantity)} onChange={(value) => setManualItem({ ...manualItem, quantity: Number(value) })} type="number" />
                    <Field label="UOM" value={getString(manualItem.uom)} onChange={(value) => setManualItem({ ...manualItem, uom: value })} />
                    <Field label="Type" value={getString(manualItem.gasket_type)} onChange={(value) => setManualItem({ ...manualItem, gasket_type: value })} />
                    <Field label="MOC" value={getString(manualItem.moc)} onChange={(value) => setManualItem({ ...manualItem, moc: value })} />
                    <Field label="Rating" value={getString(manualItem.rating)} onChange={(value) => setManualItem({ ...manualItem, rating: value })} />
                  </div>
                  <Button className="mt-3" onClick={addManualItem}>
                    <Plus className="h-4 w-4" />
                    Add manual item
                  </Button>
                </TabsContent>
              </Tabs>
              {jobId && (
                <div className="mt-4 rounded-md border bg-muted/40 p-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {jobMessage || "Smart Parse running"}
                    </div>
                    <span className="text-xs text-muted-foreground">{Math.round(jobProgress * 100)}%</span>
                  </div>
                  <div className="mt-2">
                    <ProgressBar value={jobProgress * 100} />
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </Card>
      )}

      {isDraftSection && (
        <>
          <Card>
            <CardHeader className="sticky top-16 z-20 border-b bg-card/95 backdrop-blur">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="space-y-1">
                  <CardTitle>Draft items</CardTitle>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                    <span>{items.length} items</span>
                    <span>{readyCount} ready</span>
                    <span>{actionCount} need review</span>
                    {selectedIndices.length > 0 && <Badge variant="outline">{selectedIndices.length} selected</Badge>}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="issues">Issues</SelectItem>
                      <SelectItem value="missing">Missing</SelectItem>
                      <SelectItem value="regret">Regret</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button variant="secondary" onClick={() => setSelectedRows(new Set(displayIndices))}>Select all</Button>
                  <Button variant="secondary" onClick={() => setSelectedRows(new Set())}>Clear</Button>
                  <Button variant="secondary" onClick={addBlankRow}>
                    <Plus className="h-4 w-4" />
                    Row
                  </Button>
                  <Button variant="secondary" onClick={persistInlineEdits}>
                    <Save className="h-4 w-4" />
                    Save
                  </Button>
                  <Button onClick={openQuotationScreen} disabled={!quote || !items.length}>
                    <ArrowRight className="h-4 w-4" />
                    Final Quotation
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-5">
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => recomputeRows(selectedIndices.length ? selectedIndices : displayIndices)}>
                  <RefreshCw className="h-4 w-4" />
                  Update {selectedIndices.length ? "selected" : "visible"}
                </Button>
                <Button variant="secondary" onClick={() => reprocessRows()}>
                  {jobId ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Smart Parse {selectedIndices.length ? "selected" : "visible"}
                </Button>
                <Button variant="destructive" onClick={deleteSelectedRows} disabled={!selectedIndices.length}>
                  <Trash2 className="h-4 w-4" />
                  Delete {selectedIndices.length ? `(${selectedIndices.length})` : ""}
                </Button>
                <Button variant="secondary" onClick={toggleRegretSelected} disabled={!selectedIndices.length}>
                  Toggle regret
                </Button>
              </div>

              <details className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  Bulk Edit - targeting {selectedIndices.length ? `${selectedIndices.length} selected row(s)` : `all ${displayIndices.length} visible rows`}
                </summary>
                <div className="mt-3 grid gap-3 md:grid-cols-4 xl:grid-cols-8">
                  <div className="space-y-1.5">
                    <Label>Type</Label>
                    <Select value={bulkValues.gasket_type} onValueChange={(value) => setBulkValue("gasket_type", value)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="(no change)">(no change)</SelectItem>
                        {TYPE_OPTIONS.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Field label="MOC" value={bulkValues.moc} onChange={(value) => setBulkValue("moc", value)} />
                  <Field label="Rating" value={bulkValues.rating} onChange={(value) => setBulkValue("rating", value)} />
                  <div className="space-y-1.5">
                    <Label>Face</Label>
                    <Select value={bulkValues.face_type || BLANK_SELECT_VALUE} onValueChange={(value) => setBulkValue("face_type", value === BLANK_SELECT_VALUE ? "" : value)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="(no change)">(no change)</SelectItem>
                        {FACE_OPTIONS.map((value) => <SelectItem key={value || "blank-face"} value={value || BLANK_SELECT_VALUE}>{value || "(blank)"}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Groove</Label>
                    <Select value={bulkValues.rtj_groove_type || BLANK_SELECT_VALUE} onValueChange={(value) => setBulkValue("rtj_groove_type", value === BLANK_SELECT_VALUE ? "" : value)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="(no change)">(no change)</SelectItem>
                        {GROOVE_OPTIONS.map((value) => <SelectItem key={value || "blank-groove"} value={value || BLANK_SELECT_VALUE}>{value || "(blank)"}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Field label="Thk (mm)" value={bulkValues.thickness_mm} onChange={(value) => setBulkValue("thickness_mm", value)} type="number" />
                  <Field label="BHN" value={bulkValues.rtj_hardness_bhn} onChange={(value) => setBulkValue("rtj_hardness_bhn", value)} type="number" />
                  <div className="space-y-1.5">
                    <Label>UoM</Label>
                    <Select value={bulkValues.uom} onValueChange={(value) => setBulkValue("uom", value)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="(no change)">(no change)</SelectItem>
                        {UOM_OPTIONS.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Field label="SW Winding" value={bulkValues.sw_winding_material} onChange={(value) => setBulkValue("sw_winding_material", value)} />
                  <Field label="SW Filler" value={bulkValues.sw_filler} onChange={(value) => setBulkValue("sw_filler", value)} />
                  <Field label="SW Outer Ring" value={bulkValues.sw_outer_ring} onChange={(value) => setBulkValue("sw_outer_ring", value)} />
                  <Field label="SW Inner Ring" value={bulkValues.sw_inner_ring} onChange={(value) => setBulkValue("sw_inner_ring", value)} />
                  <Field label="Standard" value={bulkValues.standard} onChange={(value) => setBulkValue("standard", value)} />
                  <div className="flex items-end">
                    <Button variant="secondary" onClick={() => applyBulkEdit().catch((error) => toast.error(error.message))}>Apply Bulk Edit</Button>
                  </div>
                </div>
              </details>

              <div className="max-h-[540px] overflow-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="sticky left-0 z-20 w-12 bg-card">Select</TableHead>
                      <TableHead className="sticky left-12 z-20 w-44 bg-card">Actions</TableHead>
                      {TABLE_COLUMNS.map((column) => <TableHead key={column.label} className={column.width ?? "min-w-36"}>{column.label}</TableHead>)}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredItems.map((item) => {
                      const index = items.indexOf(item);
                      return (
                        <TableRow key={`${index}-${item.line_no ?? ""}`} className={statusClass(item.status)}>
                          <TableCell className="sticky left-0 z-10 bg-card align-top">
                            <input
                              type="checkbox"
                              checked={selectedRows.has(index)}
                              onChange={(event) => {
                                const next = new Set(selectedRows);
                                if (event.target.checked) next.add(index);
                                else next.delete(index);
                                setSelectedRows(next);
                              }}
                              aria-label={`Select row ${index + 1}`}
                            />
                          </TableCell>
                          <TableCell className="sticky left-12 z-10 bg-card align-top">
                            <div className="flex flex-col gap-2">
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => recomputeRows([index])}
                                title="Recalculate GGPL description from this row's edited fields"
                              >
                                <RefreshCw className="h-4 w-4" />
                                Update
                              </Button>
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => reprocessRows([index])}
                                title="Run Smart Parse again on this row's customer description"
                              >
                                <RotateCcw className="h-4 w-4" />
                                Smart Parse
                              </Button>
                            </div>
                          </TableCell>
                          {TABLE_COLUMNS.map((column) => (
                            <TableCell key={column.label} className="align-top">
                              {column.field === "status" ? (
                                <div className="flex items-center gap-2 text-sm">{statusIcon[getString(item.status)]}{getString(item.status)}</div>
                              ) : column.field === "flags" ? (
                                <textarea className="h-20 min-w-72 rounded-md border bg-muted px-2 py-1 text-xs" value={notesFor(item)} readOnly />
                              ) : column.field === "line_no" || column.field === "confidence" ? (
                                <Input className="h-8 min-w-20 bg-muted text-xs" value={getString(item[column.field])} readOnly />
                              ) : column.field === "ggpl_description" || column.kind === "readonly" ? (
                                <textarea className="h-20 min-w-72 rounded-md border bg-muted px-2 py-1 text-xs" value={getString(item[column.field])} readOnly />
                              ) : column.kind === "textarea" ? (
                                <textarea className="h-20 min-w-72 rounded-md border bg-background px-2 py-1 text-xs" value={getString(item[column.field])} onChange={(event) => updateItem(index, column.field, event.target.value)} />
                              ) : column.kind === "select" ? (
                                <Select value={getString(item[column.field]) || BLANK_SELECT_VALUE} onValueChange={(value) => updateItem(index, column.field, value === BLANK_SELECT_VALUE ? "" : value)}>
                                  <SelectTrigger className="h-8 min-w-28"><SelectValue /></SelectTrigger>
                                  <SelectContent>
                                    {(column.options ?? []).map((value) => <SelectItem key={value || `${column.field}-blank`} value={value || BLANK_SELECT_VALUE}>{value || "(blank)"}</SelectItem>)}
                                  </SelectContent>
                                </Select>
                              ) : column.kind === "checkbox" ? (
                                <input
                                  type="checkbox"
                                  checked={item.status === "regret" || item.regret === true}
                                  onChange={(event) => {
                                    const next = [...items];
                                    next[index] = { ...item, regret: event.target.checked, status: event.target.checked ? "regret" : "check" };
                                    setQuote((current) => (current ? { ...current, items: next } : current));
                                  }}
                                  aria-label={`Regret row ${index + 1}`}
                                />
                              ) : (
                                <Input className="h-8 min-w-28 text-xs" type={column.kind === "number" ? "number" : "text"} value={getString(item[column.field])} onChange={(event) => updateItem(index, column.field, event.target.value)} />
                              )}
                            </TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                    {!filteredItems.length && (
                      <TableRow>
                        <TableCell colSpan={TABLE_COLUMNS.length + 2} className="py-8 text-center text-sm text-muted-foreground">No items match this filter.</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>

              <details className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm font-medium">All 50 item fields</summary>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  {selectedIndices.length === 1 ? ITEM_FIELDS.map((field) => {
                    const idx = selectedIndices[0];
                    return (
                      <Field
                        key={field}
                        label={field}
                        value={getString(items[idx]?.[field])}
                        onChange={(value) => updateItem(idx, field, value)}
                        textarea={field === "raw_description" || field === "ggpl_description" || field === "flags"}
                      />
                    );
                  }) : <div className="text-sm text-muted-foreground">Select one row to edit every model field.</div>}
                </div>
              </details>

              <div className="grid gap-4 lg:grid-cols-3">
                <div className="rounded-md border p-3">
                  <div className="text-sm font-medium">Extraction summary</div>
                  <div className="mt-2 space-y-1 text-sm text-muted-foreground">
                    {Object.entries(items.reduce<Record<string, number>>((acc, item) => {
                      const key = summaryKey(item);
                      if (key) acc[key] = (acc[key] ?? 0) + 1;
                      return acc;
                    }, {})).map(([key, count], index) => <div key={key}><span className="font-medium">{index + 1}.</span> {key} <span className="text-xs">({count})</span></div>)}
                    {!items.length && <div>No items yet.</div>}
                  </div>
                </div>
                <div className="rounded-md border p-3 lg:col-span-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">Missing-field clarification</div>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => quote && rfiDraft(quote.id).then((draft) => setRfiText(draft.text)).catch((error) => toast.error(error.message))}
                    >
                      Build RFI draft
                    </Button>
                  </div>
                  <textarea className="mt-2 min-h-32 w-full rounded-md border bg-background px-3 py-2 text-sm" value={rfiText} onChange={(event) => setRfiText(event.target.value)} />
                  {rfiText && (
                    <a
                      className="mt-2 inline-flex h-8 items-center rounded-md border px-3 text-sm"
                      download="rfi-draft.txt"
                      href={`data:text/plain;charset=utf-8,${encodeURIComponent(rfiText)}`}
                    >
                      Download RFI text
                    </a>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {isMaterialSection && (
        <Card>
          <CardHeader className="border-b">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <CardTitle>Material planning</CardTitle>
                <div className="text-sm text-muted-foreground">
                  Generate a reviewable stock plan from the selected draft. Sheet settings are editable in Planning inputs.
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {materialPlan && (
                  <Button variant="secondary" onClick={() => setMaterialPlan(null)}>
                    <X className="h-4 w-4" />
                    Clear
                  </Button>
                )}
                <Button onClick={generateMaterialPlan} disabled={!items.length}>
                  <Layers3 className="h-4 w-4" />
                  {materialPlan ? "Update material plan" : "Create material plan"}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <details className="rounded-md border p-3">
              <summary className="cursor-pointer text-sm font-medium">Planning inputs</summary>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <Field
                  label="Sheet width (mm)"
                  type="number"
                  value={String(materialConfig.sheet_width_mm)}
                  onChange={(value) => {
                    setMaterialConfig((current) => ({ ...current, sheet_width_mm: Number(value) || DEFAULT_SHEET_WIDTH_MM }));
                    setMaterialPlan(null);
                  }}
                />
                <Field
                  label="Sheet length (mm)"
                  type="number"
                  value={String(materialConfig.sheet_length_mm)}
                  onChange={(value) => {
                    setMaterialConfig((current) => ({ ...current, sheet_length_mm: Number(value) || DEFAULT_SHEET_LENGTH_MM }));
                    setMaterialPlan(null);
                  }}
                />
                <Field
                  label="Nesting efficiency (%)"
                  type="number"
                  value={String(Math.round(materialConfig.nesting_efficiency * 100))}
                  onChange={(value) => {
                    const percent = Math.max(10, Math.min(Number(value) || Math.round(DEFAULT_NESTING_EFFICIENCY * 100), 100));
                    setMaterialConfig((current) => ({ ...current, nesting_efficiency: percent / 100 }));
                    setMaterialPlan(null);
                  }}
                />
              </div>
              <div className="mt-3 text-xs leading-5 text-muted-foreground">
                Sheet size and nesting efficiency are used for sheet and plate rows. Spiral-wound strip, filler tape, and RTJ or ring blanks remain weight-based because those are normally planned from coil or ring stock, not sheet nesting.
              </div>
            </details>

            {!materialPlan ? (
              <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
                Create a plan to see one consolidated output table for stock size, planned quantity, estimated purchase weight, and review notes.
              </div>
            ) : (
              <>
                <div className="space-y-1 text-center">
                  <div className="text-base font-semibold uppercase tracking-tight">
                    {quote?.customer || quote?.quote_no || "Untitled draft"} - REG : {quote?.quote_no || quote?.id || "N/A"} / {quote?.project_ref || "N/A"} / {quote?.custom_label || "GASKETS"}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Sheet rows use {materialPlan.config.sheet_width_mm} x {materialPlan.config.sheet_length_mm} mm stock with {Math.round(materialPlan.config.nesting_efficiency * 100)}% nesting efficiency.
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">Components</div>
                    <div className="text-lg font-semibold">{materialPlan.totals.component_count}</div>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">Sheet demand</div>
                    <div className="text-lg font-semibold">{materialPlan.totals.sheet_count.toFixed(0)}</div>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">Estimated purchase weight</div>
                    <div className="text-lg font-semibold">{materialPlan.totals.total_weight_kg.toFixed(3)} kg</div>
                  </div>
                </div>

                {materialPlan.warnings.length > 0 && (
                  <div className="rounded-md border border-amber-200 bg-amber-50/60 p-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/25 dark:text-amber-100">
                    <div className="mb-2 font-medium">Review flags</div>
                    <ul className="space-y-1">
                      {materialPlan.warnings.map((warning) => (
                        <li key={warning}>- {warning}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="overflow-auto rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-20">Review</TableHead>
                        <TableHead className="w-16">SL.NO.</TableHead>
                        <TableHead className="min-w-72">Stock type</TableHead>
                        <TableHead className="min-w-44">Stock size</TableHead>
                        <TableHead className="w-36">Planned qty</TableHead>
                        <TableHead className="w-40">Est. purchase wt.</TableHead>
                        <TableHead className="w-28">Source rows</TableHead>
                        <TableHead className="min-w-96">Notes / planner review</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {materialPlan.rows.map((row, index) => (
                        <TableRow key={`${row.sl_no}-${row.type}-${index}`}>
                          <TableCell>
                            <input
                              type="checkbox"
                              checked={row.reviewed}
                              onChange={(event) => updatePlanRow(index, { reviewed: event.target.checked })}
                              aria-label={`Mark row ${index + 1} reviewed`}
                            />
                          </TableCell>
                          <TableCell>{row.sl_no}</TableCell>
                          <TableCell className="text-sm font-medium">{row.type}</TableCell>
                          <TableCell className="text-sm">{formatStockSize(row)}</TableCell>
                          <TableCell className="text-sm">{formatPlanQuantity(row)}</TableCell>
                          <TableCell className="text-sm">{row.reqd_qty_kg === null ? "Needs dimensions" : `${row.reqd_qty_kg.toFixed(2)} kg`}</TableCell>
                          <TableCell className="text-sm">{row.source_count}</TableCell>
                          <TableCell>
                            <div className="mb-2 text-xs leading-5 text-muted-foreground">{row.notes}</div>
                            <textarea
                              className="min-h-16 w-full rounded-md border bg-background px-2 py-1 text-xs"
                              value={row.planner_notes}
                              onChange={(event) => updatePlanRow(index, { planner_notes: event.target.value })}
                              placeholder="Planner notes"
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                <details className="rounded-md border p-3">
                  <summary className="cursor-pointer text-sm font-medium">Assumptions and review basis</summary>
                  <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                    {materialPlan.assumptions.map((assumption) => (
                      <div key={assumption}>- {assumption}</div>
                    ))}
                    <div>- Mark rows reviewed only after checking against the approved drawing, nesting plan, and available stock.</div>
                  </div>
                </details>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {isFinalSection && (
        <Card>
          <CardHeader className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <CardTitle>Quotation preparation</CardTitle>
                <div className="text-sm text-muted-foreground">{quote.customer || quote.quote_no || "Untitled draft"}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={closeQuotationScreen}>
                  <RotateCcw className="h-4 w-4" />
                  Back to draft
                </Button>
                <Button variant="secondary" onClick={() => savePatch({ items, quote_data: qd, quote_no: getString(qd.quote_no) } as Partial<Quote>, "Quotation saved")}>
                  <Save className="h-4 w-4" />
                  Save
                </Button>
                <Button variant="secondary" onClick={() => exportCurrent("pdf", "preview")}>
                  {exporting === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                  Preview PDF
                </Button>
                <Button onClick={() => exportCurrent("pdf")}>
                  {exporting === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  Download PDF
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
              <div className="grid gap-3 md:grid-cols-4">
                <Field label="Quote no" value={getString(qd.quote_no)} onChange={(value) => updateQd("quote_no", value)} />
                <Field label="Quote date" value={getString(qd.quote_date)} onChange={(value) => updateQd("quote_date", value)} />
                <Field label="Revision no" value={getString(qd.rev_no)} onChange={(value) => updateQd("rev_no", value)} />
                <Field label="Revision date" value={getString(qd.rev_date)} onChange={(value) => updateQd("rev_date", value)} />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Buyer name/address" value={getString(qd.buyer_name_address)} onChange={(value) => updateQd("buyer_name_address", value)} textarea />
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="Customer enquiry no" value={getString(qd.customer_enq_no)} onChange={(value) => updateQd("customer_enq_no", value)} />
                  <Field label="Attention" value={getString(qd.attention)} onChange={(value) => updateQd("attention", value)} />
                  <Field label="Designation" value={getString(qd.designation)} onChange={(value) => updateQd("designation", value)} />
                  <Field label="Contact no" value={getString(qd.contact_no)} onChange={(value) => updateQd("contact_no", value)} />
                  <Field label="Email" value={getString(qd.email)} onChange={(value) => updateQd("email", value)} />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-4">
                <Field label="Rep name" value={getString(qd.rep_name)} onChange={(value) => updateQd("rep_name", value)} />
                <Field label="Rep designation" value={getString(qd.rep_designation)} onChange={(value) => updateQd("rep_designation", value)} />
                <Field label="Rep contact" value={getString(qd.rep_contact)} onChange={(value) => updateQd("rep_contact", value)} />
                <Field label="Rep email" value={getString(qd.rep_email)} onChange={(value) => updateQd("rep_email", value)} />
              </div>
              <div className="grid gap-3 md:grid-cols-5">
                <div className="space-y-1.5">
                  <Label>Currency</Label>
                  <Select value={currency} onValueChange={(value) => updateQd("currency", value)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{currencies.map((cur) => <SelectItem key={cur} value={cur}>{cur}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <Field label="FX rate" value={getString(qd.fx_rate)} onChange={(value) => updateQd("fx_rate", Number(value))} type="number" />
                <Field label="Discount %" value={getString(qd.discount_pct)} onChange={(value) => updateQd("discount_pct", Number(value))} type="number" />
                <div className="space-y-1.5">
                  <Label>GST type</Label>
                  <Select value={getString(qd.gst_type || "IGST")} onValueChange={(value) => updateQd("gst_type", value)} disabled={currency !== "INR"}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="IGST">IGST</SelectItem>
                      <SelectItem value="CGST+SGST">CGST+SGST</SelectItem>
                      <SelectItem value="UGST">UGST</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Field label="GST %" value={getString(qd.gst_pct)} onChange={(value) => updateQd("gst_pct", Number(value))} type="number" />
              </div>

              <div className="overflow-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>#</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Qty</TableHead>
                      <TableHead>UOM</TableHead>
                      <TableHead>Base INR unit price</TableHead>
                      <TableHead>{currency} unit price</TableHead>
                      <TableHead>Total {currency}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((item, index) => {
                      const price = unitPrices[index] ?? 0;
                      const converted = currency === "INR" ? price : price / (fxRate || 1);
                      const total = item.status === "regret" ? 0 : converted * toNumber(item.quantity);
                      return (
                        <TableRow key={index}>
                          <TableCell>{index + 1}</TableCell>
                          <TableCell className="min-w-96 text-xs">{item.status === "regret" ? "REGRET - CANNOT PRODUCE" : getString(item.ggpl_description || item.raw_description)}</TableCell>
                          <TableCell><Input className="w-24" type="number" value={getString(item.quantity)} onChange={(event) => updateItem(index, "quantity", event.target.value)} /></TableCell>
                          <TableCell>{getString(item.uom || "NOS")}</TableCell>
                          <TableCell>
                            <Input
                              className="w-32"
                              type="number"
                              value={getString(price)}
                              onChange={(event) => {
                                const next = [...unitPrices];
                                next[index] = Number(event.target.value);
                                updateQd("unit_prices", next);
                              }}
                            />
                          </TableCell>
                          <TableCell>{converted.toFixed(2)}</TableCell>
                          <TableCell>{total.toFixed(2)}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
              <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Subtotal</div><div className="text-lg font-semibold">{subtotal.toFixed(2)}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Discount</div><div className="text-lg font-semibold">{discount.toFixed(2)}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">GST</div><div className="text-lg font-semibold">{gst.toFixed(2)}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Grand total</div><div className="text-lg font-semibold">{grandTotal.toFixed(2)}</div></div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                {[
                  ["price_basis", "Price basis"],
                  ["validity_days", "Validity days"],
                  ["packing", "Packing"],
                  ["freight", "Freight"],
                  ["payment_terms", "Payment terms"],
                  ["bank_charges", "Bank charges"],
                  ["delivery", "Delivery"],
                  ["inspection", "Inspection"],
                  ["insurance", "Insurance"],
                  ["hsn_code", "HSN code"],
                  ["ld_clause", "LD clause"],
                  ["cancellation", "Cancellation"],
                  ["min_order_value", "Minimum order value"],
                  ["technical_notes", "Technical notes"],
                ].map(([key, label]) => (
                  <Field
                    key={key}
                    label={label}
                    value={getString(qd[key])}
                    onChange={(value) => updateQd(key, value)}
                    textarea={["payment_terms", "cancellation", "min_order_value", "technical_notes"].includes(key)}
                  />
                ))}
              </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={Boolean(previewUrl)} onOpenChange={(open) => { if (!open) setPreviewUrl(""); }}>
        <DialogContent className="flex h-[92vh] max-h-[92vh] max-w-6xl flex-col gap-3 overflow-hidden p-4">
          <DialogHeader className="shrink-0">
            <DialogTitle>Quotation PDF preview</DialogTitle>
          </DialogHeader>
          {previewUrl && (
            <iframe
              title="Quotation PDF preview"
              src={previewUrl}
              className="min-h-0 flex-1 rounded-md border bg-background"
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
