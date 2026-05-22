"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Circle,
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
  Send,
  ShieldCheck,
  Trash2,
  Undo2,
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
  getQuote,
  listQuotes,
  patchQuote,
  reprocessText,
  rfiDraft,
  toNumber,
} from "@/lib/api";
import { addBackgroundJob } from "@/lib/background-jobs";
import { canApproveQuotes, getCurrentAppUser, roleLabels, USERS_CHANGED_EVENT } from "@/lib/auth/users";
import { buildMaterialPlan, MaterialPlan, DEFAULT_NESTING_EFFICIENCY, DEFAULT_SHEET_LENGTH_MM, DEFAULT_SHEET_WIDTH_MM } from "@/lib/material-planning";
import { getString, notesFor, validateItemField } from "@/components/quotes/item-validation";
import { buildQuotePricingSummary } from "@/components/quotes/pricing-utils";
import { evaluateQuoteQuality } from "@/components/quotes/quality-utils";
import { itemMatchesSmartFilter, quoteDueState, quoteHasClarification, quoteIsHighRisk, quoteIsHighValue } from "@/components/quotes/queue-utils";
import { QuoteSummaryRow } from "@/components/quotes/quote-summary-row";
import { appendActivity } from "@/components/quotes/activity-utils";
import { QuoteTimeline } from "@/components/quotes/quote-timeline";
import { DRAFT_STAGES, FINAL_STAGES, MATERIAL_STAGES, QuoteSection, revisionLabel, stageLabel } from "@/components/quotes/stage-utils";
import { issueBadgesForItem, TechnicalIssuesPanel } from "@/components/quotes/technical-issues-panel";
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
  include_customer_sl_no: false,
  include_customer_item_code: false,
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
  cost_prices: [],
  target_margins_pct: [],
  discount_approval_pct: 10,
  minimum_margin_pct: 15,
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

type GridCell = {
  rowIndex: number;
  colIndex: number;
};

type GridSort = {
  field: string;
  direction: "asc" | "desc";
} | null;

const TABLE_COLUMNS: TableColumn[] = [
  { label: "#", field: "line_no", kind: "readonly", width: "w-16" },
  { label: "Status", field: "status", kind: "readonly", width: "w-20" },
  { label: "Cust Sl.No", field: "customer_sl_no", width: "w-28" },
  { label: "Customer Item Code", field: "customer_item_code", width: "w-36" },
  { label: "Notes / Flags", field: "flags", kind: "readonly", width: "min-w-80" },
  { label: "Qty", field: "quantity", kind: "number", width: "w-24" },
  { label: "UoM", field: "uom", kind: "select", options: UOM_OPTIONS, width: "w-28" },
  { label: "Regret", field: "regret", kind: "checkbox", width: "w-20" },
  { label: "Customer Description", field: "raw_description", kind: "textarea", width: "min-w-96" },
  { label: "GGPL Description", field: "ggpl_description", kind: "readonly", width: "min-w-96" },
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

const TABLE_COLUMN_BY_FIELD = new Map(TABLE_COLUMNS.map((column) => [column.field, column]));

const COMPACT_TABLE_COLUMNS: TableColumn[] = [
  { label: "#", field: "line_no", kind: "readonly", width: "w-16" },
  { label: "Status", field: "status", kind: "readonly", width: "w-20" },
  { label: "Cust Sl.No", field: "customer_sl_no", width: "w-28" },
  { label: "Customer Item Code", field: "customer_item_code", width: "w-36" },
  { label: "GGPL Description", field: "ggpl_description", kind: "readonly", width: "min-w-96" },
  { label: "Notes / Flags", field: "flags", kind: "readonly", width: "min-w-72" },
  { label: "Qty", field: "quantity", kind: "number", width: "w-24" },
  { label: "UoM", field: "uom", width: "w-24" },
  { label: "Type", field: "gasket_type", width: "w-36" },
  { label: "Size", field: "size", width: "w-28" },
  { label: "Rating", field: "rating", width: "w-28" },
  { label: "MOC", field: "moc", width: "w-40" },
  { label: "Face", field: "face_type", width: "w-24" },
  { label: "Thk", field: "thickness_mm", kind: "number", width: "w-24" },
];

const STREAMLIT_TABLE_FIELDS = [
  "regret",
  "line_no",
  "customer_sl_no",
  "customer_item_code",
  "raw_description",
  "ggpl_description",
  "gasket_type",
  "size",
  "size_norm",
  "od_mm",
  "id_mm",
  "rating",
  "standard",
  "moc",
  "face_type",
  "series",
  "thickness_mm",
  "ring_no",
  "rtj_groove_type",
  "rtj_hardness_bhn",
  "sw_winding_material",
  "sw_filler",
  "sw_outer_ring",
  "sw_inner_ring",
  "isk_gasket_material",
  "isk_core_material",
  "isk_sleeve_material",
  "isk_washer_material",
  "isk_primary_seal",
  "isk_secondary_seal",
  "isk_insulating_washer",
  "kamm_core_material",
  "kamm_surface_material",
  "kamm_covering_layer",
  "kamm_rib",
  "kamm_core_thk",
  "dji_filler",
  "dji_rib",
  "dji_face_type",
  "quantity",
  "uom",
  "special",
  "status",
  "confidence",
  "flags",
];

const COLUMN_PRESET_FIELDS: Record<string, string[]> = {
  review: ["line_no", "status", "customer_sl_no", "customer_item_code", "ggpl_description", "flags", "quantity", "gasket_type", "size", "rating", "moc", "confidence"],
  commercial: ["line_no", "status", "customer_sl_no", "customer_item_code", "ggpl_description", "quantity", "uom", "gasket_type", "size", "rating", "moc"],
  soft_cut: ["line_no", "status", "ggpl_description", "quantity", "gasket_type", "size", "rating", "moc", "face_type", "thickness_mm", "standard", "confidence"],
  spiral_wound: ["line_no", "status", "ggpl_description", "quantity", "size", "rating", "sw_winding_material", "sw_filler", "sw_outer_ring", "sw_inner_ring", "standard", "confidence"],
  rtj: ["line_no", "status", "ggpl_description", "quantity", "ring_no", "rtj_groove_type", "moc", "rtj_hardness_bhn", "standard", "confidence"],
  kammprofile: ["line_no", "status", "ggpl_description", "quantity", "size", "rating", "kamm_core_material", "kamm_surface_material", "kamm_covering_layer", "kamm_rib", "kamm_core_thk", "confidence"],
  dji: ["line_no", "status", "ggpl_description", "quantity", "od_mm", "id_mm", "dji_filler", "dji_rib", "dji_face_type", "thickness_mm", "confidence"],
  isk: ["line_no", "status", "ggpl_description", "quantity", "isk_gasket_material", "isk_core_material", "isk_sleeve_material", "isk_washer_material", "isk_primary_seal", "isk_secondary_seal", "confidence"],
  full_technical: TABLE_COLUMNS.map((column) => column.field),
};

function columnsForPreset(preset: string, large: boolean): TableColumn[] {
  if (large && preset === "review") return COMPACT_TABLE_COLUMNS;
  const fields = COLUMN_PRESET_FIELDS[preset] ?? COLUMN_PRESET_FIELDS.review;
  return fields.map((field) => TABLE_COLUMN_BY_FIELD.get(field)).filter(Boolean) as TableColumn[];
}

function streamlitColumns(): TableColumn[] {
  return STREAMLIT_TABLE_FIELDS.map((field) => TABLE_COLUMN_BY_FIELD.get(field)).filter(Boolean) as TableColumn[];
}

function sameNumberSet(left: Set<number>, right: Set<number>) {
  if (left.size !== right.size) return false;
  for (const value of left) {
    if (!right.has(value)) return false;
  }
  return true;
}

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
const LARGE_DRAFT_THRESHOLD = 250;
const DRAFT_PAGE_SIZE = 500;
const FINAL_PAGE_SIZE = 50;
const SUMMARY_LIMIT = 40;
const VIRTUAL_ROW_HEIGHT = 58;
const VIRTUAL_VIEWPORT_HEIGHT = 620;
const VIRTUAL_OVERSCAN = 6;
const GRID_INPUT_CLASS =
  "h-7 w-full min-w-0 rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none focus-visible:ring-1 focus-visible:ring-ring";
const GRID_TEXTAREA_CLASS =
  "h-14 w-full min-w-0 resize-none rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none outline-none focus:ring-1 focus:ring-ring";
const GRID_READONLY_CLASS = "bg-muted/30 text-muted-foreground";
const FILTER_STORAGE_KEY = "gq_quote_saved_filters";
const RECENT_QUOTES_KEY = "gq_recent_quotes";
const DEFAULT_TABLE_MODE = "spreadsheet" as const;

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

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function nextRevisionNo(value: unknown): string {
  const current = Number.parseInt(getString(value).match(/\d+/)?.[0] ?? "0", 10);
  return String(Number.isFinite(current) ? current + 1 : 1);
}

function todayDisplayDate(): string {
  return new Date().toLocaleDateString("en-GB");
}

function storedMaterialPlan(quote: Quote | null): MaterialPlan | null {
  const plan = quote?.stage_meta?.material_plan;
  if (!plan || typeof plan !== "object") return null;
  const candidate = plan as Partial<MaterialPlan>;
  if (!Array.isArray(candidate.rows) || !candidate.totals || !candidate.config) return null;
  const rows = candidate.rows.map((row) => {
    const required = row.reqd_qty_sheets ?? row.reqd_qty_kg ?? 0;
    const available = toNumber(row.available_qty, 0);
    const reserved = toNumber(row.reserved_qty, 0);
    const shortage = row.shortage_qty ?? Math.max(0, required + reserved - available);
    return {
      ...row,
      available_qty: available,
      reserved_qty: reserved,
      shortage_qty: shortage,
      suggested_purchase_qty: row.suggested_purchase_qty ?? shortage,
      lead_time_days: toNumber(row.lead_time_days, 0),
      preferred_vendor: getString(row.preferred_vendor),
      estimated_material_cost: toNumber(row.estimated_material_cost, 0),
      production_priority: row.production_priority ?? "normal",
    };
  });
  return {
    ...(candidate as MaterialPlan),
    rows,
    grouped_summary: candidate.grouped_summary ?? [],
  };
}

type ApprovalState = {
  status: "draft" | "pending" | "approved" | "rejected";
  requested_by?: string;
  requested_at?: string;
  decided_by?: string;
  decided_at?: string;
  comments?: string;
  score?: number;
  risk_count?: number;
  required?: boolean;
  required_reasons?: string[];
  required_changes?: string;
};

function approvalState(quote: Quote | null): ApprovalState {
  const approval = quote?.stage_meta?.approval;
  if (!approval || typeof approval !== "object") return { status: "draft" };
  const status = getString((approval as ApprovalState).status);
  if (status !== "pending" && status !== "approved" && status !== "rejected") return { status: "draft" };
  return approval as ApprovalState;
}

function approvalBadgeVariant(status: ApprovalState["status"]) {
  if (status === "approved") return "secondary";
  if (status === "rejected") return "warning";
  return "outline";
}

function setItemValue(item: GasketItem, field: string, value: string): GasketItem {
  if (["line_no", "quantity", "thickness_mm", "rtj_hardness_bhn", "od_mm", "id_mm", "kamm_core_thk"].includes(field)) {
    return { ...item, [field]: value === "" ? null : Number(value) };
  }
  if (field === "is_gasket" || field === "dji_id_first" || field === "isk_standard_explicit" || field === "regret") {
    return { ...item, [field]: value === "true" };
  }
  if (field === "flags") {
    return { ...item, flags: value.split(";").map((part) => part.trim()).filter(Boolean) };
  }
  return { ...item, [field]: value };
}

function columnValue(item: GasketItem, column: TableColumn): string {
  if (column.field === "flags") return notesFor(item);
  if (column.field === "regret") return item.status === "regret" || item.regret === true ? "TRUE" : "FALSE";
  return getString(item[column.field]);
}

function isEditableGridColumn(column: TableColumn): boolean {
  if (column.field === "line_no" || column.field === "status" || column.field === "confidence" || column.field === "flags" || column.field === "ggpl_description") return false;
  return column.kind !== "readonly";
}

function parseClipboardTable(text: string): string[][] {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .filter((row, index, rows) => row.length > 0 || index < rows.length - 1)
    .map((row) => row.split("\t"));
}

function filterMatches(value: string, rawFilter: string): boolean {
  const filter = rawFilter.trim();
  if (!filter) return true;
  const normalizedValue = value.trim();
  const upperValue = normalizedValue.toUpperCase();
  const upperFilter = filter.toUpperCase();
  if (upperFilter === "EMPTY") return !normalizedValue;
  if (upperFilter === "!EMPTY") return Boolean(normalizedValue);
  const comparison = filter.match(/^(>=|<=|>|<|=|!=)\s*(.+)$/);
  if (comparison) {
    const [, operator, operand] = comparison;
    const leftNumber = Number(normalizedValue);
    const rightNumber = Number(operand);
    if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
      if (operator === ">=") return leftNumber >= rightNumber;
      if (operator === "<=") return leftNumber <= rightNumber;
      if (operator === ">") return leftNumber > rightNumber;
      if (operator === "<") return leftNumber < rightNumber;
      if (operator === "=") return leftNumber === rightNumber;
      return leftNumber !== rightNumber;
    }
    if (operator === "=") return upperValue === operand.trim().toUpperCase();
    if (operator === "!=") return upperValue !== operand.trim().toUpperCase();
  }
  return upperValue.includes(upperFilter);
}

function sortItemsByColumn(left: { item: GasketItem; index: number }, right: { item: GasketItem; index: number }, column: TableColumn, direction: "asc" | "desc") {
  const leftValue = columnValue(left.item, column);
  const rightValue = columnValue(right.item, column);
  const leftNumber = Number(leftValue);
  const rightNumber = Number(rightValue);
  const result = Number.isFinite(leftNumber) && Number.isFinite(rightNumber)
    ? leftNumber - rightNumber
    : leftValue.localeCompare(rightValue, undefined, { numeric: true, sensitivity: "base" });
  return direction === "asc" ? result : -result;
}

function renumber(items: GasketItem[]): GasketItem[] {
  return items.map((item, index) => ({ ...item, line_no: index + 1 }));
}

function quoteSummary(quote: Quote): Quote {
  return { ...quote, items: [] };
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

function validationClass(severity?: "blocker" | "review" | "optional") {
  if (severity === "blocker") return "bg-red-100/80 text-red-950 dark:bg-red-950/40 dark:text-red-100";
  if (severity === "review") return "bg-amber-100/80 text-amber-950 dark:bg-amber-950/40 dark:text-amber-100";
  if (severity === "optional") return "bg-muted/50 text-muted-foreground";
  return "";
}

function confidenceClass(value: unknown) {
  const confidence = toNumber(value, 1);
  if (confidence >= 0.85) return "bg-emerald-100/80 text-emerald-950 dark:bg-emerald-950/40 dark:text-emerald-100";
  if (confidence >= 0.65) return "bg-amber-100/80 text-amber-950 dark:bg-amber-950/40 dark:text-amber-100";
  return "bg-red-100/80 text-red-950 dark:bg-red-950/40 dark:text-red-100";
}

function storageAvailable() {
  return typeof window !== "undefined" && Boolean(window.localStorage);
}

type SavedQuoteFilters = {
  queueFilter?: string;
  statusFilter?: string;
  columnPreset?: string;
  tableMode?: "guided" | "spreadsheet";
};

function savedFiltersFor(section: QuoteSection) {
  if (!storageAvailable()) return null;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(FILTER_STORAGE_KEY) || "{}") as Record<string, SavedQuoteFilters>;
    return parsed[`${section}:${getCurrentAppUser().role}`] ?? parsed[section] ?? null;
  } catch {
    return null;
  }
}

function persistSavedFilters(section: QuoteSection, filters: { queueFilter: string; statusFilter: string; columnPreset: string; tableMode: "guided" | "spreadsheet" }) {
  if (!storageAvailable()) return;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(FILTER_STORAGE_KEY) || "{}") as Record<string, unknown>;
    window.localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({ ...parsed, [`${section}:${getCurrentAppUser().role}`]: filters }));
  } catch {
    window.localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({ [`${section}:${getCurrentAppUser().role}`]: filters }));
  }
}

function rememberRecentQuote(row: Quote) {
  if (!storageAvailable()) return;
  try {
    const recent = JSON.parse(window.localStorage.getItem(RECENT_QUOTES_KEY) || "[]") as Array<{ id: string; label: string; href: string; at: string }>;
    const href = FINAL_STAGES.has(row.stage) ? `/quotes/final?quote=${row.id}` : `/quotes?quote=${row.id}`;
    const next = [
      { id: row.id, label: row.customer || row.quote_no || row.id, href, at: new Date().toISOString() },
      ...recent.filter((item) => item.id !== row.id),
    ].slice(0, 8);
    window.localStorage.setItem(RECENT_QUOTES_KEY, JSON.stringify(next));
  } catch {
    window.localStorage.removeItem(RECENT_QUOTES_KEY);
  }
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

export function QuotesClient({ section = "drafts" }: { section?: QuoteSection }) {
  const params = useSearchParams();
  const router = useRouter();
  const [quotes, setQuotes] = React.useState<Quote[]>([]);
  const [quote, setQuote] = React.useState<Quote | null>(null);
  const [search, setSearch] = React.useState("");
  const [queueFilter, setQueueFilter] = React.useState("all");
  const [emailText, setEmailText] = React.useState("");
  const [excelFile, setExcelFile] = React.useState<File | null>(null);
  const [manualItem, setManualItem] = React.useState<GasketItem>(blankItem(1));
  const [startingExtraction, setStartingExtraction] = React.useState(false);
  const [previewUrl, setPreviewUrl] = React.useState("");
  const [selectedRows, setSelectedRows] = React.useState<Set<number>>(new Set());
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [columnPreset, setColumnPreset] = React.useState("review");
  const [tableMode, setTableMode] = React.useState<"guided" | "spreadsheet">(DEFAULT_TABLE_MODE);
  const [draftPage, setDraftPage] = React.useState(0);
  const [finalPage, setFinalPage] = React.useState(0);
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
  const [currentUser, setCurrentUser] = React.useState(() => getCurrentAppUser());
  const [approvalComment, setApprovalComment] = React.useState("");
  const [draftScrollTop, setDraftScrollTop] = React.useState(0);
  const [undoItems, setUndoItems] = React.useState<{ label: string; items: GasketItem[] } | null>(null);
  const [hasUnsavedLocalEdits, setHasUnsavedLocalEdits] = React.useState(false);
  const [activeCell, setActiveCell] = React.useState<GridCell | null>(null);
  const [selectionAnchor, setSelectionAnchor] = React.useState<GridCell | null>(null);
  const [selectionFocus, setSelectionFocus] = React.useState<GridCell | null>(null);
  const [isSelectingCells, setIsSelectingCells] = React.useState(false);
  const [columnFilters, setColumnFilters] = React.useState<Record<string, string>>({});
  const [gridSort, setGridSort] = React.useState<GridSort>(null);
  const isDraftSection = section === "drafts";
  const isMaterialSection = section === "material";
  const isFinalSection = section === "final";
  const sectionBasePath = isFinalSection ? "/quotes/final" : isMaterialSection ? "/material-planning" : "/quotes";
  const loadedQuoteId = React.useRef<string | null>(null);
  const draftGridRef = React.useRef<HTMLDivElement | null>(null);
  const filtersLoaded = React.useRef(false);

  const qd = React.useMemo(() => ({ ...quoteDefaults, ...(quote?.quote_data ?? {}) }), [quote?.quote_data]);
  const items = React.useMemo(() => quote?.items ?? [], [quote?.items]);
  const isLargeDraft = items.length > LARGE_DRAFT_THRESHOLD;
  const activeTableColumns = React.useMemo(
    () => (tableMode === "spreadsheet" ? streamlitColumns() : columnsForPreset(columnPreset, isLargeDraft)),
    [columnPreset, isLargeDraft, tableMode],
  );
  const activeColumnFilters = React.useMemo(
    () => Object.entries(columnFilters).filter(([, value]) => value.trim()),
    [columnFilters],
  );
  const displayEntries = React.useMemo(() => {
    return items
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => {
        if (statusFilter === "issues") return item.status === "check" || item.status === "missing";
        if (statusFilter === "missing") return item.status === "missing";
        if (statusFilter === "regret") return item.status === "regret";
        if (statusFilter !== "all") return itemMatchesSmartFilter(item, statusFilter);
        return true;
      })
      .filter(({ item }) => activeColumnFilters.every(([field, value]) => {
        const column = TABLE_COLUMN_BY_FIELD.get(field);
        if (!column) return true;
        return filterMatches(columnValue(item, column), value);
      }))
      .sort((left, right) => {
        if (!gridSort) return left.index - right.index;
        const column = TABLE_COLUMN_BY_FIELD.get(gridSort.field);
        if (!column) return left.index - right.index;
        return sortItemsByColumn(left, right, column, gridSort.direction) || left.index - right.index;
      });
  }, [activeColumnFilters, gridSort, items, statusFilter]);
  const displayIndices = React.useMemo(() => displayEntries.map(({ index }) => index), [displayEntries]);
  const displayIndexPositions = React.useMemo(() => {
    const positions = new Map<number, number>();
    displayIndices.forEach((index, position) => positions.set(index, position));
    return positions;
  }, [displayIndices]);
  const selectionAnchorPosition = selectionAnchor ? displayIndexPositions.get(selectionAnchor.rowIndex) ?? -1 : -1;
  const selectionFocusPosition = selectionFocus ? displayIndexPositions.get(selectionFocus.rowIndex) ?? -1 : -1;
  const selectedRange = selectionAnchor && selectionFocus && selectionAnchorPosition >= 0 && selectionFocusPosition >= 0
    ? {
        minPosition: Math.min(selectionAnchorPosition, selectionFocusPosition),
        maxPosition: Math.max(selectionAnchorPosition, selectionFocusPosition),
        minCol: Math.min(selectionAnchor.colIndex, selectionFocus.colIndex),
        maxCol: Math.max(selectionAnchor.colIndex, selectionFocus.colIndex),
      }
    : null;
  const selectedCellCount = selectedRange ? (selectedRange.maxPosition - selectedRange.minPosition + 1) * (selectedRange.maxCol - selectedRange.minCol + 1) : 0;
  const filterCount = activeColumnFilters.length + (gridSort ? 1 : 0);
  const pageCount = Math.max(1, Math.ceil(displayIndices.length / DRAFT_PAGE_SIZE));
  const safeDraftPage = Math.min(draftPage, pageCount - 1);
  const pagedDisplayIndices = React.useMemo(
    () => displayIndices.slice(safeDraftPage * DRAFT_PAGE_SIZE, (safeDraftPage + 1) * DRAFT_PAGE_SIZE),
    [displayIndices, safeDraftPage],
  );
  const filteredItems = React.useMemo(() => pagedDisplayIndices.map((index) => items[index]), [items, pagedDisplayIndices]);
  const activeVirtualRowHeight = tableMode === "spreadsheet" ? 42 : VIRTUAL_ROW_HEIGHT;
  const virtualStart = Math.max(0, Math.floor(draftScrollTop / activeVirtualRowHeight) - VIRTUAL_OVERSCAN);
  const virtualCount = Math.ceil(VIRTUAL_VIEWPORT_HEIGHT / activeVirtualRowHeight) + VIRTUAL_OVERSCAN * 2;
  const virtualEnd = Math.min(pagedDisplayIndices.length, virtualStart + virtualCount);
  const virtualDisplayIndices = React.useMemo(
    () => pagedDisplayIndices.slice(virtualStart, virtualEnd),
    [pagedDisplayIndices, virtualEnd, virtualStart],
  );
  const virtualPaddingTop = virtualStart * activeVirtualRowHeight;
  const virtualPaddingBottom = Math.max(0, (pagedDisplayIndices.length - virtualEnd) * activeVirtualRowHeight);
  const pageStart = displayIndices.length ? safeDraftPage * DRAFT_PAGE_SIZE + 1 : 0;
  const pageEnd = Math.min(displayIndices.length, (safeDraftPage + 1) * DRAFT_PAGE_SIZE);
  const finalPageCount = Math.max(1, Math.ceil(items.length / FINAL_PAGE_SIZE));
  const safeFinalPage = Math.min(finalPage, finalPageCount - 1);
  const finalPageStartIndex = safeFinalPage * FINAL_PAGE_SIZE;
  const finalPageEndIndex = Math.min(items.length, finalPageStartIndex + FINAL_PAGE_SIZE);
  const finalPageItems = items.slice(finalPageStartIndex, finalPageEndIndex);
  const selectedIndices = selectedRows.size ? Array.from(selectedRows).sort((a, b) => a - b) : [];
  const selectedRowIndex = selectedIndices.length === 1 ? selectedIndices[0] : null;
  const selectedItem = selectedRowIndex !== null ? items[selectedRowIndex] : null;
  const selectedItemBadges = selectedItem ? issueBadgesForItem(selectedItem) : [];
  const extractionSummary = React.useMemo(() => {
    const summary = items.reduce<Record<string, number>>((acc, item) => {
      const key = summaryKey(item);
      if (key) acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});
    return Object.entries(summary).sort((left, right) => right[1] - left[1]);
  }, [items]);
  const shownSummary = extractionSummary.slice(0, SUMMARY_LIMIT);
  const hiddenSummaryCount = Math.max(0, extractionSummary.length - shownSummary.length);

  function invalidateMaterialPlan() {
    setMaterialPlan(null);
  }

  async function refreshQuotes(activeId?: string) {
    const data = await listQuotes();
    setQuotes(data.map(quoteSummary));
    const nextId = activeId ?? (quote && data.some((row) => row.id === quote.id) ? quote.id : undefined);
    if (nextId) {
      setQuote(await getQuote(nextId));
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
    setMaterialPlan(isMaterialSection ? storedMaterialPlan(quote) : null);
    setDraftPage(0);
    setFinalPage(0);
    setHasUnsavedLocalEdits(false);
  }, [isFinalSection, isMaterialSection, quote]);

  React.useEffect(() => {
    setDraftPage(0);
  }, [columnFilters, gridSort, statusFilter, quote?.id]);

  React.useEffect(() => {
    setDraftScrollTop(0);
    if (draftGridRef.current) {
      draftGridRef.current.scrollTop = 0;
    }
  }, [columnFilters, gridSort, safeDraftPage, statusFilter, quote?.id]);

  React.useEffect(() => {
    setActiveCell(null);
    setSelectionAnchor(null);
    setSelectionFocus(null);
    setIsSelectingCells(false);
  }, [columnPreset, quote?.id, tableMode]);

  React.useEffect(() => {
    if (!isSelectingCells) return undefined;
    const stopSelecting = () => setIsSelectingCells(false);
    window.addEventListener("mouseup", stopSelecting);
    return () => window.removeEventListener("mouseup", stopSelecting);
  }, [isSelectingCells]);

  React.useEffect(() => {
    const refresh = () => setCurrentUser(getCurrentAppUser());
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  React.useEffect(() => {
    const saved = savedFiltersFor(section);
    if (saved?.queueFilter) setQueueFilter(saved.queueFilter);
    if (saved?.statusFilter) setStatusFilter(saved.statusFilter);
    if (saved?.columnPreset) setColumnPreset(saved.columnPreset);
    if (saved?.tableMode === "spreadsheet") setTableMode(saved.tableMode);
    filtersLoaded.current = true;
  }, [currentUser.role, section]);

  React.useEffect(() => {
    if (!filtersLoaded.current) return;
    persistSavedFilters(section, { queueFilter, statusFilter, columnPreset, tableMode });
  }, [columnPreset, queueFilter, section, statusFilter, tableMode]);

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
    setStartingExtraction(false);
    setSelectedRows(new Set());
    setPreviewUrl("");
    setStatusFilter("all");
    setQueueFilter("all");
    setColumnPreset("review");
    setTableMode(DEFAULT_TABLE_MODE);
    setBulkValues(BULK_DEFAULTS);
    setRfiText("");
    setSaving(false);
    setExporting(null);
    setIntakeCollapsed(false);
    router.replace(sectionBasePath);
  }

  async function openQuotationScreen() {
    if (!quote) return;
    const linkedQuoteId = getString(quote.stage_meta?.linked_quote_id);
    if (linkedQuoteId) {
      if (hasUnsavedLocalEdits) {
        const savedEnquiry = await savePatch({ items, quote_data: qd, quote_no: getString(qd.quote_no) } as Partial<Quote>);
        if (savedEnquiry) await syncLinkedQuotationFromEnquiry(savedEnquiry, savedEnquiry.items);
      }
      const linked = await getQuote(linkedQuoteId);
      setQuote(linked);
      rememberRecentQuote(linked);
      await refreshQuotes(linked.id);
      router.replace(`/quotes/final?quote=${linked.id}`);
      return;
    }
    const savedEnquiry = await savePatch({ items, quote_data: qd, quote_no: getString(qd.quote_no) } as Partial<Quote>);
    if (!savedEnquiry) return;
    const now = new Date().toISOString();
    const quotationMeta = appendActivity(
      {
        ...(savedEnquiry.stage_meta ?? {}),
        source_enquiry_id: savedEnquiry.id,
        source_enquiry_version: savedEnquiry.version,
        source_enquiry_quote_no: savedEnquiry.quote_no,
        created_from_enquiry_at: now,
      },
      {
        kind: "workflow",
        title: "Quotation created",
        detail: `Created from enquiry ${savedEnquiry.quote_no || savedEnquiry.id}`,
        user: currentUser.name || currentUser.id,
      },
    );
    const quotation = await createQuote({
      quote_no: savedEnquiry.quote_no,
      customer: savedEnquiry.customer,
      project_ref: savedEnquiry.project_ref,
      custom_label: savedEnquiry.custom_label,
      items: cloneJson(savedEnquiry.items),
      quote_data: cloneJson(savedEnquiry.quote_data),
      stage: "quote_prep",
      stage_meta: quotationMeta,
    } as Partial<Quote>);
    const enquiryMeta = appendActivity(
      {
        ...(savedEnquiry.stage_meta ?? {}),
        linked_quote_id: quotation.id,
        linked_quote_no: quotation.quote_no,
        linked_quote_version: quotation.version,
        linked_quote_created_at: now,
      },
      {
        kind: "workflow",
        title: "Linked quotation created",
        detail: quotation.quote_no || quotation.id,
        user: currentUser.name || currentUser.id,
      },
    );
    await patchQuote(savedEnquiry.id, { stage_meta: enquiryMeta } as Partial<Quote>);
    setQuote(quotation);
    rememberRecentQuote(quotation);
    await refreshQuotes(quotation.id);
    router.replace(`/quotes/final?quote=${quotation.id}`);
  }

  function closeQuotationScreen() {
    if (!quote) {
      router.replace("/quotes");
      return;
    }
    const sourceEnquiryId = getString(quote.stage_meta?.source_enquiry_id);
    router.replace(`/quotes?quote=${sourceEnquiryId || quote.id}`);
  }

  async function syncLinkedQuotationFromEnquiry(enquiry: Quote, nextItems: GasketItem[]) {
    if (isFinalSection) return;
    const linkedQuoteId = getString(enquiry.stage_meta?.linked_quote_id);
    if (!linkedQuoteId) return;
    try {
      const linked = await getQuote(linkedQuoteId);
      const currentQuoteData = { ...(linked.quote_data ?? {}) };
      const nextRevNo = nextRevisionNo(currentQuoteData.rev_no);
      const nextQuoteData = {
        ...currentQuoteData,
        rev_no: nextRevNo,
        rev_date: todayDisplayDate(),
      };
      const nextStageMeta = appendActivity(
        {
          ...(linked.stage_meta ?? {}),
          source_enquiry_id: enquiry.id,
          source_enquiry_version: enquiry.version,
          source_enquiry_updated_at: enquiry.updated_at,
        },
        {
          kind: "workflow",
          title: "Quotation revised from enquiry",
          detail: `Revision ${nextRevNo} created after enquiry update`,
          user: currentUser.name || currentUser.id,
        },
      );
      const updatedQuotation = await patchQuote(linked.id, {
        items: cloneJson(nextItems),
        quote_data: nextQuoteData,
        quote_no: linked.quote_no || getString(linked.quote_data?.quote_no),
        stage_meta: nextStageMeta,
      } as Partial<Quote>);
      setQuotes((prev) => prev.map((row) => (row.id === updatedQuotation.id ? quoteSummary(updatedQuotation) : row)));
      toast.success(`Linked quotation revised to rev ${nextRevNo}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Linked quotation revision failed");
    }
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
          setQuote(await getQuote(nextId));
        } else {
          setQuote(null);
        }
      }
      toast.success("Quote deleted");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Delete failed");
    }
  }

  async function updateQueueMeta(row: Quote, patch: Record<string, unknown>) {
    let nextStageMeta = { ...(row.stage_meta ?? {}), ...patch };
    const activityDetails = Object.entries(patch)
      .filter(([key]) => ["owner_id", "owner_name", "priority", "due_date", "clarification_status"].includes(key))
      .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value || "blank")}`);
    if (activityDetails.length) {
      nextStageMeta = appendActivity(nextStageMeta, {
        kind: patch.clarification_status ? "clarification" : patch.owner_id || patch.owner_name ? "owner" : patch.priority ? "priority" : "due_date",
        title: "Queue metadata updated",
        detail: activityDetails.join(", "),
        user: currentUser.name || currentUser.id,
      });
    }
    setQuotes((prev) => prev.map((item) => (item.id === row.id ? { ...item, stage_meta: nextStageMeta } : item)));
    if (quote?.id === row.id) {
      setQuote((current) => (current ? { ...current, stage_meta: nextStageMeta } : current));
    }
    try {
      const updated = await patchQuote(row.id, { stage_meta: nextStageMeta } as Partial<Quote>);
      setQuotes((prev) => prev.map((item) => (item.id === updated.id ? quoteSummary(updated) : item)));
      if (quote?.id === updated.id) setQuote(updated);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Workflow metadata save failed");
      refreshQuotes(quote?.id).catch((refreshError) => toast.error(refreshError.message));
    }
  }

  async function savePatch(payload: Partial<Quote>, success?: string): Promise<Quote | undefined> {
    if (!quote) return undefined;
    setSaving(true);
    try {
      const updated = await patchQuote(quote.id, payload);
      setQuote(updated);
      setHasUnsavedLocalEdits(false);
      setQuotes((prev) => prev.map((row) => (row.id === updated.id ? quoteSummary(updated) : row)));
      if (success) toast.success(success);
      return updated;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Save failed");
      return undefined;
    } finally {
      setSaving(false);
    }
  }

  async function updateItems(nextItems: GasketItem[], success?: string) {
    invalidateMaterialPlan();
    const updated = await savePatch({ items: nextItems } as Partial<Quote>, success);
    if (updated) await syncLinkedQuotationFromEnquiry(updated, nextItems);
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
      setStartingExtraction(true);
      const accepted = await createExtraction({
        quoteId: quote.id,
        sourceType,
        text: emailText,
        file,
        customer: quote.customer,
        projectRef: quote.project_ref,
      });
      addBackgroundJob({
        id: accepted.job_id,
        quoteId: quote.id,
        sourceType,
        label: `Smart Parse ${sourceType === "excel" ? "Excel" : "email"} enquiry`,
        startedAt: new Date().toISOString(),
      });
      invalidateMaterialPlan();
      setIntakeCollapsed(false);
      toast.info("Smart Parse is running in the background. You can keep working and will be notified when it finishes.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Extraction failed");
    } finally {
      setStartingExtraction(false);
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

  async function buildClarificationEmail() {
    if (!quote) return;
    try {
      const draft = await rfiDraft(quote.id);
      setRfiText(draft.text);
      const nextStageMeta = appendActivity(
        {
          ...(quote.stage_meta ?? {}),
          clarification_status: "requested",
          clarification_requested_at: new Date().toISOString(),
        },
        {
          kind: "clarification",
          title: "Clarification drafted",
          detail: `${Object.keys(draft.groups ?? {}).length} issue group(s) included`,
          user: currentUser.name || currentUser.id,
        },
      );
      setQuote((current) => (current ? { ...current, stage_meta: nextStageMeta } : current));
      await patchQuote(quote.id, { stage_meta: nextStageMeta } as Partial<Quote>);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not build clarification email");
    }
  }

  async function exportCurrent(type: "pdf", mode: "preview" | "download" = "download") {
    if (!quote) return;
    if (mode === "download" && !canExportFinal) {
      toast.error("Approval is required before downloading the quotation");
      return;
    }
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

  async function requestApproval() {
    if (!quote) return;
    const nextApproval: ApprovalState = {
      status: "pending",
      requested_by: currentUser.name || currentUser.id,
      requested_at: new Date().toISOString(),
      comments: approvalComment.trim(),
      score: qualityReport.score,
      risk_count: qualityReport.risks.length,
      required: pricingSummary.approvalRequired,
      required_reasons: pricingSummary.approvalReasons,
      required_changes: pricingSummary.approvalReasons.join("; "),
    };
    await savePatch(
      {
        items,
        quote_data: qd,
        quote_no: getString(qd.quote_no),
        stage_meta: appendActivity({ ...(quote.stage_meta ?? {}), approval: nextApproval }, {
          kind: "approval",
          title: "Approval requested",
          detail: pricingSummary.approvalReasons.join(", ") || approvalComment.trim() || "Approval requested",
          user: currentUser.name || currentUser.id,
        }),
      } as Partial<Quote>,
      "Approval requested",
    );
    setApprovalComment("");
  }

  async function decideApproval(status: "approved" | "rejected") {
    if (!quote || !canApprove) return;
    const nextApproval: ApprovalState = {
      ...approval,
      status,
      decided_by: currentUser.name || currentUser.id,
      decided_at: new Date().toISOString(),
      comments: approvalComment.trim() || approval.comments,
      score: qualityReport.score,
      risk_count: qualityReport.risks.length,
      required: pricingSummary.approvalRequired,
      required_reasons: pricingSummary.approvalReasons,
      required_changes: status === "rejected" ? approvalComment.trim() || "Revise pricing or resolve approval blockers" : "",
    };
    await savePatch(
      {
        items,
        quote_data: qd,
        quote_no: getString(qd.quote_no),
        stage_meta: appendActivity({ ...(quote.stage_meta ?? {}), approval: nextApproval }, {
          kind: "approval",
          title: status === "approved" ? "Approval granted" : "Approval rejected",
          detail: approvalComment.trim() || nextApproval.required_changes || status,
          user: currentUser.name || currentUser.id,
        }),
      } as Partial<Quote>,
      status === "approved" ? "Quotation approved" : "Quotation rejected",
    );
    setApprovalComment("");
  }

  async function markSent() {
    if (!quote) return;
    if (approval.status !== "approved") {
      toast.error("Approve the quotation before marking it sent");
      return;
    }
    const sentMeta = {
      ...(quote.stage_meta ?? {}),
      approval,
      sent_by: currentUser.name || currentUser.id,
      sent_at: new Date().toISOString(),
    };
    const advanced = await advanceQuoteStage(quote.id, "sent", "Approved quotation sent", appendActivity(sentMeta, {
      kind: "workflow",
      title: "Quotation sent",
      detail: "Approved quotation marked sent",
      user: currentUser.name || currentUser.id,
    }));
    setQuote(advanced);
    setQuotes((prev) => prev.map((row) => (row.id === advanced.id ? quoteSummary(advanced) : row)));
    toast.success("Quotation marked sent");
  }

  function updateItem(index: number, field: string, value: string) {
    invalidateMaterialPlan();
    const next = [...items];
    next[index] = setItemValue(next[index] ?? blankItem(index + 1), field, value);
    setQuote((current) => (current ? { ...current, items: next } : current));
    setHasUnsavedLocalEdits(true);
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
    setHasUnsavedLocalEdits(true);
    setSelectedRows(new Set());
  }

  async function deleteSelectedRows() {
    if (!quote) return;
    invalidateMaterialPlan();
    const selected = new Set(selectedIndices);
    setUndoItems({ label: "Restore deleted rows", items });
    await savePatch({
      items: renumber(items.filter((_, index) => !selected.has(index))),
      stage_meta: appendActivity(quote.stage_meta ?? {}, {
        kind: "items",
        title: "Rows deleted",
        detail: `${selected.size} row(s) deleted`,
        user: currentUser.name || currentUser.id,
      }),
    } as Partial<Quote>, "Rows deleted");
    setSelectedRows(new Set());
  }

  async function toggleRegretSelected() {
    if (!quote) return;
    invalidateMaterialPlan();
    const selected = new Set(selectedIndices);
    setUndoItems({ label: "Undo regret change", items });
    const next = items.map((item, index) => {
      if (!selected.has(index)) return item;
      const isRegret = item.status === "regret" || item.regret === true;
      return { ...item, regret: !isRegret, status: isRegret ? "check" : "regret" };
    });
    await savePatch({
      items: next,
      stage_meta: appendActivity(quote.stage_meta ?? {}, {
        kind: "items",
        title: "Regret toggled",
        detail: `${selected.size} row(s) changed`,
        user: currentUser.name || currentUser.id,
      }),
    } as Partial<Quote>, "Regret status updated");
    setSelectedRows(new Set());
  }

  async function restoreUndoItems() {
    if (!quote || !undoItems) return;
    await savePatch({
      items: undoItems.items,
      stage_meta: appendActivity(quote.stage_meta ?? {}, {
        kind: "items",
        title: "Undo restored",
        detail: undoItems.label,
        user: currentUser.name || currentUser.id,
      }),
    } as Partial<Quote>, "Rows restored");
    setUndoItems(null);
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

  async function createRevision() {
    if (!quote) return;
    setSaving(true);
    try {
      invalidateMaterialPlan();
      const saved = await patchQuote(quote.id, {
        customer: quote.customer,
        project_ref: quote.project_ref,
        custom_label: quote.custom_label,
        quote_no: quote.quote_no,
        items,
        quote_data: qd,
      } as Partial<Quote>);
      const revNo = nextRevisionNo(qd.rev_no);
      const revisionQuoteData = {
        ...cloneJson(qd),
        rev_no: revNo,
        rev_date: todayDisplayDate(),
      };
      const revision = await createQuote({
        quote_no: saved.quote_no,
        customer: saved.customer,
        project_ref: saved.project_ref,
        custom_label: saved.custom_label,
        items: cloneJson(saved.items),
        quote_data: revisionQuoteData,
        stage: "initial",
        stage_meta: {
          ...(saved.stage_meta ?? {}),
          revision_of_quote_id: saved.id,
          revision_no: revNo,
          revision_created_from_version: saved.version,
        },
      } as Partial<Quote>);
      setQuote(revision);
      setSelectedRows(new Set());
      setRfiText("");
      setIntakeCollapsed(Boolean(revision.items.length));
      await refreshQuotes(revision.id);
      router.replace(`/quotes?quote=${revision.id}`);
      toast.success(`Revision ${revNo} enquiry created`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create revision");
    } finally {
      setSaving(false);
    }
  }

  function updateQd(key: string, value: unknown) {
    const next = { ...qd, [key]: value };
    if (key === "currency") {
      next.fx_rate = defaultFx[getString(value)] ?? 1;
    }
    setQuote((current) => (current ? { ...current, quote_data: next, quote_no: getString(next.quote_no) } : current));
    setHasUnsavedLocalEdits(true);
  }

  const unitPrices = React.useMemo(() => Array.isArray(qd.unit_prices) ? qd.unit_prices.map((value) => toNumber(value)) : [], [qd.unit_prices]);
  const costPrices = React.useMemo(() => Array.isArray(qd.cost_prices) ? qd.cost_prices.map((value) => toNumber(value)) : [], [qd.cost_prices]);
  const targetMargins = React.useMemo(() => Array.isArray(qd.target_margins_pct) ? qd.target_margins_pct.map((value) => toNumber(value, 15)) : [], [qd.target_margins_pct]);
  const currency = getString(qd.currency) || "INR";
  const fxRate = toNumber(qd.fx_rate, defaultFx[currency] ?? 1);
  const discountPct = toNumber(qd.discount_pct);
  const gstPct = currency === "INR" ? toNumber(qd.gst_pct, 18) : 0;
  const discountApprovalPct = toNumber(qd.discount_approval_pct, 10);
  const minimumMarginPct = toNumber(qd.minimum_margin_pct, 15);
  const qualityReport = React.useMemo(() => evaluateQuoteQuality(quote, items, qd), [items, qd, quote]);
  const pricingSummary = React.useMemo(
    () => buildQuotePricingSummary({
      items,
      unitPrices,
      costPrices,
      targetMargins,
      discountPct,
      gstPct,
      riskCount: qualityReport.risks.filter((risk) => risk.severity === "high").length,
      fxRate,
      isForeignCurrency: currency !== "INR",
      discountApprovalPct,
      minimumMarginPct,
    }),
    [costPrices, currency, discountApprovalPct, discountPct, fxRate, gstPct, items, minimumMarginPct, qualityReport.risks, targetMargins, unitPrices],
  );
  const subtotal = pricingSummary.subtotal;
  const discount = pricingSummary.discount;
  const gst = pricingSummary.gst;
  const grandTotal = pricingSummary.grandTotal;
  const readyCount = items.filter((item) => item.status === "ready").length;
  const checkCount = items.filter((item) => item.status === "check").length;
  const missingCount = items.filter((item) => item.status === "missing").length;
  const actionCount = checkCount + missingCount;
  const readiness = items.length ? Math.round((readyCount / items.length) * 100) : 0;
  const approval = approvalState(quote);
  const canApprove = canApproveQuotes(currentUser.role);
  const canExportFinal = approval.status === "approved" || !pricingSummary.approvalRequired;
  const visibleQuotes = quotes.filter((row) => {
    if (isFinalSection) {
      if (!FINAL_STAGES.has(row.stage)) return false;
    } else if (isMaterialSection) {
      if (!MATERIAL_STAGES.has(row.stage)) return false;
    } else if (!DRAFT_STAGES.has(row.stage)) {
      return false;
    }
    if (queueFilter === "my_work" && row.stage_meta?.owner_id !== currentUser.id && row.stage_meta?.owner_name !== currentUser.name) return false;
    if (queueFilter === "due_today" && quoteDueState(row) !== "today") return false;
    if (queueFilter === "delayed" && quoteDueState(row) !== "delayed") return false;
    if (queueFilter === "clarification" && !quoteHasClarification(row)) return false;
    if (queueFilter === "high_risk" && !quoteIsHighRisk(row)) return false;
    if (queueFilter === "high_value" && !quoteIsHighValue(row)) return false;
    if (queueFilter.startsWith("stage:") && row.stage !== queueFilter.slice("stage:".length)) return false;
    const term = search.toLowerCase();
    return !term || row.customer.toLowerCase().includes(term) || row.project_ref.toLowerCase().includes(term) || row.quote_no.toLowerCase().includes(term);
  });

  async function openQuote(row: Quote) {
    try {
      invalidateMaterialPlan();
      const active = await getQuote(row.id);
      setQuote(active);
      rememberRecentQuote(active);
      setSelectedRows(new Set());
      setRfiText("");
      router.replace(`${sectionBasePath}?quote=${row.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not open quote");
    }
  }

  function setColumnFilterValue(field: string, value: string) {
    setColumnFilters((current) => {
      const next = { ...current };
      if (value.trim()) next[field] = value;
      else delete next[field];
      return next;
    });
  }

  function toggleColumnSort(field: string) {
    setGridSort((current) => {
      if (!current || current.field !== field) return { field, direction: "asc" };
      if (current.direction === "asc") return { field, direction: "desc" };
      return null;
    });
  }

  function clearGridFilters() {
    setColumnFilters({});
    setGridSort(null);
  }

  function selectGridCell(rowIndex: number, colIndex: number, extend: boolean) {
    const nextCell = { rowIndex, colIndex };
    const anchor = extend && selectionAnchor ? selectionAnchor : nextCell;
    setActiveCell(nextCell);
    setSelectionAnchor(anchor);
    setSelectionFocus(nextCell);
    const anchorPosition = displayIndexPositions.get(anchor.rowIndex) ?? -1;
    const focusPosition = displayIndexPositions.get(nextCell.rowIndex) ?? -1;
    let nextSelectedRows: Set<number>;
    if (anchorPosition >= 0 && focusPosition >= 0) {
      const start = Math.min(anchorPosition, focusPosition);
      const end = Math.max(anchorPosition, focusPosition);
      nextSelectedRows = new Set(displayIndices.slice(start, end + 1));
    } else {
      nextSelectedRows = new Set([rowIndex]);
    }
    setSelectedRows((current) => (sameNumberSet(current, nextSelectedRows) ? current : nextSelectedRows));
  }

  function focusGridCell(rowIndex: number, colIndex: number) {
    window.requestAnimationFrame(() => {
      const cell = draftGridRef.current?.querySelector<HTMLElement>(`[data-grid-row="${rowIndex}"][data-grid-col="${colIndex}"]`);
      const focusTarget = cell?.querySelector<HTMLElement>("input, textarea, button, [tabindex]");
      (focusTarget ?? cell)?.focus();
    });
  }

  function moveActiveGridCell(rowDelta: number, colDelta: number, extend: boolean) {
    if (!activeCell || !displayIndices.length || !activeTableColumns.length) return;
    const currentPosition = Math.max(0, displayIndexPositions.get(activeCell.rowIndex) ?? -1);
    const nextPosition = Math.max(0, Math.min(displayIndices.length - 1, currentPosition + rowDelta));
    const nextCol = Math.max(0, Math.min(activeTableColumns.length - 1, activeCell.colIndex + colDelta));
    const nextRow = displayIndices[nextPosition];
    selectGridCell(nextRow, nextCol, extend);
    focusGridCell(nextRow, nextCol);
  }

  function isGridCellSelected(rowIndex: number, colIndex: number) {
    if (!selectedRange) return false;
    const position = displayIndexPositions.get(rowIndex) ?? -1;
    return position >= selectedRange.minPosition && position <= selectedRange.maxPosition && colIndex >= selectedRange.minCol && colIndex <= selectedRange.maxCol;
  }

  function isActiveGridCell(rowIndex: number, colIndex: number) {
    return activeCell?.rowIndex === rowIndex && activeCell.colIndex === colIndex;
  }

  function applyGridPaste(text: string) {
    const parsed = parseClipboardTable(text);
    if (!parsed.length || !activeTableColumns.length) return false;
    const startCell = activeCell ?? selectionAnchor;
    if (!startCell) return false;
    const startPosition = selectedRange?.minPosition ?? displayIndexPositions.get(startCell.rowIndex) ?? -1;
    const startCol = selectedRange?.minCol ?? startCell.colIndex;
    if (startPosition < 0 || startCol < 0) return false;
    const singleValueFill = parsed.length === 1 && parsed[0].length === 1 && Boolean(selectedRange && selectedCellCount > 1);
    const rowCount = singleValueFill && selectedRange ? selectedRange.maxPosition - selectedRange.minPosition + 1 : parsed.length;
    const colCount = singleValueFill && selectedRange ? selectedRange.maxCol - selectedRange.minCol + 1 : Math.max(...parsed.map((row) => row.length));
    const next = [...items];
    let changed = 0;
    for (let rowOffset = 0; rowOffset < rowCount; rowOffset += 1) {
      const itemIndex = displayIndices[startPosition + rowOffset];
      if (itemIndex === undefined || !next[itemIndex]) continue;
      let row = next[itemIndex];
      for (let colOffset = 0; colOffset < colCount; colOffset += 1) {
        const column = activeTableColumns[startCol + colOffset];
        if (!column || !isEditableGridColumn(column)) continue;
        const rawValue = singleValueFill ? parsed[0][0] : parsed[rowOffset]?.[colOffset] ?? "";
        const value = column.kind === "checkbox"
          ? ["1", "TRUE", "YES", "Y"].includes(rawValue.trim().toUpperCase()) ? "true" : "false"
          : rawValue;
        row = setItemValue(row, column.field, value);
        changed += 1;
      }
      next[itemIndex] = row;
    }
    if (!changed) {
      toast.error("Paste did not target any editable cells");
      return false;
    }
    setUndoItems({ label: "Undo paste", items });
    invalidateMaterialPlan();
    setQuote((current) => (current ? { ...current, items: next } : current));
    setHasUnsavedLocalEdits(true);
    toast.success(`Pasted ${changed} cell${changed === 1 ? "" : "s"}`);
    return true;
  }

  function copyGridSelection(event: React.ClipboardEvent<HTMLDivElement>) {
    if (!selectedRange) return;
    const rows: string[] = [];
    for (let position = selectedRange.minPosition; position <= selectedRange.maxPosition; position += 1) {
      const rowIndex = displayIndices[position];
      const item = items[rowIndex];
      if (!item) continue;
      const values: string[] = [];
      for (let colIndex = selectedRange.minCol; colIndex <= selectedRange.maxCol; colIndex += 1) {
        const column = activeTableColumns[colIndex];
        values.push(column ? columnValue(item, column) : "");
      }
      rows.push(values.join("\t"));
    }
    event.clipboardData.setData("text/plain", rows.join("\n"));
    event.preventDefault();
  }

  function clearSelectedGridCells() {
    if (!selectedRange) return false;
    const next = [...items];
    let changed = 0;
    for (let position = selectedRange.minPosition; position <= selectedRange.maxPosition; position += 1) {
      const rowIndex = displayIndices[position];
      if (rowIndex === undefined || !next[rowIndex]) continue;
      let row = next[rowIndex];
      for (let colIndex = selectedRange.minCol; colIndex <= selectedRange.maxCol; colIndex += 1) {
        const column = activeTableColumns[colIndex];
        if (!column || !isEditableGridColumn(column)) continue;
        row = setItemValue(row, column.field, column.kind === "checkbox" ? "false" : "");
        changed += 1;
      }
      next[rowIndex] = row;
    }
    if (!changed) return false;
    setUndoItems({ label: "Undo clear", items });
    invalidateMaterialPlan();
    setQuote((current) => (current ? { ...current, items: next } : current));
    setHasUnsavedLocalEdits(true);
    return true;
  }

  function handleGridKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (tableMode !== "spreadsheet") return;
    const target = event.target as HTMLElement | null;
    const targetTag = target?.tagName;
    const inDescriptionEditor = targetTag === "TEXTAREA";
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
      if (!displayIndices.length || !activeTableColumns.length) return;
      event.preventDefault();
      const first = { rowIndex: displayIndices[0], colIndex: 0 };
      const last = { rowIndex: displayIndices[displayIndices.length - 1], colIndex: activeTableColumns.length - 1 };
      setActiveCell(first);
      setSelectionAnchor(first);
      setSelectionFocus(last);
      const nextSelectedRows = new Set(displayIndices);
      setSelectedRows((current) => (sameNumberSet(current, nextSelectedRows) ? current : nextSelectedRows));
      return;
    }
    if ((event.key === "Delete" || event.key === "Backspace") && selectedCellCount > 1) {
      if (clearSelectedGridCells()) event.preventDefault();
      return;
    }
    if (event.key === "Escape") {
      setSelectionAnchor(activeCell);
      setSelectionFocus(activeCell);
      return;
    }
    if (event.key === "Tab") {
      event.preventDefault();
      moveActiveGridCell(0, event.shiftKey ? -1 : 1, false);
      return;
    }
    if (event.key === "Enter" && !inDescriptionEditor) {
      event.preventDefault();
      moveActiveGridCell(event.shiftKey ? -1 : 1, 0, false);
      return;
    }
    if (inDescriptionEditor || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveActiveGridCell(-1, 0, event.shiftKey);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      moveActiveGridCell(1, 0, event.shiftKey);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      moveActiveGridCell(0, -1, event.shiftKey);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      moveActiveGridCell(0, 1, event.shiftKey);
    }
  }

  function renderGridCell(index: number, item: GasketItem, column: TableColumn) {
    const rawValue = item[column.field];
    const validation = validateItemField(item, column.field);
    const cellClass = column.field === "confidence" ? confidenceClass(rawValue) : validationClass(validation?.severity);
    const inputClass = tableMode === "spreadsheet"
      ? "h-8 w-full min-w-0 rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none focus-visible:ring-1 focus-visible:ring-ring"
      : GRID_INPUT_CLASS;
    const textareaClass = tableMode === "spreadsheet"
      ? "h-8 w-full min-w-0 resize-none rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none outline-none focus:ring-1 focus:ring-ring"
      : GRID_TEXTAREA_CLASS;
    if (column.field === "status") {
      return (
        <div className="flex h-7 items-center gap-1.5 px-2 text-xs">
          {statusIcon[getString(item.status)]}
          <span className="capitalize">{getString(item.status)}</span>
        </div>
      );
    }
    if (column.field === "flags") {
      return (
        <textarea
          className={`${textareaClass} ${GRID_READONLY_CLASS} ${cellClass}`}
          value={notesFor(item)}
          readOnly
          title={validation?.message}
        />
      );
    }
    if (column.field === "line_no" || column.field === "confidence") {
      return <Input className={`${inputClass} ${GRID_READONLY_CLASS} ${cellClass}`} value={getString(rawValue)} readOnly title={validation?.message} />;
    }
    if (column.field === "ggpl_description" || column.kind === "readonly") {
      return (
        <textarea
          className={`${textareaClass} ${GRID_READONLY_CLASS} ${cellClass}`}
          value={getString(rawValue)}
          readOnly
          title={validation?.message}
        />
      );
    }
    if (column.kind === "textarea") {
      return (
        <textarea
          className={`${textareaClass} ${cellClass}`}
          value={getString(rawValue)}
          onChange={(event) => updateItem(index, column.field, event.target.value)}
          title={validation?.message}
        />
      );
    }
    if (column.kind === "select") {
      return (
        <Select value={getString(rawValue) || BLANK_SELECT_VALUE} onValueChange={(value) => updateItem(index, column.field, value === BLANK_SELECT_VALUE ? "" : value)}>
          <SelectTrigger className={`${inputClass} ${cellClass} min-w-28 justify-between`} title={validation?.message}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(column.options ?? []).map((value) => <SelectItem key={value || `${column.field}-blank`} value={value || BLANK_SELECT_VALUE}>{value || "(blank)"}</SelectItem>)}
          </SelectContent>
        </Select>
      );
    }
    if (column.kind === "checkbox") {
      return (
        <div className="flex h-7 items-center justify-center">
          <input
            type="checkbox"
            checked={item.status === "regret" || item.regret === true}
            onChange={(event) => {
              const next = [...items];
              next[index] = { ...item, regret: event.target.checked, status: event.target.checked ? "regret" : "check" };
              invalidateMaterialPlan();
              setQuote((current) => (current ? { ...current, items: next } : current));
            }}
            aria-label={`Regret row ${index + 1}`}
          />
        </div>
      );
    }
    return (
      <Input
        className={`${inputClass} ${cellClass}`}
        type={column.kind === "number" ? "number" : "text"}
        value={getString(rawValue)}
        onChange={(event) => updateItem(index, column.field, event.target.value)}
        title={validation?.message}
      />
    );
  }

  async function generateMaterialPlan() {
    if (!quote) return;
    const nextPlan = buildMaterialPlan(items, materialConfig);
    setMaterialPlan(nextPlan);
    await savePatch(
      {
        stage_meta: {
          ...(quote.stage_meta ?? {}),
          material_plan: nextPlan,
          material_plan_updated_at: new Date().toISOString(),
        },
      } as Partial<Quote>,
      "Material plan saved",
    );
  }

  async function saveMaterialPlan(plan: MaterialPlan | null = materialPlan) {
    if (!quote || !plan) return;
    await savePatch(
      {
        stage_meta: {
          ...(quote.stage_meta ?? {}),
          material_plan: plan,
          material_plan_updated_at: new Date().toISOString(),
        },
      } as Partial<Quote>,
      "Material plan saved",
    );
  }

  async function clearMaterialPlan() {
    if (!quote) return;
    const nextStageMeta = { ...(quote.stage_meta ?? {}) };
    delete nextStageMeta.material_plan;
    delete nextStageMeta.material_plan_updated_at;
    setMaterialPlan(null);
    await savePatch({ stage_meta: nextStageMeta } as Partial<Quote>, "Material plan cleared");
  }

  function updatePlanRow(index: number, patch: Partial<MaterialPlan["rows"][number]>) {
    setMaterialPlan((current) => {
      if (!current) return current;
      const nextRows = current.rows.map((row, rowIndex) => {
        if (rowIndex !== index) return row;
        const nextRow = { ...row, ...patch };
        const required = nextRow.reqd_qty_sheets ?? nextRow.reqd_qty_kg ?? 0;
        const available = toNumber(nextRow.available_qty, 0);
        const reserved = toNumber(nextRow.reserved_qty, 0);
        const shortage = Math.max(0, required + reserved - available);
        return {
          ...nextRow,
          shortage_qty: shortage,
          suggested_purchase_qty: patch.suggested_purchase_qty === undefined ? shortage : toNumber(nextRow.suggested_purchase_qty, shortage),
        };
      });
      const grouped = nextRows.reduce<MaterialPlan["grouped_summary"]>((acc, row) => {
        const group = `${row.type} / ${row.thickness_mm ?? "-"} mm / ${row.preferred_vendor || "Vendor TBD"}`;
        const currentGroup = acc.find((item) => item.group === group);
        if (currentGroup) {
          currentGroup.rows += 1;
          currentGroup.shortage_qty += row.shortage_qty;
          currentGroup.suggested_purchase_qty += row.suggested_purchase_qty;
          currentGroup.estimated_material_cost += row.estimated_material_cost;
        } else {
          acc.push({
            group,
            rows: 1,
            shortage_qty: row.shortage_qty,
            suggested_purchase_qty: row.suggested_purchase_qty,
            estimated_material_cost: row.estimated_material_cost,
          });
        }
        return acc;
      }, []);
      return { ...current, rows: nextRows, grouped_summary: grouped };
    });
    setHasUnsavedLocalEdits(true);
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
                {isFinalSection ? "Quotation queue" : isMaterialSection ? "Material planning queue" : "Enquiry queue"}
              </div>
              <div>
                <h2 className="text-2xl font-semibold tracking-normal">{isFinalSection ? "Quotations" : isMaterialSection ? "Material planning" : "Enquiry"}</h2>
                <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                  {isFinalSection
                    ? "Prepared and completed quotations are listed here for review."
                    : isMaterialSection
                      ? "Select a cleaned enquiry to generate starter stock sizes, estimated weights, and review notes."
                    : "Email and Excel enquiries move through enquiry cleanup before quotation preparation."}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {isDraftSection && (
                <Button onClick={startQuote}>
                  <Plus className="h-4 w-4" />
                  New enquiry
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
              <CardTitle>{isFinalSection ? "Quotation queue" : isMaterialSection ? "Material planning queue" : "Enquiry queue"}</CardTitle>
              <div className="text-sm text-muted-foreground">{visibleQuotes.length} workspace{visibleQuotes.length === 1 ? "" : "s"}</div>
            </div>
            <div className="relative w-full md:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input className="pl-9" placeholder="Search customer, project, quote no" value={search} onChange={(event) => setSearch(event.target.value)} />
            </div>
            <Select value={queueFilter} onValueChange={setQueueFilter}>
              <SelectTrigger className="w-full md:w-48"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All work</SelectItem>
                <SelectItem value="my_work">My work</SelectItem>
                <SelectItem value="due_today">Due today</SelectItem>
                <SelectItem value="delayed">Delayed</SelectItem>
                <SelectItem value="clarification">Clarification</SelectItem>
                <SelectItem value="high_risk">High risk</SelectItem>
                <SelectItem value="high_value">High value</SelectItem>
                <SelectItem value="stage:initial">Stage: enquiry</SelectItem>
                <SelectItem value="stage:review">Stage: review</SelectItem>
                <SelectItem value="stage:quote_prep">Stage: quote prep</SelectItem>
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-hidden">
              <Table>
                <TableHeader>
                    <TableRow>
                      <TableHead>Workspace</TableHead>
                      <TableHead className="w-36">Owner</TableHead>
                      <TableHead className="w-32">Priority</TableHead>
                      <TableHead className="w-40">Due / age</TableHead>
                      <TableHead className="w-48">Readiness</TableHead>
                      <TableHead className="w-28">Items</TableHead>
                      <TableHead className="w-44">Value / next action</TableHead>
                      <TableHead className="w-40">Updated</TableHead>
                      <TableHead className="w-28 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleQuotes.map((row) => (
                    <QuoteSummaryRow key={row.id} quote={row} section={section} onOpen={openQuote} onDelete={removeQuote} onMetaChange={updateQueueMeta} />
                  ))}
                  {!visibleQuotes.length && (
                    <TableRow>
                      <TableCell colSpan={9} className="py-14 text-center">
                        <div className="mx-auto flex max-w-sm flex-col items-center gap-3 text-sm text-muted-foreground">
                          <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-background">
                            {isFinalSection ? <FileSpreadsheet className="h-5 w-5" /> : isMaterialSection ? <Layers3 className="h-5 w-5" /> : <Inbox className="h-5 w-5" />}
                          </div>
                          <div>{isFinalSection ? "No quotes are ready for quotation yet." : isMaterialSection ? "No enquiries are ready for material planning." : "No enquiries match the current search."}</div>
                          {isDraftSection && (
                            <Button onClick={startQuote}>
                              <Plus className="h-4 w-4" />
                              New enquiry
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
              {revisionLabel(quote) && <Badge variant="outline">{revisionLabel(quote)}</Badge>}
              {saving && <span className="inline-flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving</span>}
              {!saving && hasUnsavedLocalEdits && <Badge variant="warning">Unsaved edits</Badge>}
            </div>
            <div>
              <h2 className="truncate text-2xl font-semibold tracking-normal">{quote.customer || quote.quote_no || "Untitled enquiry"}</h2>
              <div className="mt-1 truncate text-sm text-muted-foreground">{quote.project_ref || quote.id}</div>
            </div>
            {!isFinalSection && (
              <div className="grid gap-3 sm:grid-cols-5">
                <SummaryTile label="Items" value={items.length} detail={`${filteredItems.length} on this page`} />
                <SummaryTile label="RFQ score" value={`${qualityReport.score}%`} detail={`${readiness}% item ready`} tone={qualityReport.score >= 80 ? "ready" : qualityReport.score >= 60 ? "check" : "missing"} />
                <SummaryTile label="Ready" value={readyCount} detail={`${readiness}% complete`} tone="ready" />
                <SummaryTile label="Review" value={checkCount} detail="Defaults used" tone="check" />
                <SummaryTile label="Risks" value={qualityReport.risks.length} detail={`${qualityReport.risks.filter((risk) => risk.severity === "high").length} high`} tone={qualityReport.risks.some((risk) => risk.severity === "high") ? "missing" : qualityReport.risks.length ? "check" : "ready"} />
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
                  New enquiry
                </Button>
                <Button variant="secondary" onClick={createRevision}>
                  <RefreshCw className="h-4 w-4" />
                  Revision
                </Button>
                <Button onClick={openQuotationScreen} disabled={!items.length}>
                  <ArrowRight className="h-4 w-4" />
                  Quotation
                </Button>
              </>
            )}
          </div>
        </div>

        {!isFinalSection && (
          <div className="mt-5 grid gap-3 border-t pt-5 lg:grid-cols-[1fr_1fr]">
            <div className="rounded-md border p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">RFQ completeness</div>
                  <div className="text-xs text-muted-foreground">
                    Commercial {qualityReport.quoteScore}% / Technical {qualityReport.technicalScore}% / Risk {qualityReport.riskScore}%
                  </div>
                </div>
                <Badge variant={qualityReport.score >= 80 ? "secondary" : qualityReport.score >= 60 ? "warning" : "outline"}>{qualityReport.score}%</Badge>
              </div>
              <div className="mt-3">
                <ProgressBar value={qualityReport.score} />
              </div>
              {qualityReport.missing.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {qualityReport.missing.slice(0, 5).map((item) => <Badge key={item} variant="outline">{item}</Badge>)}
                  {qualityReport.missing.length > 5 && <Badge variant="muted">+{qualityReport.missing.length - 5} more</Badge>}
                </div>
              )}
            </div>

            <div className="rounded-md border p-3">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">Technical risk check</div>
                  <div className="text-xs text-muted-foreground">Flags missing data, standard mismatches, and non-standard items.</div>
                </div>
                <Badge variant={qualityReport.risks.some((risk) => risk.severity === "high") ? "warning" : "secondary"}>
                  {qualityReport.risks.length} risk{qualityReport.risks.length === 1 ? "" : "s"}
                </Badge>
              </div>
              {qualityReport.risks.length === 0 ? (
                <div className="text-sm text-muted-foreground">No technical risks detected from the current enquiry data.</div>
              ) : (
                <div className="space-y-2">
                  {qualityReport.risks.slice(0, 5).map((risk) => (
                    <div key={`${risk.title}-${risk.detail}`} className="rounded-md bg-muted/40 px-2 py-1.5 text-xs">
                      <span className="font-medium">{risk.title}</span>
                      <span className="text-muted-foreground"> - {risk.detail}</span>
                      {risk.rows?.length ? <span className="text-muted-foreground"> Rows {risk.rows.slice(0, 8).join(", ")}</span> : null}
                    </div>
                  ))}
                  {qualityReport.risks.length > 5 && <div className="text-xs text-muted-foreground">+{qualityReport.risks.length - 5} more risk checks</div>}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mt-5 grid gap-3 border-t pt-5 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <Field label="Customer" value={quote.customer} onChange={(value) => setQuote({ ...quote, customer: value })} />
          <Field label="Project / PO reference" value={quote.project_ref} onChange={(value) => setQuote({ ...quote, project_ref: value })} />
          <Button
            variant="secondary"
            onClick={() => savePatch({ customer: quote.customer, project_ref: quote.project_ref } as Partial<Quote>, "Enquiry details saved")}
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
                <CardTitle>Enquiry intake</CardTitle>
                <div className="text-sm text-muted-foreground">
                  {intakeCollapsed && !startingExtraction ? `${items.length} item(s) captured. Intake is minimized.` : "Email, Excel, and manual item capture"}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {startingExtraction && (
                  <Badge variant="outline" className="w-fit">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Starting
                  </Badge>
                )}
                {(items.length > 0 || intakeCollapsed) && !startingExtraction && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIntakeCollapsed((value) => !value)}
                    aria-label={intakeCollapsed ? "Expand enquiry intake" : "Minimize enquiry intake"}
                    title={intakeCollapsed ? "Expand enquiry intake" : "Minimize enquiry intake"}
                  >
                    {intakeCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          {intakeCollapsed && !startingExtraction ? (
            <CardContent className="pt-5">
              <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
                Intake minimized. Review and clean the extracted enquiry below.
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
                    <Button onClick={() => runExtraction("email")} disabled={startingExtraction}>
                      {startingExtraction ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      Process email enquiry
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
                  <Button className="mt-3" onClick={() => runExtraction("excel", excelFile)} disabled={startingExtraction}>
                    <Upload className="h-4 w-4" />
                    Process Excel enquiry
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
              {startingExtraction && (
                <div className="mt-4 rounded-md border bg-muted/40 p-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Starting Smart Parse background job
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </Card>
      )}

      {isDraftSection && (
        <>
          {tableMode === "guided" && (
            <>
              <TechnicalIssuesPanel
                items={items}
                onSelectRow={(index) => {
                  setSelectedRows(new Set([index]));
                  setStatusFilter("all");
                }}
                onBuildClarification={buildClarificationEmail}
              />
              <QuoteTimeline quote={quote} />
            </>
          )}
          <Card className={tableMode === "spreadsheet" ? "rounded-none shadow-none" : ""}>
            <CardHeader className={`sticky top-16 z-20 border-b bg-card/95 backdrop-blur ${tableMode === "spreadsheet" ? "px-3 py-3" : ""}`}>
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="space-y-1">
                  <CardTitle>Enquiry items</CardTitle>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                    <span>{items.length} items</span>
                    <span>{readyCount} ready</span>
                    <span>{actionCount} need review</span>
                    {selectedIndices.length > 0 && <Badge variant="outline">{selectedIndices.length} selected</Badge>}
                    {tableMode === "spreadsheet" && <Badge variant="muted">{selectedCellCount ? `${selectedCellCount} cells` : "Excel-style editor"}</Badge>}
                    {filterCount > 0 && <Badge variant="outline">{filterCount} grid filter{filterCount === 1 ? "" : "s"}</Badge>}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Select value={tableMode} onValueChange={(value) => setTableMode(value as "guided" | "spreadsheet")}>
                    <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="spreadsheet">Classic full table</SelectItem>
                      <SelectItem value="guided">Guided review</SelectItem>
                    </SelectContent>
                  </Select>
                  {tableMode === "guided" ? (
                    <Select value={columnPreset} onValueChange={setColumnPreset}>
                      <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="review">Review columns</SelectItem>
                        <SelectItem value="commercial">Commercial</SelectItem>
                        <SelectItem value="soft_cut">Soft cut</SelectItem>
                        <SelectItem value="spiral_wound">Spiral wound</SelectItem>
                        <SelectItem value="rtj">RTJ</SelectItem>
                        <SelectItem value="kammprofile">Kammprofile</SelectItem>
                        <SelectItem value="dji">DJI</SelectItem>
                        <SelectItem value="isk">ISK</SelectItem>
                        <SelectItem value="full_technical">Full technical</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <Badge variant="outline" className="h-10 rounded-none px-3 text-xs">
                      {activeTableColumns.length} columns
                    </Badge>
                  )}
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="issues">Issues</SelectItem>
                      <SelectItem value="missing">Missing</SelectItem>
                      <SelectItem value="missing_size">Missing size</SelectItem>
                      <SelectItem value="missing_material">Missing material</SelectItem>
                      <SelectItem value="missing_rating">Missing rating/class</SelectItem>
                      <SelectItem value="low_confidence">Low confidence</SelectItem>
                      <SelectItem value="drawing_required">Drawing required</SelectItem>
                      <SelectItem value="duplicate_likely">Duplicate likely</SelectItem>
                      <SelectItem value="non_gasket">Non-gasket</SelectItem>
                      <SelectItem value="regret">Regret</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button variant="secondary" onClick={() => setSelectedRows(new Set(displayIndices))}>Select all</Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setSelectedRows(new Set());
                      setActiveCell(null);
                      setSelectionAnchor(null);
                      setSelectionFocus(null);
                    }}
                  >
                    Clear
                  </Button>
                  <Button variant="secondary" onClick={clearGridFilters} disabled={!filterCount}>Clear filters</Button>
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
                    Quotation
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className={tableMode === "spreadsheet" ? "space-y-3 p-3" : "space-y-4 pt-5"}>
              <div className={`flex flex-wrap gap-2 ${tableMode === "spreadsheet" ? "rounded-none border bg-muted/20 p-2" : ""}`}>
                <Button variant="secondary" onClick={() => recomputeRows(selectedIndices.length ? selectedIndices : displayIndices)}>
                  <RefreshCw className="h-4 w-4" />
                  {tableMode === "spreadsheet" ? "Update Descriptions" : `Update ${selectedIndices.length ? "selected" : "visible"}`}
                </Button>
                <Button variant="secondary" onClick={() => reprocessRows()}>
                  {startingExtraction ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  {tableMode === "spreadsheet" ? "Reprocess Text" : `Smart Parse ${selectedIndices.length ? "selected" : "visible"}`}
                </Button>
                <Button variant="destructive" onClick={deleteSelectedRows} disabled={!selectedIndices.length}>
                  <Trash2 className="h-4 w-4" />
                  {tableMode === "spreadsheet" ? `Delete (${selectedIndices.length || "none selected"})` : `Delete ${selectedIndices.length ? `(${selectedIndices.length})` : ""}`}
                </Button>
                <Button variant="secondary" onClick={toggleRegretSelected} disabled={!selectedIndices.length}>
                  {tableMode === "spreadsheet" ? `Regret (${selectedIndices.length || "none selected"})` : "Toggle regret"}
                </Button>
                {undoItems && (
                  <Button variant="secondary" onClick={restoreUndoItems}>
                    <Undo2 className="h-4 w-4" />
                    {undoItems.label}
                  </Button>
                )}
              </div>

              <details className={tableMode === "spreadsheet" ? "border p-2" : "rounded-md border p-3"}>
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

              <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_380px]">
                <div className="min-w-0 space-y-3">
              <div className={`flex flex-wrap items-center justify-between gap-3 border bg-muted/30 px-3 py-2 text-sm ${tableMode === "spreadsheet" ? "rounded-none" : "rounded-md"}`}>
                <div className="text-muted-foreground">
                  Showing {pageStart}-{pageEnd} of {displayIndices.length} visible row(s).
                  {tableMode === "spreadsheet"
                    ? " Click or drag cells to select ranges. Paste Excel rows directly into the selected cell range."
                    : isLargeDraft
                      ? " Compact columns are shown for large enquiries; select one row to edit in the side panel."
                      : " Large enquiries are paged to keep the browser responsive."}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setDraftPage((page) => Math.max(0, page - 1))}
                    disabled={safeDraftPage <= 0}
                  >
                    Previous
                  </Button>
                  <span className="text-xs text-muted-foreground">Page {safeDraftPage + 1} of {pageCount}</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setDraftPage((page) => Math.min(pageCount - 1, page + 1))}
                    disabled={safeDraftPage >= pageCount - 1}
                  >
                    Next
                  </Button>
                </div>
              </div>

              <div
                ref={draftGridRef}
                tabIndex={0}
                className={`max-h-[620px] overflow-auto border ${tableMode === "spreadsheet" ? "rounded-none bg-background" : "rounded-md"}`}
                onCopy={copyGridSelection}
                onKeyDown={handleGridKeyDown}
                onPaste={(event) => {
                  if (tableMode !== "spreadsheet") return;
                  const text = event.clipboardData.getData("text/plain");
                  if (text && applyGridPaste(text)) event.preventDefault();
                }}
                onScroll={(event) => setDraftScrollTop(event.currentTarget.scrollTop)}
              >
                <Table className={`w-max min-w-full border-collapse text-xs ${tableMode === "spreadsheet" ? "[&_td]:border-r [&_td]:border-b [&_th]:border-r [&_th]:border-b" : ""}`}>
                  <TableHeader className={tableMode === "spreadsheet" ? "sticky top-0 z-30 bg-muted" : "sticky top-0 z-30 bg-card"}>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className={`sticky left-0 z-40 h-8 w-10 border-r px-2 text-center ${tableMode === "spreadsheet" ? "bg-muted" : "bg-card"}`}>
                        {tableMode === "spreadsheet" ? "☑" : "Sel"}
                      </TableHead>
                      {tableMode !== "spreadsheet" && <TableHead className="sticky left-10 z-40 h-8 w-20 border-r bg-card px-2 text-center">Tools</TableHead>}
                      {activeTableColumns.map((column) => (
                        <TableHead key={column.label} className={`${column.width ?? "min-w-36"} whitespace-nowrap border-r px-2 py-1 text-xs font-semibold ${tableMode === "spreadsheet" ? "bg-muted" : "bg-card"}`}>
                          <div className="flex min-h-8 items-center justify-between gap-2">
                            <span>{column.label}</span>
                            <button
                              type="button"
                              className={`inline-flex h-6 w-6 items-center justify-center rounded-sm border text-muted-foreground hover:bg-background ${gridSort?.field === column.field ? "bg-background text-foreground" : ""}`}
                              onClick={() => toggleColumnSort(column.field)}
                              title={`Sort ${column.label}`}
                            >
                              {gridSort?.field === column.field && gridSort.direction === "desc" ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
                            </button>
                          </div>
                          {tableMode === "spreadsheet" && (
                            <div className="relative mt-1">
                              <Search className="pointer-events-none absolute left-1.5 top-1.5 h-3 w-3 text-muted-foreground" />
                              <input
                                className="h-6 w-full min-w-0 rounded-none border bg-background pl-6 pr-6 text-xs font-normal outline-none focus:ring-1 focus:ring-ring"
                                value={columnFilters[column.field] ?? ""}
                                onChange={(event) => setColumnFilterValue(column.field, event.target.value)}
                                onClick={(event) => event.stopPropagation()}
                                placeholder="Filter"
                                title="Use text, EMPTY, !EMPTY, >10, <=5, =value, or !=value"
                              />
                              {columnFilters[column.field] && (
                                <button
                                  type="button"
                                  className="absolute right-1 top-1 inline-flex h-4 w-4 items-center justify-center text-muted-foreground hover:text-foreground"
                                  onClick={() => setColumnFilterValue(column.field, "")}
                                  title={`Clear ${column.label} filter`}
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              )}
                            </div>
                          )}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {virtualPaddingTop > 0 && (
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={activeTableColumns.length + (tableMode === "spreadsheet" ? 1 : 2)} style={{ height: virtualPaddingTop }} className="border-0 p-0" />
                      </TableRow>
                    )}
                    {virtualDisplayIndices.map((index) => {
                      const item = items[index];
                      if (!item) return null;
                      const selected = selectedRows.has(index);
                      return (
                        <TableRow
                          key={`${index}-${item.line_no ?? ""}`}
                          style={{ height: activeVirtualRowHeight }}
                          className={`${tableMode === "spreadsheet" ? "hover:bg-muted/30" : statusClass(item.status)} ${selected ? "outline outline-1 outline-primary" : ""}`}
                          onClick={() => {
                            if (tableMode === "spreadsheet") return;
                            if (selectedRows.size === 1 && selected) return;
                            setSelectedRows(new Set([index]));
                          }}
                        >
                          <TableCell className={`sticky left-0 z-20 border-r p-0 text-center align-middle ${tableMode === "spreadsheet" ? "bg-background" : "bg-card"}`}>
                            <input
                              type="checkbox"
                              checked={selected}
                              onClick={(event) => event.stopPropagation()}
                              onChange={(event) => {
                                const next = new Set(selectedRows);
                                if (event.target.checked) next.add(index);
                                else next.delete(index);
                                setSelectedRows(next);
                              }}
                              aria-label={`Select row ${index + 1}`}
                            />
                          </TableCell>
                          {tableMode !== "spreadsheet" && (
                            <TableCell className="sticky left-10 z-20 border-r bg-card p-0 align-middle">
                              <div className="flex h-full items-center justify-center gap-1 px-1">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    recomputeRows([index]);
                                  }}
                                  title="Update row"
                                >
                                  <RefreshCw className="h-3.5 w-3.5" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    reprocessRows([index]);
                                  }}
                                  title="Smart Parse row"
                                >
                                  <RotateCcw className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            </TableCell>
                          )}
                          {activeTableColumns.map((column, colIndex) => {
                            const selectedCell = tableMode === "spreadsheet" && isGridCellSelected(index, colIndex);
                            const activeGridCell = tableMode === "spreadsheet" && isActiveGridCell(index, colIndex);
                            return (
                            <TableCell
                              key={column.label}
                              data-grid-row={index}
                              data-grid-col={colIndex}
                              tabIndex={tableMode === "spreadsheet" ? 0 : undefined}
                              className={`border-r p-0 align-top outline-none ${selectedCell ? "bg-primary/10 ring-1 ring-inset ring-primary/50" : ""} ${activeGridCell ? "ring-2 ring-inset ring-primary" : ""}`}
                              onMouseDown={(event) => {
                                if (tableMode !== "spreadsheet") return;
                                selectGridCell(index, colIndex, event.shiftKey);
                                setIsSelectingCells(true);
                              }}
                              onMouseEnter={() => {
                                if (tableMode !== "spreadsheet" || !isSelectingCells) return;
                                selectGridCell(index, colIndex, true);
                              }}
                              onFocus={() => {
                                if (tableMode !== "spreadsheet") return;
                                if (!isGridCellSelected(index, colIndex)) selectGridCell(index, colIndex, false);
                              }}
                            >
                              {renderGridCell(index, item, column)}
                            </TableCell>
                          );
                          })}
                        </TableRow>
                      );
                    })}
                    {virtualPaddingBottom > 0 && (
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={activeTableColumns.length + (tableMode === "spreadsheet" ? 1 : 2)} style={{ height: virtualPaddingBottom }} className="border-0 p-0" />
                      </TableRow>
                    )}
                    {!filteredItems.length && (
                      <TableRow>
                        <TableCell colSpan={activeTableColumns.length + (tableMode === "spreadsheet" ? 1 : 2)} className="py-8 text-center text-sm text-muted-foreground">No items match this filter.</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>

              {tableMode === "spreadsheet" && (
                <details className="border p-2">
                  <summary className="cursor-pointer text-sm font-medium">Advanced review panels</summary>
                  <div className="mt-3 space-y-3">
                    <TechnicalIssuesPanel
                      items={items}
                      onSelectRow={(index) => {
                        setSelectedRows(new Set([index]));
                        setStatusFilter("all");
                      }}
                      onBuildClarification={buildClarificationEmail}
                    />
                    <QuoteTimeline quote={quote} />
                  </div>
                </details>
              )}
                </div>

                <aside className={`h-fit border bg-background p-3 xl:sticky xl:top-32 xl:max-h-[calc(100vh-9rem)] xl:overflow-auto ${tableMode === "spreadsheet" ? "rounded-none" : "rounded-md"}`}>
                  <div className="flex items-start justify-between gap-3 border-b pb-3">
                    <div>
                      <div className="text-sm font-medium">Row editor</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {selectedItem && selectedRowIndex !== null
                          ? `Row ${selectedRowIndex + 1}`
                          : selectedIndices.length > 1
                            ? `${selectedIndices.length} rows selected`
                            : "Select one row"}
                      </div>
                    </div>
                    {selectedItem && selectedRowIndex !== null && <Badge variant="outline">{getString(selectedItem.status) || "draft"}</Badge>}
                  </div>

                  {selectedItem && selectedRowIndex !== null ? (
                    <div className="mt-3 space-y-3">
                      <Field
                        label="Customer description"
                        value={getString(selectedItem.raw_description)}
                        onChange={(value) => updateItem(selectedRowIndex, "raw_description", value)}
                        textarea
                      />
                      <Field
                        label="GGPL description"
                        value={getString(selectedItem.ggpl_description)}
                        onChange={(value) => updateItem(selectedRowIndex, "ggpl_description", value)}
                        textarea
                      />
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                        <Field label="Quantity" value={getString(selectedItem.quantity)} onChange={(value) => updateItem(selectedRowIndex, "quantity", value)} type="number" />
                        <Field label="UoM" value={getString(selectedItem.uom)} onChange={(value) => updateItem(selectedRowIndex, "uom", value)} />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Missing / review notes</Label>
                        <textarea
                          className="min-h-24 w-full resize-none rounded-md border border-input bg-muted/40 px-3 py-2 text-sm text-muted-foreground outline-none"
                          value={notesFor(selectedItem) || "No missing fields detected for this row."}
                          readOnly
                        />
                      </div>
                      <Field
                        label="Clarification note"
                        value={getString(selectedItem.clarification_note)}
                        onChange={(value) => updateItem(selectedRowIndex, "clarification_note", value)}
                        textarea
                      />
                      <div className="space-y-1.5">
                        <Label>Review badges</Label>
                        <div className="flex min-h-20 flex-wrap content-start gap-1.5 rounded-md border bg-muted/20 p-2">
                          {selectedItemBadges.map((badge) => <Badge key={badge} variant="outline">{badge}</Badge>)}
                          {!selectedItemBadges.length && <div className="text-sm text-muted-foreground">No row badges.</div>}
                        </div>
                      </div>
                      <details className="border p-3">
                        <summary className="cursor-pointer text-sm font-medium">All item fields</summary>
                        <div className="mt-3 space-y-3">
                          {ITEM_FIELDS.map((field) => (
                            <Field
                              key={field}
                              label={field}
                              value={getString(selectedItem[field])}
                              onChange={(value) => updateItem(selectedRowIndex, field, value)}
                              textarea={field === "raw_description" || field === "ggpl_description" || field === "flags"}
                            />
                          ))}
                        </div>
                      </details>
                    </div>
                  ) : (
                    <div className="mt-3 rounded-md border border-dashed bg-muted/20 p-3 text-sm text-muted-foreground">
                      {selectedIndices.length > 1
                        ? "Use bulk edit for multi-row changes, or select one row to edit its details here."
                        : "Click a row or select a cell to edit its details here."}
                    </div>
                  )}
                </aside>
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <div className="rounded-md border p-3">
                  <div className="text-sm font-medium">Extraction summary</div>
                  <div className="mt-2 space-y-1 text-sm text-muted-foreground">
                    {shownSummary.map(([key, count], index) => <div key={key}><span className="font-medium">{index + 1}.</span> {key} <span className="text-xs">({count})</span></div>)}
                    {hiddenSummaryCount > 0 && <div>+ {hiddenSummaryCount} more summary group(s)</div>}
                    {!items.length && <div>No items yet.</div>}
                  </div>
                </div>
                <div className="rounded-md border p-3 lg:col-span-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">Missing-field clarification</div>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={buildClarificationEmail}
                    >
                      Build RFI email
                    </Button>
                  </div>
                  <textarea
                    className="mt-2 min-h-20 w-full rounded-md border bg-background px-3 py-2 text-sm"
                    value={getString(quote.stage_meta?.clarification_note)}
                    onChange={(event) => {
                      const stageMeta = { ...(quote.stage_meta ?? {}), clarification_note: event.target.value };
                      setQuote((current) => (current ? { ...current, stage_meta: stageMeta } : current));
                      setHasUnsavedLocalEdits(true);
                    }}
                    placeholder="Quote-level clarification context"
                  />
                  <Button
                    className="mt-2"
                    variant="secondary"
                    size="sm"
                    onClick={() => savePatch({ stage_meta: appendActivity(quote.stage_meta ?? {}, {
                      kind: "clarification",
                      title: "Clarification note saved",
                      detail: getString(quote.stage_meta?.clarification_note) || "Quote clarification note updated",
                      user: currentUser.name || currentUser.id,
                    }) } as Partial<Quote>, "Clarification note saved")}
                  >
                    <Save className="h-4 w-4" />
                    Save note
                  </Button>
                  <textarea className="mt-2 min-h-32 w-full rounded-md border bg-background px-3 py-2 text-sm" value={rfiText} onChange={(event) => setRfiText(event.target.value)} />
                  {rfiText && (
                    <a
                      className="mt-2 inline-flex h-8 items-center rounded-md border px-3 text-sm"
                      download="rfi-enquiry.txt"
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
                  Generate a reviewable stock plan from the selected enquiry. Sheet settings are editable in Planning inputs.
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {materialPlan && (
                  <Button variant="secondary" onClick={() => saveMaterialPlan()}>
                    <Save className="h-4 w-4" />
                    Save plan
                  </Button>
                )}
                {materialPlan && (
                  <Button variant="secondary" onClick={clearMaterialPlan}>
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
                    {quote?.customer || quote?.quote_no || "Untitled enquiry"} - REG : {quote?.quote_no || quote?.id || "N/A"} / {quote?.project_ref || "N/A"} / {quote?.custom_label || "GASKETS"}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Sheet rows use {materialPlan.config.sheet_width_mm} x {materialPlan.config.sheet_length_mm} mm stock with {Math.round(materialPlan.config.nesting_efficiency * 100)}% nesting efficiency.
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
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
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">Shortage rows</div>
                    <div className="text-lg font-semibold">{materialPlan.rows.filter((row) => row.shortage_qty > 0).length}</div>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">Suggested purchase</div>
                    <div className="text-lg font-semibold">{materialPlan.rows.reduce((sum, row) => sum + row.suggested_purchase_qty, 0).toFixed(2)}</div>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">Material cost impact</div>
                    <div className="text-lg font-semibold">{materialPlan.rows.reduce((sum, row) => sum + row.estimated_material_cost, 0).toFixed(2)}</div>
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

                {materialPlan.rows.some((row) => row.shortage_qty > 0) && (
                  <div className="rounded-md border border-red-200 bg-red-50/60 p-3 text-sm text-red-950 dark:border-red-900 dark:bg-red-950/25 dark:text-red-100">
                    <div className="font-medium">Shortage warning</div>
                    <div className="mt-1">
                      {materialPlan.rows.filter((row) => row.shortage_qty > 0).length} stock row(s) need purchase or reservation review before production release.
                    </div>
                  </div>
                )}

                {(materialPlan.grouped_summary ?? []).length > 0 && (
                  <details className="rounded-md border p-3">
                    <summary className="cursor-pointer text-sm font-medium">Grouped purchase summary</summary>
                    <div className="mt-3 overflow-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Material / thickness / vendor</TableHead>
                            <TableHead className="w-24">Rows</TableHead>
                            <TableHead className="w-32">Shortage</TableHead>
                            <TableHead className="w-40">Suggested purchase</TableHead>
                            <TableHead className="w-36">Est. cost</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {(materialPlan.grouped_summary ?? []).map((row) => (
                            <TableRow key={row.group}>
                              <TableCell className="font-medium">{row.group}</TableCell>
                              <TableCell>{row.rows}</TableCell>
                              <TableCell>{row.shortage_qty.toFixed(2)}</TableCell>
                              <TableCell>{row.suggested_purchase_qty.toFixed(2)}</TableCell>
                              <TableCell>{row.estimated_material_cost.toFixed(2)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </details>
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
                        <TableHead className="w-32">Available</TableHead>
                        <TableHead className="w-32">Reserved</TableHead>
                        <TableHead className="w-32">Shortage</TableHead>
                        <TableHead className="w-40">Suggested purchase</TableHead>
                        <TableHead className="w-40">Vendor</TableHead>
                        <TableHead className="w-32">Lead days</TableHead>
                        <TableHead className="w-40">Material cost</TableHead>
                        <TableHead className="w-36">Priority</TableHead>
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
                          <TableCell><Input className="w-28" type="number" value={getString(row.available_qty)} onChange={(event) => updatePlanRow(index, { available_qty: Number(event.target.value) })} /></TableCell>
                          <TableCell><Input className="w-28" type="number" value={getString(row.reserved_qty)} onChange={(event) => updatePlanRow(index, { reserved_qty: Number(event.target.value) })} /></TableCell>
                          <TableCell className={row.shortage_qty > 0 ? "font-medium text-red-600" : "text-sm"}>{row.shortage_qty.toFixed(2)}</TableCell>
                          <TableCell><Input className="w-32" type="number" value={getString(row.suggested_purchase_qty)} onChange={(event) => updatePlanRow(index, { suggested_purchase_qty: Number(event.target.value) })} /></TableCell>
                          <TableCell><Input className="w-36" value={row.preferred_vendor} onChange={(event) => updatePlanRow(index, { preferred_vendor: event.target.value })} /></TableCell>
                          <TableCell><Input className="w-24" type="number" value={getString(row.lead_time_days)} onChange={(event) => updatePlanRow(index, { lead_time_days: Number(event.target.value) })} /></TableCell>
                          <TableCell><Input className="w-32" type="number" value={getString(row.estimated_material_cost)} onChange={(event) => updatePlanRow(index, { estimated_material_cost: Number(event.target.value) })} /></TableCell>
                          <TableCell>
                            <Select value={row.production_priority} onValueChange={(value) => updatePlanRow(index, { production_priority: value as MaterialPlan["rows"][number]["production_priority"] })}>
                              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="low">Low</SelectItem>
                                <SelectItem value="normal">Normal</SelectItem>
                                <SelectItem value="high">High</SelectItem>
                                <SelectItem value="urgent">Urgent</SelectItem>
                              </SelectContent>
                            </Select>
                          </TableCell>
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
                <div className="text-sm text-muted-foreground">{quote.customer || quote.quote_no || "Untitled enquiry"}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={closeQuotationScreen}>
                  <RotateCcw className="h-4 w-4" />
                  Back to enquiry
                </Button>
                <Button variant="secondary" onClick={() => savePatch({ items, quote_data: qd, quote_no: getString(qd.quote_no) } as Partial<Quote>, "Quotation saved")}>
                  <Save className="h-4 w-4" />
                  Save
                </Button>
                <Button variant="secondary" onClick={() => exportCurrent("pdf", "preview")} disabled={!canExportFinal}>
                  {exporting === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                  Preview PDF
                </Button>
                <Button variant="secondary" onClick={markSent} disabled={approval.status !== "approved" || quote.stage === "sent"}>
                  <Send className="h-4 w-4" />
                  Mark sent
                </Button>
                <Button onClick={() => exportCurrent("pdf")} disabled={!canExportFinal}>
                  {exporting === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  Download PDF
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
              <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
                <div className="rounded-md border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <ShieldCheck className="h-4 w-4" />
                        Approval workflow
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        Current user: {currentUser.name} ({roleLabels[currentUser.role]})
                      </div>
                    </div>
                    <Badge variant={approvalBadgeVariant(approval.status)}>{approval.status}</Badge>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
                    <div>RFQ score: <span className="font-medium text-foreground">{qualityReport.score}%</span></div>
                    <div>Risks: <span className="font-medium text-foreground">{qualityReport.risks.length}</span></div>
                    <div>Quote value: <span className="font-medium text-foreground">{grandTotal.toFixed(2)} {currency}</span></div>
                  </div>
                  {qualityReport.risks.length > 0 && (
                    <div className="mt-3 rounded-md border bg-muted/30 p-2">
                      <div className="text-xs font-medium">Technical risk details</div>
                      <div className="mt-2 space-y-1.5">
                        {qualityReport.risks.slice(0, 6).map((risk) => (
                          <div key={`${risk.title}-${risk.detail}`} className="text-xs">
                            <span className={risk.severity === "high" ? "font-medium text-red-600" : "font-medium text-amber-700"}>{risk.title}</span>
                            <span className="text-muted-foreground"> - {risk.detail}</span>
                            {risk.rows?.length ? <span className="text-muted-foreground"> Rows {risk.rows.slice(0, 8).join(", ")}</span> : null}
                          </div>
                        ))}
                        {qualityReport.risks.length > 6 && <div className="text-xs text-muted-foreground">+ {qualityReport.risks.length - 6} more risk checks</div>}
                      </div>
                    </div>
                  )}
                  {pricingSummary.approvalRequired && (
                    <div className="mt-3 rounded-md border border-amber-200 bg-amber-50/70 p-2 text-xs text-amber-950 dark:border-amber-900 dark:bg-amber-950/25 dark:text-amber-100">
                      <div className="font-medium">Approval required</div>
                      <ul className="mt-1 space-y-1">
                        {pricingSummary.approvalReasons.map((reason) => <li key={reason}>- {reason}</li>)}
                      </ul>
                    </div>
                  )}
                  {approval.requested_by && (
                    <div className="mt-2 text-xs text-muted-foreground">
                      Requested by {approval.requested_by}{approval.requested_at ? ` on ${new Date(approval.requested_at).toLocaleString()}` : ""}
                    </div>
                  )}
                  {approval.decided_by && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {approval.status === "approved" ? "Approved" : "Rejected"} by {approval.decided_by}{approval.decided_at ? ` on ${new Date(approval.decided_at).toLocaleString()}` : ""}
                    </div>
                  )}
                  {approval.comments && <div className="mt-2 rounded-md bg-muted/40 p-2 text-xs">{approval.comments}</div>}
                  {approval.required_changes && <div className="mt-2 rounded-md bg-muted/40 p-2 text-xs">Required changes: {approval.required_changes}</div>}
                </div>

                <div className="rounded-md border p-3">
                  <Label>Approval comments</Label>
                  <textarea
                    className="mt-1 min-h-20 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                    value={approvalComment}
                    onChange={(event) => setApprovalComment(event.target.value)}
                    placeholder="Reason, exception approval, price override, or rejection comments"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={requestApproval} disabled={approval.status === "pending" || approval.status === "approved"}>
                      <ShieldCheck className="h-4 w-4" />
                      Request approval
                    </Button>
                    <Button onClick={() => decideApproval("approved")} disabled={!canApprove || approval.status !== "pending"}>
                      <CheckCircle2 className="h-4 w-4" />
                      Approve
                    </Button>
                    <Button variant="secondary" onClick={() => decideApproval("rejected")} disabled={!canApprove || approval.status !== "pending"}>
                      <Ban className="h-4 w-4" />
                      Reject
                    </Button>
                  </div>
                  {!canApprove && <div className="mt-2 text-xs text-muted-foreground">Only admin or approver users can approve or reject.</div>}
                  {!canExportFinal && <div className="mt-1 text-xs text-muted-foreground">Quotation PDF download is locked until approval is completed.</div>}
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-4">
                <Field label="Quote no" value={getString(qd.quote_no)} onChange={(value) => updateQd("quote_no", value)} />
                <Field label="Quote date" value={getString(qd.quote_date)} onChange={(value) => updateQd("quote_date", value)} />
                <Field label="Revision no" value={getString(qd.rev_no)} onChange={(value) => updateQd("rev_no", value)} />
                <Field label="Revision date" value={getString(qd.rev_date)} onChange={(value) => updateQd("rev_date", value)} />
              </div>
              <div className="grid gap-3 rounded-md border bg-muted/20 p-3 md:grid-cols-2">
                <label className="flex items-start gap-3 text-sm">
                  <input
                    className="mt-1"
                    type="checkbox"
                    checked={Boolean(qd.include_customer_sl_no)}
                    onChange={(event) => updateQd("include_customer_sl_no", event.target.checked)}
                  />
                  <span>
                    <span className="block font-medium">Use customer SL No. in quotation PDF</span>
                    <span className="block text-xs text-muted-foreground">When enabled, customer SL No. replaces the default serial number.</span>
                  </span>
                </label>
                <label className="flex items-start gap-3 text-sm">
                  <input
                    className="mt-1"
                    type="checkbox"
                    checked={Boolean(qd.include_customer_item_code)}
                    onChange={(event) => updateQd("include_customer_item_code", event.target.checked)}
                  />
                  <span>
                    <span className="block font-medium">Add customer item code to quotation PDF</span>
                    <span className="block text-xs text-muted-foreground">Keep disabled when the customer code is only for internal matching.</span>
                  </span>
                </label>
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
                <Field label="Approval discount %" value={getString(qd.discount_approval_pct)} onChange={(value) => updateQd("discount_approval_pct", Number(value))} type="number" />
                <Field label="Minimum margin %" value={getString(qd.minimum_margin_pct)} onChange={(value) => updateQd("minimum_margin_pct", Number(value))} type="number" />
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

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm">
                <div className="text-muted-foreground">
                  Showing {items.length ? finalPageStartIndex + 1 : 0}-{finalPageEndIndex} of {items.length} quotation row(s).
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setFinalPage((page) => Math.max(0, page - 1))}
                    disabled={safeFinalPage <= 0}
                  >
                    Previous
                  </Button>
                  <span className="text-xs text-muted-foreground">Page {safeFinalPage + 1} of {finalPageCount}</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setFinalPage((page) => Math.min(finalPageCount - 1, page + 1))}
                    disabled={safeFinalPage >= finalPageCount - 1}
                  >
                    Next
                  </Button>
                </div>
              </div>

              <div className="max-h-[620px] overflow-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>#</TableHead>
                      <TableHead>Cust Sl.No</TableHead>
                      <TableHead>Customer item code</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Qty</TableHead>
                      <TableHead>UOM</TableHead>
                      <TableHead>Cost/unit</TableHead>
                      <TableHead>Target margin %</TableHead>
                      <TableHead>Base INR unit price</TableHead>
                      <TableHead>{currency} unit price</TableHead>
                      <TableHead>Margin %</TableHead>
                      <TableHead>Discount impact</TableHead>
                      <TableHead>Total {currency}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {finalPageItems.map((item, pageIndex) => {
                      const index = finalPageStartIndex + pageIndex;
                      const price = unitPrices[index] ?? 0;
                      const converted = currency === "INR" ? price : price / (fxRate || 1);
                      const total = item.status === "regret" ? 0 : converted * toNumber(item.quantity);
                      const pricingLine = pricingSummary.lines[index];
                      return (
                        <TableRow key={index}>
                          <TableCell>{index + 1}</TableCell>
                          <TableCell><Input className="w-24" value={getString(item.customer_sl_no)} onChange={(event) => updateItem(index, "customer_sl_no", event.target.value)} /></TableCell>
                          <TableCell><Input className="w-36" value={getString(item.customer_item_code)} onChange={(event) => updateItem(index, "customer_item_code", event.target.value)} /></TableCell>
                          <TableCell className="min-w-96 text-xs">
                            {item.status === "regret" ? (
                              "REGRET - CANNOT PRODUCE"
                            ) : (
                              <div className="space-y-1">
                                <div>{getString(item.raw_description || item.ggpl_description)}</div>
                                {item.ggpl_description && item.ggpl_description !== item.raw_description && (
                                  <div className="text-muted-foreground">GGPL: {getString(item.ggpl_description)}</div>
                                )}
                              </div>
                            )}
                          </TableCell>
                          <TableCell><Input className="w-24" type="number" value={getString(item.quantity)} onChange={(event) => updateItem(index, "quantity", event.target.value)} /></TableCell>
                          <TableCell>{getString(item.uom || "NOS")}</TableCell>
                          <TableCell>
                            <Input
                              className="w-28"
                              type="number"
                              value={getString(costPrices[index] ?? 0)}
                              onChange={(event) => {
                                const next = [...costPrices];
                                next[index] = Number(event.target.value);
                                updateQd("cost_prices", next);
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              className="w-28"
                              type="number"
                              value={getString(targetMargins[index] ?? minimumMarginPct)}
                              onChange={(event) => {
                                const next = [...targetMargins];
                                next[index] = Number(event.target.value);
                                updateQd("target_margins_pct", next);
                              }}
                            />
                          </TableCell>
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
                          <TableCell className={pricingLine?.marginPct !== null && pricingLine?.marginPct !== undefined && pricingLine.marginPct < minimumMarginPct ? "text-red-600" : ""}>
                            {pricingLine?.marginPct === null || pricingLine?.marginPct === undefined ? "-" : pricingLine.marginPct.toFixed(1)}
                          </TableCell>
                          <TableCell>{(pricingLine?.discountImpact ?? 0).toFixed(2)}</TableCell>
                          <TableCell>{total.toFixed(2)}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
              <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-7">
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Subtotal</div><div className="text-lg font-semibold">{subtotal.toFixed(2)}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Discount</div><div className="text-lg font-semibold">{discount.toFixed(2)}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">GST</div><div className="text-lg font-semibold">{gst.toFixed(2)}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Grand total</div><div className="text-lg font-semibold">{grandTotal.toFixed(2)}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Cost total</div><div className="text-lg font-semibold">{pricingSummary.costTotal.toFixed(2)}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Gross margin</div><div className="text-lg font-semibold">{pricingSummary.grossMarginPct === null ? "-" : `${pricingSummary.grossMarginPct.toFixed(1)}%`}</div></div>
                <div className="rounded-md border p-3"><div className="text-xs text-muted-foreground">Lowest line margin</div><div className="text-lg font-semibold">{pricingSummary.lowestLineMarginPct === null ? "-" : `${pricingSummary.lowestLineMarginPct.toFixed(1)}%`}</div></div>
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
