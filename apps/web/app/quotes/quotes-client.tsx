"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Circle,
  Copy,
  Download,
  FileUp,
  FileSpreadsheet,
  FileText,
  Inbox,
  ListFilter,
  Loader2,
  Mail,
  Layers3,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  PanelRight,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Send,
  ShieldCheck,
  ShoppingCart,
  SlidersHorizontal,
  Trash2,
  Undo2,
  Upload,
  Users,
  WandSparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";

import {
  API_BASE,
  BusinessMasterData,
  GasketItem,
  ITEM_FIELDS,
  OutlookLinkedMessage,
  Quote,
  advanceQuoteStage,
  bulkRecompute,
  createExtraction,
  createQuote,
  deleteQuote,
  exportQuote,
  getAccessSettingsRemote,
  getBusinessMasterData,
  getCurrentAppUserRemote,
  getJobStatus,
  getQuote,
  listAppUsers,
  listQuotes,
  listOutlookThreadMessages,
  patchQuote,
  reprocessText,
  resolveOutlookMessage,
  rfiDraft,
  toNumber,
} from "@/lib/api";
import { addBackgroundJob, BACKGROUND_JOBS_EVENT, listBackgroundJobs } from "@/lib/background-jobs";
import { ACCESS_SETTINGS_CHANGED_EVENT, canRole, getAccessSettings, normalizeAccessSettings, saveAccessSettings } from "@/lib/auth/access-control";
import { getAppUsers, getCurrentAppUser, resolveAppUserName, roleLabels, setCurrentAppUser, USERS_CHANGED_EVENT } from "@/lib/auth/users";
import {
  buildMaterialBreakdown,
  DEFAULT_MATERIAL_PLANNING_INPUTS,
  DEFAULT_NESTING_EFFICIENCY,
  DEFAULT_SHEET_LENGTH_MM,
  DEFAULT_SHEET_WIDTH_MM,
  MaterialBreakdownRow,
  MaterialInputRow,
  MaterialPlan,
} from "@/lib/material-planning";
import { getString, notesFor, validateItemField } from "@/components/quotes/item-validation";
import { buildQuotePricingSummary } from "@/components/quotes/pricing-utils";
import { evaluateQuoteQuality } from "@/components/quotes/quality-utils";
import { itemMatchesSmartFilter, quoteDueState, quoteHasClarification, quoteIsHighRisk, quoteIsHighValue } from "@/components/quotes/queue-utils";
import { QuoteSummaryRow } from "@/components/quotes/quote-summary-row";
import { appendActivity } from "@/components/quotes/activity-utils";
import { ClipboardTableDetection, detectClipboardTable, rowsToTsv, structuredRowsToItemFields } from "@/components/quotes/clipboard-table";
import { QuoteTimeline } from "@/components/quotes/quote-timeline";
import { DRAFT_STAGES, ENQUIRY_STAGES, EnquiryStageId, FINAL_STAGES, PO_STAGES, QuoteSection, enquiryStageFromQuote, enquiryStageLabel, revisionLabel, stageLabel } from "@/components/quotes/stage-utils";
import { issueBadgesForItem, TechnicalIssuesPanel } from "@/components/quotes/technical-issues-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
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
const TYPE_OPTIONS = ["SOFT_CUT", "SHEET_GASKET", "CORRUGATED", "PLUG_GASKET", "SPIRAL_WOUND", "RTJ", "KAMM", "DJI", "ISK", "ISK_RTJ"];
const FACE_OPTIONS = ["RF", "FF", ""];
const UOM_OPTIONS = ["NOS", "M"];
const GROOVE_OPTIONS = ["OCT", "OVAL", ""];
const ISK_FIRE_SAFETY_OPTIONS = ["NON FIRE SAFE", "FIRE SAFE"];

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

const DEFAULT_TECHNICAL_NOTES =
  "1. Certifications: MTC to EN10204-3.1 for metallic parts and EN10204-2.1 for non-metallic.\n" +
  "2. Testing Charges for gasket will be extra at actuals for tests other than compression & sealability test and chemical analysis.";

const quoteDefaults: Record<string, unknown> = {
  quote_no: "",
  quote_date: new Date().toLocaleDateString("en-GB"),
  rev_no: "0",
  rev_date: "",
  quotation_stage: "draft_preparation",
  quotation_stage_history: [],
  include_customer_sl_no: false,
  include_customer_item_code: false,
  buyer_name_address: "",
  buyer_name: "",
  buyer_address_line1: "",
  buyer_address_line2: "",
  buyer_city: "",
  buyer_state: "",
  buyer_pin_code: "",
  buyer_country: "",
  customer_enq_no: "",
  attention: "",
  designation: "",
  contact_no: "",
  mobile_no: "",
  telephone_no: "",
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
  discount_approval_pct: 0,
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
  technical_deviation_remarks: "",
  commercial_tnc: "",
  technical_notes: DEFAULT_TECHNICAL_NOTES,
};

const BUYER_ADDRESS_FIELDS = [
  "buyer_name",
  "buyer_address_line1",
  "buyer_address_line2",
  "buyer_city",
  "buyer_state",
  "buyer_pin_code",
  "buyer_country",
];

function buyerNameAddressLines(data: Record<string, unknown>): string[] {
  const hasStructuredBuyer = BUYER_ADDRESS_FIELDS.some((key) => getString(data[key]).trim());
  if (!hasStructuredBuyer) {
    return getString(data.buyer_name_address)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  }
  const cityStatePin = [
    getString(data.buyer_city),
    getString(data.buyer_state),
    getString(data.buyer_pin_code),
  ].filter(Boolean).join(", ");
  return [
    getString(data.buyer_name),
    getString(data.buyer_address_line1),
    getString(data.buyer_address_line2),
    cityStatePin,
    getString(data.buyer_country),
  ].filter(Boolean);
}

function buyerNameAddressText(data: Record<string, unknown>): string {
  return buyerNameAddressLines(data).join("\n");
}

function quoteDataWithDefaults(data?: Record<string, unknown> | null): Record<string, unknown> {
  const next = { ...quoteDefaults, ...(data ?? {}) };
  if (typeof next.technical_notes !== "string" || !next.technical_notes.trim()) {
    next.technical_notes = DEFAULT_TECHNICAL_NOTES;
  }
  if (!BUYER_ADDRESS_FIELDS.some((key) => getString(next[key]).trim())) {
    const [name = "", addressLine1 = "", addressLine2 = "", cityStatePin = "", country = ""] = buyerNameAddressLines(next);
    next.buyer_name = name;
    next.buyer_address_line1 = addressLine1;
    next.buyer_address_line2 = addressLine2;
    next.buyer_city = cityStatePin;
    next.buyer_country = country;
  }
  next.buyer_name_address = buyerNameAddressText(next);
  return next;
}

const SALES_DETAIL_QUOTE_DATA_FIELDS = new Set([
  "buyer_name_address",
  ...BUYER_ADDRESS_FIELDS,
  "customer_enq_no",
  "attention",
  "designation",
  "contact_no",
  "mobile_no",
  "telephone_no",
  "email",
  "sales_notes",
  "technical_notes",
]);

function pickSalesDetailQuoteData(data: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(data).filter(([key]) => SALES_DETAIL_QUOTE_DATA_FIELDS.has(key)),
  );
}

type OutlookThreadLink = {
  mailbox_user: string;
  message_id: string;
  conversation_id: string;
  internet_message_id: string;
  web_link: string;
  subject: string;
  from_name: string;
  from_email: string;
  received_at: string;
  linked_at: string;
  linked_by: string;
};

const blankOutlookThread: OutlookThreadLink = {
  mailbox_user: "",
  message_id: "",
  conversation_id: "",
  internet_message_id: "",
  web_link: "",
  subject: "",
  from_name: "",
  from_email: "",
  received_at: "",
  linked_at: "",
  linked_by: "",
};

function outlookThreadFromMeta(meta: Record<string, unknown> | undefined): OutlookThreadLink | null {
  const raw = meta?.outlook_thread;
  if (!raw || typeof raw !== "object") return null;
  const data = raw as Record<string, unknown>;
  const link = {
    mailbox_user: getString(data.mailbox_user),
    message_id: getString(data.message_id),
    conversation_id: getString(data.conversation_id),
    internet_message_id: getString(data.internet_message_id),
    web_link: getString(data.web_link),
    subject: getString(data.subject),
    from_name: getString(data.from_name),
    from_email: getString(data.from_email),
    received_at: getString(data.received_at),
    linked_at: getString(data.linked_at),
    linked_by: getString(data.linked_by),
  };
  return link.conversation_id || link.message_id || link.web_link ? link : null;
}

function outlookThreadFromMessage(message: OutlookLinkedMessage): OutlookThreadLink {
  return {
    mailbox_user: message.mailbox_user,
    message_id: message.message_id,
    conversation_id: message.conversation_id,
    internet_message_id: message.internet_message_id,
    web_link: message.web_link,
    subject: message.subject,
    from_name: message.from_name,
    from_email: message.from_email,
    received_at: message.received_at || message.sent_at,
    linked_at: message.linked_at,
    linked_by: message.linked_by,
  };
}

function messageIdFromOutlookInput(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const url = new URL(trimmed);
    for (const key of ["itemid", "ItemID", "id", "messageId", "messageid"]) {
      const found = url.searchParams.get(key);
      if (found) return found;
    }
  } catch {
    // Plain Graph message IDs are accepted directly.
  }
  return /^https?:\/\//i.test(trimmed) ? "" : trimmed;
}

function webLinkFromOutlookInput(value: string) {
  const trimmed = value.trim();
  return /^https?:\/\//i.test(trimmed) ? trimmed : "";
}

function nextQuotationNumber(rows: Quote[], marketType: string) {
  const prefix = QUOTATION_NUMBER_PREFIX[marketType];
  if (!prefix) return "";
  const pattern = new RegExp(`^${prefix}(\\d{3,})$`, "i");
  let highest = -1;
  rows.forEach((row) => {
    [row.quote_no, getString(row.quote_data?.quote_no)].forEach((candidate) => {
      const match = pattern.exec(candidate.trim());
      if (match) highest = Math.max(highest, Number(match[1]));
    });
  });
  return `${prefix}${String(highest + 1).padStart(3, "0")}`;
}

type QuotationStageId =
  | "draft_preparation"
  | "technical_review"
  | "costing"
  | "commercial_review"
  | "approval"
  | "ready_to_send"
  | "sent_to_customer"
  | "negotiation"
  | "revision"
  | "po_received"
  | "lost";

const QUOTATION_STAGES: Array<{
  id: QuotationStageId;
  label: string;
  owner: string;
  description: string;
}> = [
  { id: "draft_preparation", label: "Draft preparation", owner: "Sales", description: "Customer details, enquiry references, line descriptions, and quote header are prepared." },
  { id: "technical_review", label: "Technical review", owner: "Engineering", description: "Specs, materials, risk items, drawings, deviations, and regret rows are checked." },
  { id: "costing", label: "Costing", owner: "Planning / costing", description: "Material, bought-out, machining, packing, freight, and overhead cost inputs are entered." },
  { id: "commercial_review", label: "Commercial review", owner: "Sales / commercial", description: "Margins, discount, currency, taxes, delivery, validity, and payment terms are reviewed." },
  { id: "approval", label: "Internal approval", owner: "Approver", description: "Approval is requested when margins, discount, risk, or value require sign-off." },
  { id: "ready_to_send", label: "Ready to send", owner: "Sales", description: "Quotation PDF is approved and ready for customer release." },
  { id: "sent_to_customer", label: "Sent to customer", owner: "Sales", description: "Approved quotation has been shared with the customer." },
  { id: "negotiation", label: "Negotiation", owner: "Sales", description: "Customer feedback, commercial negotiation, alternates, and clarifications are being handled." },
  { id: "revision", label: "Revision", owner: "Sales / engineering", description: "A revised quotation is being prepared after customer or internal changes." },
  { id: "po_received", label: "PO received", owner: "Sales", description: "Customer PO is received and the quotation is ready for handover." },
  { id: "lost", label: "Lost / closed", owner: "Sales", description: "Opportunity is closed without order, with loss reason captured in notes." },
];

const QUOTATION_STAGE_INDEX = new Map(QUOTATION_STAGES.map((stage, index) => [stage.id, index]));

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

type ExtractionSummaryRow = {
  item: string;
  count: number;
  note1: string;
  note2: string;
};

type StoredExtractionSummary = {
  source_quote_version: number;
  generated_at: string;
  item_signature: string;
  rows: ExtractionSummaryRow[];
  unmatched_item_rows: number[];
};

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
  { label: "ISK Fire Safe", field: "isk_fire_safety", kind: "select", options: ISK_FIRE_SAFETY_OPTIONS, width: "w-36" },
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
  "status",
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
  "isk_fire_safety",
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
  "regret",
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
  isk: ["line_no", "status", "ggpl_description", "quantity", "isk_fire_safety", "isk_gasket_material", "isk_core_material", "isk_sleeve_material", "isk_washer_material", "isk_primary_seal", "isk_secondary_seal", "confidence"],
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

function spreadsheetColumnName(index: number) {
  let value = index + 1;
  let name = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
}

const BLANK_SELECT_VALUE = "__blank__";
const CUSTOM_SALES_REP_VALUE = "__custom_sales_rep__";
const QUOTATION_NUMBER_PREFIX: Record<string, string> = {
  export: "EXP",
  domestic: "DOM",
};
const LARGE_DRAFT_THRESHOLD = 250;
const DRAFT_PAGE_SIZE = 500;
const FINAL_PAGE_SIZE = 50;
const VIRTUAL_ROW_HEIGHT = 58;
const VIRTUAL_VIEWPORT_HEIGHT = 620;
const VIRTUAL_OVERSCAN = 6;
const AUTO_UPDATE_DELAY_MS = 700;
const AUTO_UPDATE_FIELDS = new Set([
  "gasket_type",
  "size",
  "size_norm",
  "od_mm",
  "id_mm",
  "rating",
  "moc",
  "face_type",
  "thickness_mm",
  "standard",
  "series",
  "special",
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
  "isk_fire_safety",
  "kamm_core_material",
  "kamm_surface_material",
  "kamm_covering_layer",
  "kamm_rib",
  "kamm_core_thk",
  "dji_filler",
  "dji_rib",
  "dji_face_type",
]);
const GRID_INPUT_CLASS =
  "h-7 w-full min-w-0 rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none focus-visible:ring-1 focus-visible:ring-ring";
const GRID_TEXTAREA_CLASS =
  "h-14 w-full min-w-0 resize-none rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none outline-none focus:ring-1 focus:ring-ring";
const GRID_READONLY_CLASS = "bg-muted/30 text-muted-foreground";
const SHEET_TABLE_CLASS = "w-max min-w-full border-collapse text-xs [&_td]:border-r [&_td]:border-b [&_th]:border-r [&_th]:border-b";
const SHEET_HEADER_CLASS = "sticky top-0 z-20 bg-[#f3f3f3] dark:bg-muted";
const SHEET_HEAD_CLASS = "h-8 whitespace-nowrap bg-[#f3f3f3] px-2 py-1 text-xs font-semibold text-foreground dark:bg-muted";
const SHEET_ROW_HEADER_CLASS = "sticky left-0 z-10 h-8 w-10 bg-[#f3f3f3] px-2 py-1 text-center text-xs text-muted-foreground dark:bg-muted";
const SHEET_CELL_CLASS = "h-8 whitespace-nowrap px-2 py-1 text-xs";
const SHEET_INPUT_CLASS = "h-8 rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none focus-visible:ring-1 focus-visible:ring-emerald-600";
const SHEET_SELECT_CLASS = "h-8 rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none focus:ring-1 focus:ring-emerald-600";
const SHEET_TEXTAREA_CLASS = "min-h-16 w-full min-w-80 resize-y whitespace-normal rounded-none border-0 bg-transparent px-2 py-1 text-xs shadow-none outline-none focus:ring-1 focus:ring-emerald-600";
const STATUS_OPTIONS = ["ready", "check", "missing", "regret"] as const;
const STATUS_LABELS: Record<(typeof STATUS_OPTIONS)[number], string> = {
  ready: "Ready",
  check: "Check",
  missing: "Missing",
  regret: "Regret",
};
const MATERIAL_PHASE2_UOMS = ["SHEETS", "KG", "COIL", "RINGS", "NOS"] as const;
const DEFAULT_TABLE_MODE = "spreadsheet" as const;
const SAVED_QUOTE_FILTERS_PREFIX = "goodrich:quote-workspace:";

type MaterialPhase2Row = MaterialPlan["rows"][number];

function materialPhase2RequiredQty(row: MaterialPhase2Row) {
  return row.reqd_qty_sheets ?? row.reqd_qty_kg ?? 0;
}

function summarizeMaterialPhase2Rows(rows: MaterialPhase2Row[]) {
  return rows.reduce<MaterialPlan["grouped_summary"]>((acc, row) => {
    const group = `${row.type || "Material TBD"} / ${row.purchase_uom} / ${row.thickness_mm ?? "-"} mm / ${row.preferred_vendor || "Vendor TBD"}`;
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
}

function materialPlanWithRows(plan: MaterialPlan, rows: MaterialPhase2Row[]): MaterialPlan {
  const normalizedRows = rows.map((row, index) => {
    const required = materialPhase2RequiredQty(row);
    const available = toNumber(row.available_qty, 0);
    const reserved = toNumber(row.reserved_qty, 0);
    const shortage = Math.max(0, required + reserved - available);
    return {
      ...row,
      sl_no: index + 1,
      available_qty: available,
      reserved_qty: reserved,
      shortage_qty: shortage,
      suggested_purchase_qty: toNumber(row.suggested_purchase_qty, shortage),
      lead_time_days: toNumber(row.lead_time_days, 0),
      estimated_material_cost: toNumber(row.estimated_material_cost, 0),
      production_priority: row.production_priority ?? "normal",
    };
  });
  return {
    ...plan,
    rows: normalizedRows,
    grouped_summary: summarizeMaterialPhase2Rows(normalizedRows),
    totals: {
      component_count: normalizedRows.length,
      sheet_count: normalizedRows.reduce((sum, row) => sum + (row.reqd_qty_sheets || 0), 0),
      total_weight_kg: normalizedRows.reduce((sum, row) => sum + (row.purchase_uom === "NOS" ? 0 : row.reqd_qty_kg || 0), 0),
    },
  };
}

function blankMaterialPhase2Row(slNo: number): MaterialPhase2Row {
  return {
    reviewed: false,
    sl_no: slNo,
    type: "",
    purchase_uom: "KG",
    width_mm: null,
    length_mm: null,
    thickness_mm: null,
    reqd_qty_sheets: null,
    reqd_qty_kg: 0,
    available_qty: 0,
    reserved_qty: 0,
    shortage_qty: 0,
    suggested_purchase_qty: 0,
    lead_time_days: 0,
    preferred_vendor: "",
    estimated_material_cost: 0,
    production_priority: "normal",
    notes: "",
    planner_notes: "",
    source_count: 0,
  };
}

function materialPhase2RowsFromBreakdown(breakdown: MaterialBreakdownRow[]): MaterialPhase2Row[] {
  return breakdown.map((row, index) => {
    const material = [row.winding, row.inner_ring, row.outer_ring, row.filler].filter(Boolean).join(" / ");
    const stockType = [material || row.gasket_type || "Material TBD", row.thickness].filter(Boolean).join(" ");
    const quantity = toNumber(row.qty, 0);
    return {
      ...blankMaterialPhase2Row(index + 1),
      type: stockType,
      purchase_uom: "NOS",
      reqd_qty_kg: quantity,
      source_count: row.source_rows || 1,
      notes: [
        row.size_inch ? `Size ${row.size_inch}` : "",
        row.pressure_rating,
        row.series,
        row.remarks,
      ].filter(Boolean).join(" / "),
    };
  });
}

function createManualMaterialPlan(rows: MaterialPhase2Row[], config: MaterialPlan["config"]): MaterialPlan {
  return materialPlanWithRows({
    config,
    rows: [],
    summary: [],
    grouped_summary: [],
    assumptions: ["The purchase plan is manually maintained by the material planner."],
    warnings: [],
    totals: {
      component_count: 0,
      sheet_count: 0,
      total_weight_kg: 0,
    },
  }, rows);
}

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
      purchase_uom: row.purchase_uom ?? (row.reqd_qty_sheets !== null && row.reqd_qty_sheets !== undefined ? "SHEETS" : "KG"),
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

function storedMaterialBreakdown(quote: Quote | null): MaterialBreakdownRow[] | null {
  const breakdown = quote?.stage_meta?.material_breakdown;
  if (!Array.isArray(breakdown)) return null;
  return breakdown.map((row, index) => {
    const candidate = row as Partial<MaterialBreakdownRow>;
    return {
      reviewed: Boolean(candidate.reviewed),
      line_no: toNumber(candidate.line_no, index + 1),
      gasket_type: getString(candidate.gasket_type || "SOFT_CUT"),
      size_inch: getString(candidate.size_inch),
      pressure_rating: getString(candidate.pressure_rating),
      thickness: getString(candidate.thickness),
      winding: getString(candidate.winding),
      inner_ring: getString(candidate.inner_ring),
      outer_ring: getString(candidate.outer_ring),
      filler: getString(candidate.filler),
      qty: toNumber(candidate.qty, 0),
      uom: getString(candidate.uom || "NOS"),
      series: getString(candidate.series),
      remarks: getString(candidate.remarks),
      od_mm: candidate.od_mm === null || candidate.od_mm === undefined ? null : toNumber(candidate.od_mm, 0) || null,
      id_mm: candidate.id_mm === null || candidate.id_mm === undefined ? null : toNumber(candidate.id_mm, 0) || null,
      source_rows: toNumber(candidate.source_rows, 1),
      source_description: getString(candidate.source_description),
    };
  });
}

function storedMaterialInputs(quote: Quote | null): MaterialInputRow[] {
  const inputs = quote?.stage_meta?.material_inputs;
  if (!Array.isArray(inputs)) return [];
  return inputs.map((row) => {
    const candidate = row as Partial<MaterialInputRow>;
    return {
      material: getString(candidate.material),
      component: getString(candidate.component),
      stock_form: getString(candidate.stock_form),
      purchase_uom: (["SHEETS", "KG", "COIL", "RINGS", "NOS"].includes(getString(candidate.purchase_uom)) ? candidate.purchase_uom : "KG") as MaterialInputRow["purchase_uom"],
      stock_width_mm: candidate.stock_width_mm === null || candidate.stock_width_mm === undefined ? null : toNumber(candidate.stock_width_mm, 0) || null,
      stock_length_mm: typeof candidate.stock_length_mm === "string" ? candidate.stock_length_mm : candidate.stock_length_mm === null || candidate.stock_length_mm === undefined ? null : toNumber(candidate.stock_length_mm, 0) || null,
      stock_thickness_mm: candidate.stock_thickness_mm === null || candidate.stock_thickness_mm === undefined ? null : toNumber(candidate.stock_thickness_mm, 0) || null,
      density_g_cm3: toNumber(candidate.density_g_cm3, 0),
      wastage_percent: toNumber(candidate.wastage_percent, DEFAULT_MATERIAL_PLANNING_INPUTS.purchase_wastage_percent),
      available_qty: toNumber(candidate.available_qty, 0),
      reserved_qty: toNumber(candidate.reserved_qty, 0),
      preferred_vendor: getString(candidate.preferred_vendor),
      lead_time_days: toNumber(candidate.lead_time_days, 0),
      rate_per_uom: toNumber(candidate.rate_per_uom, 0),
      moq: toNumber(candidate.moq, 0),
      notes: getString(candidate.notes),
    };
  });
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

function quotationStageFromData(qd: Record<string, unknown>, quote: Quote | null): QuotationStageId {
  const explicit = getString(qd.quotation_stage) as QuotationStageId;
  if (QUOTATION_STAGE_INDEX.has(explicit)) return explicit;
  if (quote?.stage === "po") return "po_received";
  if (quote?.stage === "sent") return "sent_to_customer";
  return "draft_preparation";
}

function quotationStageBadgeVariant(stage: QuotationStageId) {
  if (stage === "po_received") return "secondary";
  if (stage === "lost") return "warning";
  if (stage === "approval" || stage === "negotiation" || stage === "revision") return "warning";
  if (stage === "sent_to_customer" || stage === "ready_to_send") return "outline";
  return "muted";
}

function quotationStageChecklist(
  stage: QuotationStageId,
  approval: ApprovalState,
  pricingSummary: ReturnType<typeof buildQuotePricingSummary>,
  qualityScore: number,
) {
  return [
    { label: "Technical risk reviewed", done: qualityScore >= 75 || stage !== "draft_preparation" },
    { label: "Cost and margins entered", done: pricingSummary.costTotal > 0 && pricingSummary.lines.some((line) => line.sellingPrice > 0) },
    { label: "Commercial terms completed", done: stage !== "draft_preparation" && stage !== "technical_review" },
    { label: "Approval cleared where required", done: !pricingSummary.approvalRequired || approval.status === "approved" },
  ];
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function descriptionWithSpecial(item: GasketItem, nextSpecial: string): string {
  const special = nextSpecial.trim();
  const previousSpecial = getString(item.special).trim();
  let description = getString(item.ggpl_description).trim();
  if (previousSpecial && description) {
    description = description
      .replace(new RegExp(`\\s*,\\s*${escapeRegExp(previousSpecial)}\\s*`, "i"), ", ")
      .replace(new RegExp(`${escapeRegExp(previousSpecial)}\\s*,\\s*`, "i"), "")
      .replace(new RegExp(`${escapeRegExp(previousSpecial)}`, "i"), "")
      .replace(/\s*,\s*,\s*/g, ", ")
      .replace(/\s{2,}/g, " ")
      .replace(/,\s*$/, "")
      .trim();
  }
  if (!special || description.toUpperCase().includes(special.toUpperCase())) return description;
  return description ? `${description}, ${special}` : special;
}

function setItemValue(item: GasketItem, field: string, value: string): GasketItem {
  if (field === "special") {
    return { ...item, special: value, ggpl_description: descriptionWithSpecial(item, value) };
  }
  if (field === "status") {
    const nextStatus = value.trim() || "missing";
    return {
      ...item,
      status: nextStatus,
      regret: nextStatus === "regret",
      status_source: "manual",
    };
  }
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
  if (column.field === "line_no" || column.field === "confidence" || column.field === "flags" || column.field === "ggpl_description") return false;
  return column.field === "status" || column.kind !== "readonly";
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

function normalizeExtractionSummaryRows(value: unknown): ExtractionSummaryRow[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((row) => {
      const data = row && typeof row === "object" ? row as Record<string, unknown> : {};
      return {
        item: getString(data.item || data.summary_item || data.key),
        count: toNumber(data.count, 0),
        note1: getString(data.note1),
        note2: getString(data.note2),
      };
    })
    .filter((row) => row.item || row.count || row.note1 || row.note2);
}

function normalizeStoredExtractionSummary(value: unknown): StoredExtractionSummary | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<StoredExtractionSummary>;
  if (!Array.isArray(candidate.rows)) return null;
  return {
    source_quote_version: toNumber(candidate.source_quote_version, 0),
    generated_at: getString(candidate.generated_at),
    item_signature: getString(candidate.item_signature),
    rows: normalizeExtractionSummaryRows(candidate.rows),
    unmatched_item_rows: Array.isArray(candidate.unmatched_item_rows)
      ? candidate.unmatched_item_rows.map((row) => toNumber(row, 0)).filter(Boolean)
      : [],
  };
}

function extractionSummaryItemSignature(items: GasketItem[]): string {
  return JSON.stringify(items.map((item) =>
    Object.keys(item)
      .sort()
      .map((key) => [key, item[key]]),
  ));
}

function summaryRowsMatch(left: ExtractionSummaryRow[], right: ExtractionSummaryRow[]) {
  if (left.length !== right.length) return false;
  return left.every((row, index) => row.item === right[index]?.item && row.count === right[index]?.count);
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

type SavedQuoteFilters = {
  queueFilter?: string;
  statusFilter?: string;
  columnPreset?: string;
  tableMode?: "guided" | "spreadsheet";
};

function savedFiltersFor(section: QuoteSection): SavedQuoteFilters | null {
  if (typeof window === "undefined") return null;
  try {
    const saved = window.localStorage.getItem(`${SAVED_QUOTE_FILTERS_PREFIX}${section}`);
    return saved ? JSON.parse(saved) as SavedQuoteFilters : null;
  } catch {
    return null;
  }
}

function persistSavedFilters(section: QuoteSection, filters: { queueFilter: string; statusFilter: string; columnPreset: string; tableMode: "guided" | "spreadsheet" }) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(`${SAVED_QUOTE_FILTERS_PREFIX}${section}`, JSON.stringify(filters));
  } catch {
    // Preferences are optional when browser storage is unavailable.
  }
}

function rememberRecentQuote(row: Quote) {
  void row;
}

function Field({
  label,
  value,
  onChange,
  textarea,
  type = "text",
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  textarea?: boolean;
  type?: string;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {textarea ? (
        <textarea
          className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
        />
      ) : (
        <Input type={type} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} />
      )}
    </div>
  );
}

function CompactMetric({
  icon,
  label,
  value,
  tone = "neutral",
  className = "",
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  tone?: "neutral" | "ready" | "check" | "missing";
  className?: string;
}) {
  const toneClass =
    tone === "ready"
      ? "border-emerald-200 bg-emerald-50/70 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/25 dark:text-emerald-100"
      : tone === "check"
        ? "border-amber-200 bg-amber-50/70 text-amber-950 dark:border-amber-900 dark:bg-amber-950/25 dark:text-amber-100"
        : tone === "missing"
          ? "border-red-200 bg-red-50/70 text-red-950 dark:border-red-900 dark:bg-red-950/25 dark:text-red-100"
          : "border-border bg-background";
  return (
    <div className={`inline-flex h-9 items-center gap-2 rounded-md border px-2.5 text-sm ${toneClass} ${className}`}>
      <span className="text-muted-foreground">{icon}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-semibold">{value}</span>
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
  const [emailTablePreview, setEmailTablePreview] = React.useState<ClipboardTableDetection | null>(null);
  const [excelFile, setExcelFile] = React.useState<File | null>(null);
  const [manualRows, setManualRows] = React.useState<GasketItem[]>([blankItem(1)]);
  const [startingExtraction, setStartingExtraction] = React.useState(false);
  const [previewUrl, setPreviewUrl] = React.useState("");
  const [selectedRows, setSelectedRows] = React.useState<Set<number>>(new Set());
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [columnPreset, setColumnPreset] = React.useState("review");
  const [tableMode, setTableMode] = React.useState<"guided" | "spreadsheet">(DEFAULT_TABLE_MODE);
  const [compactRows, setCompactRows] = React.useState(true);
  const [spreadsheetFullscreen, setSpreadsheetFullscreen] = React.useState(false);
  const [draftPage, setDraftPage] = React.useState(0);
  const [finalPage, setFinalPage] = React.useState(0);
  const [rfiText, setRfiText] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [exporting, setExporting] = React.useState<string | null>(null);
  const [intakeCollapsed, setIntakeCollapsed] = React.useState(false);
  const [enquirySetupOpen, setEnquirySetupOpen] = React.useState(false);
  const [quotationSetupOpen, setQuotationSetupOpen] = React.useState(false);
  const [rowEditorOpen, setRowEditorOpen] = React.useState(false);
  const [materialBreakdown, setMaterialBreakdown] = React.useState<MaterialBreakdownRow[] | null>(null);
  const [materialInputs, setMaterialInputs] = React.useState<MaterialInputRow[]>([]);
  const [materialPlan, setMaterialPlan] = React.useState<MaterialPlan | null>(null);
  const [materialConfig, setMaterialConfig] = React.useState({
    sheet_width_mm: DEFAULT_SHEET_WIDTH_MM,
    sheet_length_mm: DEFAULT_SHEET_LENGTH_MM,
    nesting_efficiency: DEFAULT_NESTING_EFFICIENCY,
    ...DEFAULT_MATERIAL_PLANNING_INPUTS,
  });
  const [currentUser, setCurrentUser] = React.useState(() => getCurrentAppUser());
  const [appUsers, setAppUsers] = React.useState(() => getAppUsers());
  const [masterData, setMasterData] = React.useState<BusinessMasterData>({ customers: [], epc_names: [] });
  const [accessSettings, setAccessSettings] = React.useState(() => getAccessSettings());
  const [approvalComment, setApprovalComment] = React.useState("");
  const [outlookDraft, setOutlookDraft] = React.useState<OutlookThreadLink>(blankOutlookThread);
  const [outlookQuickInput, setOutlookQuickInput] = React.useState("");
  const [outlookMessages, setOutlookMessages] = React.useState<OutlookLinkedMessage[]>([]);
  const [outlookLoading, setOutlookLoading] = React.useState(false);
  const [draftScrollTop, setDraftScrollTop] = React.useState(0);
  const [undoItems, setUndoItems] = React.useState<{ label: string; items: GasketItem[]; local?: boolean } | null>(null);
  const [hasUnsavedLocalEdits, setHasUnsavedLocalEdits] = React.useState(false);
  const [autoUpdateRows, setAutoUpdateRows] = React.useState<Set<number>>(new Set());
  const [activeCell, setActiveCell] = React.useState<GridCell | null>(null);
  const [editingCell, setEditingCell] = React.useState<GridCell | null>(null);
  const [selectionAnchor, setSelectionAnchor] = React.useState<GridCell | null>(null);
  const [selectionFocus, setSelectionFocus] = React.useState<GridCell | null>(null);
  const [isSelectingCells, setIsSelectingCells] = React.useState(false);
  const [columnFilters, setColumnFilters] = React.useState<Record<string, string>>({});
  const [gridSort, setGridSort] = React.useState<GridSort>(null);
  const isDraftSection = section === "drafts";
  const isMaterialSection = section === "material";
  const isFinalSection = section === "final";
  const isPoSection = section === "po";
  const isQuotationSection = isFinalSection || isPoSection;
  const sectionBasePath = isPoSection ? "/purchase-orders" : isFinalSection ? "/quotes/final" : isMaterialSection ? "/material-planning" : "/quotes";
  const canCreateEnquiry = canRole(currentUser.role, "create_enquiry", accessSettings);
  const canAddDetails = canRole(currentUser.role, "edit_sales_details", accessSettings);
  const canEditLineItems = canRole(currentUser.role, "edit_line_items", accessSettings);
  const canEditWorkflow = canRole(currentUser.role, "edit_workflow", accessSettings);
  const canEditQuotation = canRole(currentUser.role, "edit_quotation", accessSettings);
  const canEditQuote = canCreateEnquiry || canEditLineItems || canEditWorkflow || canEditQuotation;
  const canRunMaterialPhase1 = canEditWorkflow;
  const canEditMaterialPhase2 = canRole(currentUser.role, "edit_material_phase2", accessSettings);
  const canSaveProgress = Boolean(quote && (canEditQuote || canAddDetails || canEditMaterialPhase2));
  const loadedQuoteId = React.useRef<string | null>(null);
  const draftGridRef = React.useRef<HTMLDivElement | null>(null);
  const [filtersReady, setFiltersReady] = React.useState(false);
  const initialRouteLoaded = React.useRef(false);
  const newQuoteRequest = React.useRef<string | null>(null);
  const locallyStartedExtractionJobs = React.useRef(new Map<string, string>());

  const qd = React.useMemo(() => quoteDataWithDefaults(quote?.quote_data), [quote?.quote_data]);
  const items = React.useMemo(() => quote?.items ?? [], [quote?.items]);
  const salesRepUsers = React.useMemo(
    () => appUsers
      .filter((user) => user.active)
      .sort((left, right) => {
        const leftRank = left.role === "sales" ? 0 : 1;
        const rightRank = right.role === "sales" ? 0 : 1;
        return leftRank - rightRank || left.name.localeCompare(right.name);
      }),
    [appUsers],
  );
  const quotationSalesRepLabel = resolveAppUserName([qd.rep_name, qd.rep_email, qd.sales_rep_user_id], appUsers, "Custom sales rep");
  const selectedEnquiryOwnerId = getString(quote?.stage_meta?.owner_id);
  const selectedEnquiryOwnerValue = salesRepUsers.some((user) => user.id === selectedEnquiryOwnerId) ? selectedEnquiryOwnerId : CUSTOM_SALES_REP_VALUE;
  const selectedEnquiryOwnerLabel = resolveAppUserName([
    quote?.stage_meta?.owner_name,
    quote?.stage_meta?.owner_email,
    quote?.stage_meta?.owner_id,
  ], appUsers, "Unassigned");
  const createdByUser = React.useMemo(() => {
    if (!quote?.created_by) return undefined;
    const createdBy = quote.created_by.toLowerCase();
    return appUsers.find((user) => user.id.toLowerCase() === createdBy || user.email.toLowerCase() === createdBy);
  }, [appUsers, quote?.created_by]);
  const createdByUsernameFromMeta = getString(quote?.stage_meta?.created_by_username);
  const createdByNameFromMeta = getString(quote?.stage_meta?.created_by_name);
  const createdByRoleFromMeta = getString(quote?.stage_meta?.created_by_role);
  const createdByRoleLabel = createdByRoleFromMeta && createdByRoleFromMeta in roleLabels
    ? roleLabels[createdByRoleFromMeta as keyof typeof roleLabels]
    : createdByUser?.role ? roleLabels[createdByUser.role] : "User";
  const createdByUsername = createdByUsernameFromMeta || createdByUser?.id || getString(quote?.created_by);
  const createdByDisplayName = resolveAppUserName([
    createdByNameFromMeta,
    quote?.stage_meta?.created_by_email,
    createdByUsername,
  ], appUsers);
  const createdByLabel = createdByDisplayName
    ? `${createdByDisplayName} - ${createdByRoleLabel}`
    : createdByNameFromMeta || "Not recorded";
  const currentEnquiryStage = quote ? enquiryStageFromQuote(quote) : "draft";
  const enquiryMarketType = getString(quote?.stage_meta?.market_type);
  const effectiveQuoteNo = getString(quote?.quote_no);
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
        if (statusFilter === "ready") return item.status === "ready";
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
  const activeVirtualRowHeight = tableMode === "spreadsheet" ? compactRows ? 42 : 72 : VIRTUAL_ROW_HEIGHT;
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
  const selectedOrVisibleIndices = selectedIndices.length ? selectedIndices : displayIndices;
  const selectedOrVisibleRows = selectedOrVisibleIndices.map((index) => items[index]).filter(Boolean);
  const hasActionRows = selectedOrVisibleRows.length > 0;
  const hasRowsWithCustomerText = selectedOrVisibleRows.some((item) => getString(item.raw_description).trim());
  const hasRequiredMarketType = Boolean(QUOTATION_NUMBER_PREFIX[getString(quote?.stage_meta?.market_type)]);
  const emailCreateDisabled = startingExtraction || saving || !emailText.trim() || !hasRequiredMarketType;
  const emailCreateTitle = !hasRequiredMarketType
    ? "Select Export or Domestic first"
    : !emailText.trim()
      ? "Paste enquiry text first"
      : "Create line items from the pasted email";
  const excelCreateDisabled = startingExtraction || saving || !excelFile || !hasRequiredMarketType;
  const excelCreateTitle = !hasRequiredMarketType
    ? "Select Export or Domestic first"
    : !excelFile
      ? "Choose an Excel or CSV file first"
      : "Create line items from the selected Excel or CSV file";
  const rereadRowsDisabled = saving || startingExtraction || !hasRowsWithCustomerText;
  const rereadRowsTitle = !hasActionRows
    ? "No rows available to re-read"
    : !hasRowsWithCustomerText
      ? "Selected or visible rows need customer description text"
      : selectedIndices.length
        ? "Re-read selected rows from customer text"
        : "Re-read visible rows from customer text";
  const saveProgressDisabled = saving || !hasUnsavedLocalEdits;
  const saveProgressTitle = hasUnsavedLocalEdits ? "Save progress (Ctrl+S)" : "No unsaved changes";
  const selectedRowIndex = selectedIndices.length === 1 ? selectedIndices[0] : null;
  const selectedItem = selectedRowIndex !== null ? items[selectedRowIndex] : null;
  const activeGridColumn = activeCell ? activeTableColumns[activeCell.colIndex] : undefined;
  const activeGridItem = activeCell ? items[activeCell.rowIndex] : undefined;
  const activeCellAddress = activeCell && activeGridColumn
    ? `${spreadsheetColumnName(activeCell.colIndex)}${(displayIndexPositions.get(activeCell.rowIndex) ?? activeCell.rowIndex) + 1}`
    : "";
  const activeCellValue = activeGridItem && activeGridColumn ? columnValue(activeGridItem, activeGridColumn) : "";
  const selectedItemBadges = selectedItem ? issueBadgesForItem(selectedItem) : [];
  const extractionSummary = React.useMemo(() => {
    const summary = items.reduce<Record<string, number>>((acc, item) => {
      const key = summaryKey(item);
      if (key) acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});
    return Object.entries(summary).sort((left, right) => right[1] - left[1]);
  }, [items]);
  const legacyExtractionSummaryRows = React.useMemo(
    () => normalizeExtractionSummaryRows(quote?.stage_meta?.extraction_summary_rows),
    [quote?.stage_meta?.extraction_summary_rows],
  );
  const extractionSummaryNotes = React.useMemo(
    () => {
      const notes = {
        ...(quote?.stage_meta?.extraction_summary_notes as Record<string, { note1?: string; note2?: string }> | undefined),
      };
      legacyExtractionSummaryRows.forEach((row) => {
        if (!row.item || (!row.note1 && !row.note2)) return;
        notes[row.item] = {
          note1: getString(notes[row.item]?.note1 || row.note1),
          note2: getString(notes[row.item]?.note2 || row.note2),
        };
      });
      return notes;
    },
    [legacyExtractionSummaryRows, quote?.stage_meta?.extraction_summary_notes],
  );
  const extractionSummaryRows = React.useMemo(
    () => extractionSummary.map(([item, count]) => ({
      item,
      count,
      note1: getString(extractionSummaryNotes[item]?.note1),
      note2: getString(extractionSummaryNotes[item]?.note2),
    })),
    [extractionSummary, extractionSummaryNotes],
  );
  const unmatchedSummaryItemRows = React.useMemo(
    () => items
      .map((item, index) => ({ index, key: summaryKey(item), status: item.status }))
      .filter((row) => !row.key && row.status !== "regret")
      .map((row) => row.index + 1),
    [items],
  );
  const currentExtractionSummarySignature = React.useMemo(() => extractionSummaryItemSignature(items), [items]);
  const storedExtractionSummary = React.useMemo(
    () => normalizeStoredExtractionSummary(quote?.stage_meta?.extraction_summary),
    [quote?.stage_meta?.extraction_summary],
  );
  const extractionSummaryStale = !storedExtractionSummary
    || storedExtractionSummary.item_signature !== currentExtractionSummarySignature
    || !summaryRowsMatch(storedExtractionSummary.rows, extractionSummaryRows)
    || JSON.stringify(storedExtractionSummary.unmatched_item_rows) !== JSON.stringify(unmatchedSummaryItemRows);

  function invalidateMaterialPlan() {
    setMaterialPlan(null);
  }

  function canDiscardUnsavedEdits(action: string) {
    return !hasUnsavedLocalEdits || window.confirm(`You have unsaved edits. ${action} without saving them?`);
  }

  function updateQuoteDraft(patch: Partial<Quote>) {
    setQuote((current) => current ? { ...current, ...patch } : current);
    setHasUnsavedLocalEdits(true);
  }

  function isSalesDetailPayload(payload: Partial<Quote>) {
    if (currentUser.role !== "sales") return false;
    const allowedQuoteKeys = new Set(["customer", "project_ref", "custom_label", "quote_data", "stage_meta"]);
    if (Object.keys(payload).some((key) => !allowedQuoteKeys.has(key))) return false;
    return true;
  }

  function canSavePayload(payload: Partial<Quote>) {
    return canEditQuote || isSalesDetailPayload(payload);
  }

  async function saveSalesDetails(success = "Details saved") {
    if (!quote || !canAddDetails) return undefined;
    const salesNotes = getString(quote.stage_meta?.sales_notes);
    const stageMeta = appendActivity(
      { ...(quote.stage_meta ?? {}), sales_notes: salesNotes },
      {
        kind: "workflow",
        title: "Sales details updated",
        detail: salesNotes ? "Sales notes saved" : "Customer details saved",
        user: currentUser.name || currentUser.id,
      },
    );
    return savePatch(
      {
        customer: quote.customer,
        project_ref: quote.project_ref,
        custom_label: quote.custom_label,
        quote_no: quote.quote_no,
        quote_data: { ...(quote.quote_data ?? {}), ...pickSalesDetailQuoteData(qd) },
        stage_meta: stageMeta,
      } as Partial<Quote>,
      success,
    );
  }

  async function resolveOutlookThread() {
    if (!outlookDraft.message_id.trim()) {
      toast.error("Enter the Outlook message id first");
      return;
    }
    setOutlookLoading(true);
    try {
      const resolved = await resolveOutlookMessage({
        mailboxUser: outlookDraft.mailbox_user,
        messageId: outlookDraft.message_id,
      });
      setOutlookDraft(outlookThreadFromMessage(resolved));
      toast.success("Outlook message resolved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Outlook lookup failed");
    } finally {
      setOutlookLoading(false);
    }
  }

  async function loadOutlookThreadMessages() {
    const source = outlookThread ?? outlookDraft;
    if (!source.conversation_id.trim()) {
      toast.error("Conversation id is required");
      return;
    }
    setOutlookLoading(true);
    try {
      const messages = await listOutlookThreadMessages({
        mailboxUser: source.mailbox_user,
        conversationId: source.conversation_id,
      });
      setOutlookMessages(messages);
      toast.success("Outlook thread refreshed");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Outlook thread refresh failed");
    } finally {
      setOutlookLoading(false);
    }
  }

  async function propagateOutlookThreadToLinkedRecords(thread: OutlookThreadLink | null) {
    if (!quote) return;
    const linkedIds = [
      getString(quote.stage_meta?.linked_quote_id),
      getString(quote.stage_meta?.source_enquiry_id),
    ].filter((id) => id && id !== quote.id);
    for (const id of Array.from(new Set(linkedIds))) {
      try {
        const linked = await getQuote(id);
        const linkedMeta = { ...(linked.stage_meta ?? {}) };
        if (thread) linkedMeta.outlook_thread = thread;
        else delete linkedMeta.outlook_thread;
        await patchQuote(id, { stage_meta: linkedMeta } as Partial<Quote>);
      } catch {
        // Keep the current record linked even if an older linked record is unavailable.
      }
    }
  }

  async function saveOutlookThread(threadOverride?: OutlookThreadLink) {
    if (!quote || !canAddDetails) return;
    const source = threadOverride ?? outlookDraft;
    const nextThread = {
      ...source,
      linked_at: source.linked_at || new Date().toISOString(),
      linked_by: source.linked_by || currentUser.id,
    };
    if (!nextThread.conversation_id && !nextThread.message_id && !nextThread.web_link) {
      toast.error("Add a conversation id, message id, or Outlook link");
      return;
    }
    const nextMeta = appendActivity(
      { ...(quote.stage_meta ?? {}), outlook_thread: nextThread },
      {
        kind: "workflow",
        title: "Outlook thread linked",
        detail: nextThread.subject || nextThread.conversation_id || nextThread.message_id,
        user: currentUser.name || currentUser.id,
      },
    );
    const saved = await savePatch({ stage_meta: nextMeta } as Partial<Quote>, "Outlook thread linked");
    if (saved) await propagateOutlookThreadToLinkedRecords(nextThread);
  }

  async function connectOutlookThread() {
    if (!quote || !canAddDetails) return;
    const input = outlookQuickInput.trim();
    if (!input) {
      toast.error("Paste an Outlook email link or message id");
      return;
    }
    const messageId = messageIdFromOutlookInput(input);
    const webLink = webLinkFromOutlookInput(input);
    const baseThread = {
      ...outlookDraft,
      message_id: messageId || outlookDraft.message_id,
      web_link: webLink || outlookDraft.web_link,
    };
    if (!messageId) {
      setOutlookDraft(baseThread);
      await saveOutlookThread(baseThread);
      return;
    }
    setOutlookLoading(true);
    try {
      const resolved = await resolveOutlookMessage({
        mailboxUser: baseThread.mailbox_user,
        messageId,
      });
      const nextThread = {
        ...outlookThreadFromMessage(resolved),
        web_link: outlookThreadFromMessage(resolved).web_link || webLink,
      };
      setOutlookDraft(nextThread);
      await saveOutlookThread(nextThread);
    } catch (error) {
      const fallbackThread = {
        ...baseThread,
        linked_at: new Date().toISOString(),
        linked_by: currentUser.id,
      };
      setOutlookDraft(fallbackThread);
      await saveOutlookThread(fallbackThread);
      toast.warning(error instanceof Error ? `Saved link without Graph lookup: ${error.message}` : "Saved link without Graph lookup");
    } finally {
      setOutlookLoading(false);
    }
  }

  async function unlinkOutlookThread() {
    if (!quote || !canAddDetails) return;
    const nextMeta = { ...(quote.stage_meta ?? {}) };
    delete nextMeta.outlook_thread;
    const withActivity = appendActivity(nextMeta, {
      kind: "workflow",
      title: "Outlook thread unlinked",
      detail: outlookThread?.subject || outlookThread?.conversation_id || "Thread removed",
      user: currentUser.name || currentUser.id,
    });
    setOutlookDraft(blankOutlookThread);
    setOutlookMessages([]);
    const saved = await savePatch({ stage_meta: withActivity } as Partial<Quote>, "Outlook thread unlinked");
    if (saved) await propagateOutlookThreadToLinkedRecords(null);
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
    if (params.get("new") === "1") {
      const requestKey = params.toString();
      if (newQuoteRequest.current !== requestKey) {
        newQuoteRequest.current = requestKey;
        initialRouteLoaded.current = true;
        void startQuote();
      }
      return;
    }
    if (initialRouteLoaded.current) return;
    initialRouteLoaded.current = true;
    refreshQuotes(params.get("quote") ?? undefined).catch((error) => toast.error(error.message));
    // The initial quote id is read once from the URL so resume links open deterministically.
    // The new enquiry flag remains reactive so the global header button works on this page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  React.useEffect(() => {
    if (quote?.id === loadedQuoteId.current) return;
    loadedQuoteId.current = quote?.id ?? null;
    setIntakeCollapsed(Boolean(quote && !isQuotationSection && (quote.items?.length ?? 0) > 0));
    setMaterialBreakdown(isMaterialSection ? storedMaterialBreakdown(quote) : null);
    setMaterialInputs(isMaterialSection ? storedMaterialInputs(quote) : []);
    const storedPlan = isMaterialSection ? storedMaterialPlan(quote) : null;
    setMaterialPlan(storedPlan);
    if (storedPlan?.config) {
      setMaterialConfig((current) => ({
        ...current,
        sheet_width_mm: storedPlan.config.sheet_width_mm ?? current.sheet_width_mm,
        sheet_length_mm: storedPlan.config.sheet_length_mm ?? current.sheet_length_mm,
        nesting_efficiency: storedPlan.config.nesting_efficiency ?? current.nesting_efficiency,
        winding_strip_width_mm: storedPlan.config.winding_strip_width_mm ?? current.winding_strip_width_mm,
        winding_strip_thickness_mm: storedPlan.config.winding_strip_thickness_mm ?? current.winding_strip_thickness_mm,
        filler_tape_width_mm: storedPlan.config.filler_tape_width_mm ?? current.filler_tape_width_mm,
        filler_tape_thickness_mm: storedPlan.config.filler_tape_thickness_mm ?? current.filler_tape_thickness_mm,
        ring_radial_allowance_mm: storedPlan.config.ring_radial_allowance_mm ?? current.ring_radial_allowance_mm,
        ring_thickness_mm: storedPlan.config.ring_thickness_mm ?? current.ring_thickness_mm,
        purchase_wastage_percent: storedPlan.config.purchase_wastage_percent ?? current.purchase_wastage_percent,
      }));
    }
    setDraftPage(0);
    setFinalPage(0);
    setHasUnsavedLocalEdits(false);
    setAutoUpdateRows(new Set());
  }, [isMaterialSection, isQuotationSection, quote]);

  React.useEffect(() => {
    const thread = outlookThreadFromMeta(quote?.stage_meta);
    setOutlookDraft(thread ?? blankOutlookThread);
    setOutlookQuickInput(thread?.web_link || thread?.message_id || thread?.conversation_id || "");
    setOutlookMessages([]);
  }, [quote?.id, quote?.stage_meta]);

  React.useEffect(() => {
    setDraftPage(0);
  }, [columnFilters, gridSort, statusFilter, quote?.id]);

  React.useEffect(() => {
    setDraftScrollTop(0);
    if (draftGridRef.current) {
      draftGridRef.current.scrollTop = 0;
    }
    setEditingCell(null);
  }, [columnFilters, gridSort, safeDraftPage, statusFilter, quote?.id]);

  React.useEffect(() => {
    setActiveCell(null);
    setEditingCell(null);
    setSelectionAnchor(null);
    setSelectionFocus(null);
    setIsSelectingCells(false);
  }, [columnPreset, quote?.id, tableMode]);

  React.useEffect(() => {
    if (!spreadsheetFullscreen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [spreadsheetFullscreen]);

  React.useEffect(() => {
    if (!isSelectingCells) return undefined;
    const stopSelecting = () => setIsSelectingCells(false);
    window.addEventListener("mouseup", stopSelecting);
    return () => window.removeEventListener("mouseup", stopSelecting);
  }, [isSelectingCells]);

  React.useEffect(() => {
    const refresh = () => {
      listAppUsers().then(setAppUsers).catch(() => setAppUsers([]));
      setCurrentUser(getCurrentAppUser());
      setAccessSettings(getAccessSettings());
    };
    getCurrentAppUserRemote()
      .then((user) => {
        setCurrentAppUser(user);
        setCurrentUser(user);
      })
      .catch(() => undefined);
    listAppUsers().then(setAppUsers).catch(() => setAppUsers([]));
    getBusinessMasterData().then(setMasterData).catch(() => setMasterData({ customers: [], epc_names: [] }));
    getAccessSettingsRemote()
      .then((settings) => {
        const normalized = normalizeAccessSettings(settings);
        saveAccessSettings(normalized);
        setAccessSettings(normalized);
      })
      .catch(() => setAccessSettings(getAccessSettings()));
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
      window.removeEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  React.useEffect(() => {
    setFiltersReady(false);
    const saved = savedFiltersFor(section);
    if (saved?.queueFilter) setQueueFilter(saved.queueFilter);
    if (saved?.statusFilter) setStatusFilter(saved.statusFilter);
    if (saved?.columnPreset) setColumnPreset(saved.columnPreset);
    setTableMode(DEFAULT_TABLE_MODE);
    setFiltersReady(true);
  }, [currentUser.role, section]);

  React.useEffect(() => {
    if (!filtersReady) return;
    persistSavedFilters(section, { queueFilter, statusFilter, columnPreset, tableMode });
  }, [columnPreset, filtersReady, queueFilter, section, statusFilter, tableMode]);

  React.useEffect(() => {
    if (!hasUnsavedLocalEdits) return undefined;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
      return "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedLocalEdits]);

  React.useEffect(() => {
    async function refreshCompletedJob(jobId: string, quoteId: string) {
      try {
        const status = await getJobStatus(jobId);
        if (status.status !== "succeeded" || quoteId !== quote?.id || hasUnsavedLocalEdits) return;
        await refreshQuotes(quoteId);
      } catch {
        // The global monitor still reports failures. Auto-refresh is best effort.
      }
    }

    const handleBackgroundJobsChanged = () => {
      const activeIds = new Set(listBackgroundJobs().map((job) => job.id));
      locallyStartedExtractionJobs.current.forEach((quoteId, jobId) => {
        if (activeIds.has(jobId)) return;
        locallyStartedExtractionJobs.current.delete(jobId);
        void refreshCompletedJob(jobId, quoteId);
      });
    };
    const handleCompletedEvent = (event: Event) => {
      const detail = (event as CustomEvent<{ jobId?: string; quoteId?: string; status?: string }>).detail;
      if (!detail?.jobId || !detail.quoteId || detail.status !== "succeeded") return;
      locallyStartedExtractionJobs.current.delete(detail.jobId);
      void refreshCompletedJob(detail.jobId, detail.quoteId);
    };

    window.addEventListener(BACKGROUND_JOBS_EVENT, handleBackgroundJobsChanged);
    window.addEventListener("gasket:job-completed", handleCompletedEvent);
    return () => {
      window.removeEventListener(BACKGROUND_JOBS_EVENT, handleBackgroundJobsChanged);
      window.removeEventListener("gasket:job-completed", handleCompletedEvent);
    };
  // refreshQuotes is intentionally excluded: it is declared in this state-owner
  // component and changes identity on each render.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasUnsavedLocalEdits, quote?.id]);

  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "s") return;
      if (!canSaveProgress || saveProgressDisabled) return;
      event.preventDefault();
      void saveCurrentProgress();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  // saveCurrentProgress is intentionally excluded to avoid re-registering the
  // shortcut on every render of this state-owner component.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canSaveProgress, saveProgressDisabled, quote, items, qd, materialBreakdown, materialPlan, isMaterialSection]);

  React.useEffect(() => {
    if (!quote || !canEditLineItems || !autoUpdateRows.size) return undefined;
    const timer = window.setTimeout(() => {
      const target = Array.from(autoUpdateRows).filter((index) => Boolean(items[index]));
      setAutoUpdateRows(new Set());
      if (target.length) {
        void recomputeRows(target, { success: undefined });
      }
    }, AUTO_UPDATE_DELAY_MS);
    return () => window.clearTimeout(timer);
  // recomputeRows is intentionally excluded because its inputs are represented
  // by the row state dependencies above.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoUpdateRows, canEditLineItems, items, quote]);

  async function startQuote() {
    if (!canCreateEnquiry) {
      toast.error("You do not have permission to create enquiry workspaces.");
      router.replace("/quotes");
      return;
    }
    if (quote && !canDiscardUnsavedEdits("Start a new enquiry")) return;
    setSaving(true);
    try {
      invalidateMaterialPlan();
      const created = await createQuote({
        customer: "",
        project_ref: "",
        items: [],
        quote_data: quoteDataWithDefaults(),
        stage: "initial",
        stage_meta: {
          enquiry_stage: "draft",
          created_by_username: currentUser.id,
          created_by_name: currentUser.name,
          created_by_role: currentUser.role,
          created_by_email: currentUser.email,
        },
      } as Partial<Quote>);
      setQuote(created);
      await refreshQuotes(created.id);
      setSelectedRows(new Set());
      setRfiText("");
      setIntakeCollapsed(false);
      router.push(`/quotes?quote=${created.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create quote");
    } finally {
      setSaving(false);
    }
  }

  function clearWorkspace() {
    if (!canDiscardUnsavedEdits("Return to the enquiry list")) return;
    invalidateMaterialPlan();
    setQuote(null);
    setEmailText("");
    setEmailTablePreview(null);
    setExcelFile(null);
    setManualRows([blankItem(1)]);
    setStartingExtraction(false);
    setSelectedRows(new Set());
    setPreviewUrl("");
    setStatusFilter("all");
    setQueueFilter("all");
    setColumnPreset("review");
    setTableMode(DEFAULT_TABLE_MODE);
    setCompactRows(false);
    setRfiText("");
    setSaving(false);
    setExporting(null);
    setIntakeCollapsed(false);
    router.push(sectionBasePath);
  }

  async function openQuotationScreen() {
    if (!canEditQuotation) {
      toast.error("Sales users can view quotations, but cannot create or update quotation work.");
      return;
    }
    if (!quote) return;
    const linkedQuoteId = getString(quote.stage_meta?.linked_quote_id);
    if (linkedQuoteId) {
      if (hasUnsavedLocalEdits) {
        const savedEnquiry = await savePatch({ items, quote_data: qd, quote_no: effectiveQuoteNo } as Partial<Quote>);
        if (savedEnquiry) await syncLinkedQuotationFromEnquiry(savedEnquiry, savedEnquiry.items);
      }
      const linked = await getQuote(linkedQuoteId);
      setQuote(linked);
      rememberRecentQuote(linked);
      await refreshQuotes(linked.id);
      router.push(`/quotes/final?quote=${linked.id}`);
      return;
    }
    const marketType = getString(quote.stage_meta?.market_type);
    if (!QUOTATION_NUMBER_PREFIX[marketType]) {
      toast.error("Select Export or Domestic before creating the quotation.");
      return;
    }
    const savedEnquiry = await savePatch({ items, quote_data: qd, quote_no: effectiveQuoteNo, stage_meta: quote.stage_meta } as Partial<Quote>);
    if (!savedEnquiry) return;
    const now = new Date().toISOString();
    const latestQuotes = await listQuotes();
    const quotationNo = nextQuotationNumber(latestQuotes, marketType);
    if (!quotationNo) {
      toast.error("Could not generate quotation number. Select Export or Domestic and try again.");
      return;
    }
    const quotationQuoteData = {
      ...cloneJson(savedEnquiry.quote_data),
      quote_no: quotationNo,
      quotation_number_type: marketType,
      source_enquiry_quote_no: savedEnquiry.quote_no,
    };
    const quotationMeta = appendActivity(
      {
        ...(savedEnquiry.stage_meta ?? {}),
        source_enquiry_id: savedEnquiry.id,
        source_enquiry_version: savedEnquiry.version,
        source_enquiry_quote_no: savedEnquiry.quote_no,
        quotation_number_type: marketType,
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
      quote_no: quotationNo,
      customer: savedEnquiry.customer,
      project_ref: savedEnquiry.project_ref,
      custom_label: savedEnquiry.custom_label,
      items: cloneJson(savedEnquiry.items),
      quote_data: quotationQuoteData,
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
    router.push(`/quotes/final?quote=${quotation.id}`);
  }

  function closeQuotationScreen() {
    if (!canDiscardUnsavedEdits("Leave this quotation")) return;
    if (!quote) {
      router.push("/quotes");
      return;
    }
    const sourceEnquiryId = getString(quote.stage_meta?.source_enquiry_id);
    router.push(`/quotes?quote=${sourceEnquiryId || quote.id}`);
  }

  async function syncLinkedQuotationFromEnquiry(enquiry: Quote, nextItems: GasketItem[]) {
    if (isQuotationSection) return;
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
    if (!canEditQuote) {
      toast.error("Sales users cannot delete quote workspaces.");
      return;
    }
    if (quote?.id === row.id && !canDiscardUnsavedEdits("Delete this workspace")) return;
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
    if (!canEditWorkflow) {
      toast.error("Sales users cannot change workflow metadata.");
      return;
    }
    let nextStageMeta = { ...(row.stage_meta ?? {}), ...patch };
    const activityDetails = Object.entries(patch)
      .filter(([key]) => ["owner_id", "owner_name", "owner_email", "owner_role", "priority", "due_date", "clarification_status", "with_whom", "enquiry_stage", "material_planning_enabled", "material_planning_enabled_at"].includes(key))
      .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value || "blank")}`);
    if (activityDetails.length) {
      nextStageMeta = appendActivity(nextStageMeta, {
        kind: patch.clarification_status || patch.with_whom ? "clarification" : patch.owner_id || patch.owner_name ? "owner" : patch.priority ? "priority" : patch.enquiry_stage || patch.material_planning_enabled ? "workflow" : "due_date",
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
    if (!canSavePayload(payload)) {
      toast.error("Sales users can save customer details and notes only.");
      return undefined;
    }
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

  async function saveCurrentProgress(success = "Progress saved") {
    if (!quote) return;
    if (isMaterialSection && (materialBreakdown || materialPlan)) {
      await saveMaterialPlan(materialPlan);
      return;
    }
    if (!canEditQuote) {
      await saveSalesDetails(success);
      return;
    }
    await savePatch(
      {
        customer: quote.customer,
        project_ref: quote.project_ref,
        custom_label: quote.custom_label,
        quote_no: effectiveQuoteNo,
        items,
        quote_data: qd,
        stage_meta: quote.stage_meta,
      } as Partial<Quote>,
      success,
    );
  }

  async function updateItems(nextItems: GasketItem[], success?: string) {
    if (!canEditLineItems) {
      toast.error("Sales users cannot edit line items.");
      return;
    }
    invalidateMaterialPlan();
    const updated = await savePatch({ items: nextItems } as Partial<Quote>, success);
    if (updated) await syncLinkedQuotationFromEnquiry(updated, nextItems);
  }

  async function runExtraction(sourceType: "email" | "excel" | "csv", file?: File | null) {
    if (!canEditQuote) {
      toast.error("Sales users cannot run enquiry extraction.");
      return;
    }
    if (!quote) {
      toast.error("Create a quote workspace first");
      return;
    }
    const marketType = getString(quote.stage_meta?.market_type);
    if (!QUOTATION_NUMBER_PREFIX[marketType]) {
      toast.error("Select Export or Domestic before processing the enquiry.");
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
      const savedContext = await savePatch({ stage_meta: quote.stage_meta } as Partial<Quote>);
      if (!savedContext) return;
      const accepted = await createExtraction({
        quoteId: quote.id,
        sourceType,
        text: emailText,
        file,
        customer: quote.customer,
        projectRef: quote.project_ref,
      });
      locallyStartedExtractionJobs.current.set(accepted.job_id, quote.id);
      addBackgroundJob({
        id: accepted.job_id,
        quoteId: quote.id,
        sourceType,
        label: `Reading ${sourceType === "excel" ? "Excel" : sourceType === "csv" ? "CSV" : "email"} enquiry`,
        startedAt: new Date().toISOString(),
      });
      invalidateMaterialPlan();
      setIntakeCollapsed(false);
      toast.info("We are creating the item list in the background. You can keep working and will be notified when it finishes.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Extraction failed");
    } finally {
      setStartingExtraction(false);
    }
  }

  function structuredFieldsToItems(detection: ClipboardTableDetection): GasketItem[] {
    return structuredRowsToItemFields(detection).map((row, index) => ({
      ...blankItem(items.length + index + 1),
      customer_sl_no: row.customer_sl_no,
      customer_item_code: row.customer_item_code,
      raw_description: row.raw_description,
      quantity: toNumber(row.quantity, 1) || 1,
      uom: row.uom || "NOS",
      status: "check",
      flags: ["Imported row requires review"],
    }));
  }

  async function appendImportedRows(rows: GasketItem[], success: string) {
    if (!canEditLineItems) {
      toast.error("Sales users cannot add line items.");
      return;
    }
    if (!quote) return;
    const fallbackRows = rows
      .filter((row) => getString(row.raw_description || row.customer_item_code || row.customer_sl_no).trim())
      .map((row, index) => ({
        ...blankItem(items.length + index + 1),
        ...row,
        line_no: items.length + index + 1,
        raw_description: getString(row.raw_description),
        quantity: toNumber(row.quantity, 1) || 1,
        uom: getString(row.uom || "NOS") || "NOS",
        status: "check",
        flags: Array.isArray(row.flags) && row.flags.length ? row.flags : ["Manual row added with optional fields pending review"],
      }));
    if (!fallbackRows.length) {
      toast.error("Enter at least one description or customer item code");
      return;
    }
    let nextRows: GasketItem[] = fallbackRows;
    try {
      const processed = await bulkRecompute(quote.id, fallbackRows);
      nextRows = fallbackRows.map((fallback, index) => processed[index] ? {
        ...fallback,
        ...processed[index],
        customer_sl_no: fallback.customer_sl_no,
        customer_item_code: fallback.customer_item_code,
        raw_description: fallback.raw_description,
        quantity: fallback.quantity,
        uom: fallback.uom,
        line_no: fallback.line_no,
      } : fallback);
    } catch {
      toast.warning("Rows added without recompute. Review optional fields later.");
    }
    await updateItems([...items, ...nextRows], success);
    setManualRows([blankItem(items.length + nextRows.length + 1)]);
    setEmailTablePreview(null);
    setIntakeCollapsed(true);
  }

  async function addManualItems() {
    await appendImportedRows(manualRows, `${manualRows.length} manual row(s) added`);
  }

  async function importDetectedEmailTable() {
    if (!emailTablePreview) return;
    await appendImportedRows(structuredFieldsToItems(emailTablePreview), `${emailTablePreview.bodyRows.length} table row(s) imported`);
  }

  function appendManualRows(count: number) {
    setManualRows((current) => [
      ...current,
      ...Array.from({ length: count }, (_, index) => blankItem(current.length + index + 1)),
    ]);
  }

  function updateManualRow(index: number, field: string, value: string) {
    setManualRows((current) => current.map((row, rowIndex) =>
      rowIndex === index ? setItemValue(row, field, value) : row,
    ));
  }

  function handleManualPaste(event: React.ClipboardEvent<HTMLDivElement>) {
    const detection = detectClipboardTable(event.clipboardData.getData("text/html"), event.clipboardData.getData("text/plain"));
    if (!detection) return;
    event.preventDefault();
    const imported = structuredFieldsToItems(detection).map((row, index) => ({ ...row, line_no: index + 1 }));
    setManualRows(imported.length ? imported : [blankItem(1)]);
    toast.success(`Loaded ${imported.length} pasted row${imported.length === 1 ? "" : "s"} for review`);
  }

  async function recomputeRows(indices: number[] = selectedIndices, options?: { sourceItems?: GasketItem[]; success?: string }) {
    if (!canEditLineItems) {
      toast.error("Sales users cannot update line items.");
      return;
    }
    if (!quote) return;
    const target = indices.length ? indices : items.map((_, idx) => idx);
    const sourceItems = options?.sourceItems ?? items;
    const rows = target.map((idx) => sourceItems[idx]).filter(Boolean);
    const recomputed = await bulkRecompute(quote.id, rows);
    const next = [...sourceItems];
    target.forEach((idx, offset) => {
      if (next[idx] && recomputed[offset]) {
        const current = next[idx];
        const wasRegret = current?.status === "regret" || current?.regret === true;
        const isManualStatus = current?.status_source === "manual";
        next[idx] = {
          ...recomputed[offset],
          ...(wasRegret ? { regret: true, status: "regret" } : {}),
          ...(isManualStatus ? {
            status: current?.status ?? recomputed[offset].status,
            regret: current?.regret ?? (current?.status === "regret"),
            status_source: "manual",
          } : {}),
        };
      }
    });
    const success = options && "success" in options ? options.success : "Rules and descriptions refreshed";
    await updateItems(next, success);
  }

  async function reprocessRows(indices?: number[]) {
    if (!canEditLineItems) {
      toast.error("Sales users cannot reprocess line items.");
      return;
    }
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
        const current = next[idx];
        const wasRegret = current?.status === "regret" || current?.regret === true;
        const isManualStatus = current?.status_source === "manual";
        next[idx] = {
          ...extracted[offset],
          line_no: current?.line_no ?? idx + 1,
          regret: isManualStatus ? current?.regret : wasRegret ? true : extracted[offset].regret,
          status: isManualStatus ? current?.status : wasRegret ? "regret" : extracted[offset].status,
          status_source: isManualStatus ? "manual" : extracted[offset].status_source ?? current?.status_source,
        };
      }
    });
    await updateItems(next, "Selected rows re-read from customer text");
  }

  async function buildClarificationEmail() {
    if (!canEditWorkflow) {
      toast.error("Sales users cannot change clarification workflow.");
      return;
    }
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

  function updateExtractionSummaryNote(itemKey: string, noteField: "note1" | "note2", note: string) {
    if (!quote || !canEditLineItems) return;
    const nextNotes = {
      ...extractionSummaryNotes,
      [itemKey]: {
        ...extractionSummaryNotes[itemKey],
        [noteField]: note,
      },
    };
    setQuote((current) => current ? {
      ...current,
      stage_meta: { ...(current.stage_meta ?? {}), extraction_summary_notes: nextNotes },
    } : current);
    setHasUnsavedLocalEdits(true);
  }

  async function regenerateExtractionSummary() {
    if (!quote || !canEditLineItems) return;
    const generatedAt = new Date().toISOString();
    const extractionSummaryRecord: StoredExtractionSummary = {
      source_quote_version: quote.version,
      generated_at: generatedAt,
      item_signature: currentExtractionSummarySignature,
      rows: extractionSummaryRows,
      unmatched_item_rows: unmatchedSummaryItemRows,
    };
    await savePatch({
      stage_meta: appendActivity(
        {
          ...(quote.stage_meta ?? {}),
          extraction_summary_rows: extractionSummaryRows,
          extraction_summary: extractionSummaryRecord,
          extraction_summary_notes: extractionSummaryNotes,
        },
        {
          kind: "items",
          title: "Extraction summary regenerated",
          detail: `${extractionSummaryRows.length} generated group(s), ${unmatchedSummaryItemRows.length} unmatched row(s)`,
          user: currentUser.name || currentUser.id,
        },
      ),
    } as Partial<Quote>, "Extraction summary regenerated");
  }

  async function saveExtractionSummaryNotes() {
    if (!quote || !canEditLineItems) return;
    await savePatch({
      stage_meta: appendActivity(
        { ...(quote.stage_meta ?? {}), extraction_summary_notes: extractionSummaryNotes },
        {
          kind: "items",
          title: "Extraction summary notes saved",
          detail: `${Object.keys(extractionSummaryNotes).length} summary note group(s) retained`,
          user: currentUser.name || currentUser.id,
        },
      ),
    } as Partial<Quote>, "Manual summary notes saved");
  }

  async function exportCurrent(type: "pdf" | "xlsx", mode: "preview" | "download" = "download") {
    if (!canExportQuotes) {
      toast.error("You do not have permission to export quotation documents.");
      return;
    }
    if (!quote) return;
    if (mode === "download" && !canExportFinal) {
      toast.error("Approval is required before downloading the quotation");
      return;
    }
    setExporting(type);
    try {
      const saved = await savePatch({ items, quote_data: qd, quote_no: effectiveQuoteNo } as Partial<Quote>);
      if (!saved) return;
      const response = await exportQuote(saved.id, type);
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
    if (!canEditQuotation) {
      toast.error("Sales users cannot request quotation approval.");
      return;
    }
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
        quote_data: { ...qd, quotation_stage: "approval", quotation_stage_updated_at: new Date().toISOString() },
        quote_no: effectiveQuoteNo,
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
        quote_data: { ...qd, quotation_stage: status === "approved" ? "ready_to_send" : "revision", quotation_stage_updated_at: new Date().toISOString() },
        quote_no: effectiveQuoteNo,
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

  async function setQuotationStage(stage: QuotationStageId) {
    if (!canEditWorkflow) {
      toast.error("Sales users cannot change quotation workflow.");
      return;
    }
    if (!quote) return;
    if ((stage === "sent_to_customer" || stage === "po_received") && !canExportFinal) {
      toast.error("Approval is required before moving the quotation to this stage");
      return;
    }
    const now = new Date().toISOString();
    const stageInfo = QUOTATION_STAGES[QUOTATION_STAGE_INDEX.get(stage) ?? 0];
    const history = Array.isArray(qd.quotation_stage_history) ? qd.quotation_stage_history : [];
    const nextQuoteData = {
      ...qd,
      quotation_stage: stage,
      quotation_stage_updated_at: now,
      quotation_stage_history: [
        ...history,
        {
          stage,
          label: stageInfo.label,
          at: now,
          user: currentUser.name || currentUser.id,
        },
      ],
    };
    const nextMeta = appendActivity(quote.stage_meta ?? {}, {
      kind: "workflow",
      title: "Quotation stage updated",
      detail: stageInfo.label,
      user: currentUser.name || currentUser.id,
    });
    const saved = await savePatch({ quote_data: nextQuoteData, quote_no: effectiveQuoteNo, stage_meta: nextMeta } as Partial<Quote>, "Quotation stage updated");
    if (!saved) return;
    if (stage === "sent_to_customer" && saved.stage !== "sent" && saved.stage !== "po") {
      const advanced = await advanceQuoteStage(saved.id, "sent", "Quotation sent to customer", saved.stage_meta);
      setQuote(advanced);
      setQuotes((prev) => prev.map((row) => (row.id === advanced.id ? quoteSummary(advanced) : row)));
    }
    if (stage === "po_received" && saved.stage !== "po") {
      const advanced = await advanceQuoteStage(saved.id, "po", "Customer PO received", saved.stage_meta);
      setQuote(advanced);
      setQuotes((prev) => prev.map((row) => (row.id === advanced.id ? quoteSummary(advanced) : row)));
    }
  }

  async function markSent() {
    if (!canEditWorkflow) {
      toast.error("Sales users cannot mark quotations as sent.");
      return;
    }
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
    const nextQuoteData = {
      ...qd,
      quotation_stage: "sent_to_customer",
      quotation_stage_updated_at: new Date().toISOString(),
    };
    const saved = await savePatch({ quote_data: nextQuoteData, quote_no: effectiveQuoteNo } as Partial<Quote>);
    if (!saved) return;
    const advanced = await advanceQuoteStage(saved.id, "sent", "Approved quotation sent", appendActivity(sentMeta, {
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
    if (!canEditLineItems) return;
    invalidateMaterialPlan();
    const next = [...items];
    next[index] = setItemValue(next[index] ?? blankItem(index + 1), field, value);
    setQuote((current) => (current ? { ...current, items: next } : current));
    setHasUnsavedLocalEdits(true);
    if (AUTO_UPDATE_FIELDS.has(field)) {
      setAutoUpdateRows((current) => {
        const updated = new Set(current);
        updated.add(index);
        return updated;
      });
    }
  }

  function addBlankRow() {
    if (!canEditLineItems) return;
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
    if (!canEditLineItems) {
      toast.error("Sales users cannot delete line items.");
      return;
    }
    if (!quote) return;
    if (!selectedIndices.length) return;
    if (!window.confirm(`Delete ${selectedIndices.length} selected item row(s)? You can undo this action.`)) return;
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
    if (!canEditLineItems) {
      toast.error("Sales users cannot change line-item regret status.");
      return;
    }
    if (!quote) return;
    invalidateMaterialPlan();
    const selected = new Set(selectedIndices);
    setUndoItems({ label: "Undo regret change", items });
    const next = items.map((item, index) => {
      if (!selected.has(index)) return item;
      const isRegret = item.status === "regret" || item.regret === true;
      return { ...item, regret: !isRegret, status: isRegret ? "check" : "regret", status_source: "manual" };
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
    if (!canEditLineItems) {
      toast.error("Sales users cannot restore line-item changes.");
      return;
    }
    if (!quote || !undoItems) return;
    if (undoItems.local) {
      invalidateMaterialPlan();
      setQuote((current) => current ? { ...current, items: undoItems.items } : current);
      setHasUnsavedLocalEdits(true);
      setUndoItems(null);
      toast.success("Grid change undone");
      return;
    }
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

  async function createRevision() {
    if (!canCreateEnquiry) {
      toast.error("You do not have permission to create enquiry revisions.");
      return;
    }
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
        quote_no: "",
        rev_no: revNo,
        rev_date: todayDisplayDate(),
      };
      const revision = await createQuote({
        customer: saved.customer,
        project_ref: saved.project_ref,
        custom_label: saved.custom_label,
        items: cloneJson(saved.items),
        quote_data: revisionQuoteData,
        stage: "initial",
        stage_meta: {
          ...(saved.stage_meta ?? {}),
          enquiry_stage: "draft",
          created_by_username: currentUser.id,
          created_by_name: currentUser.name,
          created_by_role: currentUser.role,
          created_by_email: currentUser.email,
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
      router.push(`/quotes?quote=${revision.id}`);
      toast.success(`Revision ${revNo} enquiry created`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create revision");
    } finally {
      setSaving(false);
    }
  }

  function updateQd(key: string, value: unknown) {
    if (!canEditQuotation && !(canAddDetails && SALES_DETAIL_QUOTE_DATA_FIELDS.has(key))) return;
    const next = { ...qd, [key]: value };
    if (BUYER_ADDRESS_FIELDS.includes(key)) {
      next.buyer_name_address = buyerNameAddressText(next);
    }
    if (key === "currency") {
      next.fx_rate = defaultFx[getString(value)] ?? 1;
    }
    if (key === "discount_pct") {
      next.discount_approval_pct = Number(value) || 0;
    }
    setQuote((current) => (current ? { ...current, quote_data: next, quote_no: effectiveQuoteNo } : current));
    setHasUnsavedLocalEdits(true);
  }

  function selectCustomer(customerId: string) {
    const customer = masterData.customers.find((row) => row.id === customerId);
    if (!customer || !quote) return;
    const nextQuoteData = quoteDataWithDefaults({
      ...qd,
      buyer_name: customer.name,
      buyer_address_line1: customer.address_line1,
      buyer_address_line2: customer.address_line2,
      buyer_city: customer.city,
      buyer_state: customer.state,
      buyer_pin_code: customer.pin_code,
      buyer_country: customer.country,
      attention: customer.contact_name,
      designation: customer.designation,
      email: customer.email,
      contact_no: customer.phone,
      gst_no: customer.gst_no,
      currency: customer.default_currency || getString(qd.currency) || "INR",
      payment_terms: customer.payment_terms || qd.payment_terms,
      delivery: customer.delivery_terms || qd.delivery,
    });
    updateQuoteDraft({
      customer: customer.name,
      quote_data: nextQuoteData,
      stage_meta: { ...(quote.stage_meta ?? {}), customer_master_id: customer.id, country: customer.country || quote.stage_meta?.country, city: customer.city || quote.stage_meta?.city },
    });
  }

  function salesRepQuoteData(user: (typeof salesRepUsers)[number]) {
    return {
      ...qd,
      sales_rep_user_id: user.id,
      rep_name: user.name,
      rep_email: user.email,
      rep_designation: user.designation || roleLabels[user.role],
      rep_contact: user.contact || "",
    };
  }

  function selectSalesRep(userId: string) {
    if (!canEditQuotation) return;
    if (userId === CUSTOM_SALES_REP_VALUE) return;
    const user = salesRepUsers.find((row) => row.id === userId);
    if (!user) return;
    const next = salesRepQuoteData(user);
    setQuote((current) => (current ? { ...current, quote_data: next, quote_no: effectiveQuoteNo } : current));
    setHasUnsavedLocalEdits(true);
  }

  const unitPrices = React.useMemo(() => Array.isArray(qd.unit_prices) ? qd.unit_prices.map((value) => toNumber(value)) : [], [qd.unit_prices]);
  const costPrices = React.useMemo(() => Array.isArray(qd.cost_prices) ? qd.cost_prices.map((value) => toNumber(value)) : [], [qd.cost_prices]);
  const targetMargins = React.useMemo(() => Array.isArray(qd.target_margins_pct) ? qd.target_margins_pct.map((value) => toNumber(value, 0)) : [], [qd.target_margins_pct]);
  const currency = getString(qd.currency) || "INR";
  const fxRate = toNumber(qd.fx_rate, defaultFx[currency] ?? 1);
  const discountPct = toNumber(qd.discount_pct);
  const gstPct = currency === "INR" ? toNumber(qd.gst_pct, 18) : 0;
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
    }),
    [costPrices, currency, discountPct, fxRate, gstPct, items, qualityReport.risks, targetMargins, unitPrices],
  );
  const subtotal = pricingSummary.subtotal;
  const discount = pricingSummary.discount;
  const gst = pricingSummary.gst;
  const grandTotal = pricingSummary.grandTotal;
  const totalQuantity = pricingSummary.lines.reduce((sum, line) => sum + line.quantity, 0);
  const totalQuantityLabel = Number.isInteger(totalQuantity) ? `${totalQuantity}` : totalQuantity.toFixed(2);
  const readyCount = items.filter((item) => item.status === "ready").length;
  const checkCount = items.filter((item) => item.status === "check").length;
  const missingCount = items.filter((item) => item.status === "missing").length;
  const actionCount = checkCount + missingCount;
  const readiness = items.length ? Math.round((readyCount / items.length) * 100) : 0;
  const approval = approvalState(quote);
  const canApprove = canRole(currentUser.role, "approve_quotes", accessSettings);
  const canExportQuotes = canRole(currentUser.role, "export_quotes", accessSettings);
  const approvalAllowsExport = approval.status === "approved" || !pricingSummary.approvalRequired;
  const canExportFinal = currentUser.role === "admin" || (canExportQuotes && approvalAllowsExport);
  const materialPlanStatus = getString(quote?.stage_meta?.material_plan_status || (quote?.stage_meta?.material_plan_finished_at ? "finished" : materialPlan ? "draft" : ""));
  const materialPhase2Finished = materialPlanStatus === "finished";
  const outlookThread = outlookThreadFromMeta(quote?.stage_meta);
  const quotationStage = quotationStageFromData(qd, quote);
  const quotationStageIndex = QUOTATION_STAGE_INDEX.get(quotationStage) ?? 0;
  const quotationStageMeta = QUOTATION_STAGES[quotationStageIndex] ?? QUOTATION_STAGES[0];
  const quotationChecklist = quotationStageChecklist(quotationStage, approval, pricingSummary, qualityReport.score);
  const visibleQuotes = quotes.filter((row) => {
    if (isPoSection) {
      if (!PO_STAGES.has(row.stage)) return false;
    } else if (isFinalSection) {
      if (!FINAL_STAGES.has(row.stage)) return false;
    } else if (isMaterialSection) {
      if (row.stage_meta?.material_planning_enabled !== true) return false;
    } else if (!DRAFT_STAGES.has(row.stage)) {
      return false;
    }
    if (queueFilter === "my_work" && row.stage_meta?.owner_id !== currentUser.id && row.stage_meta?.owner_name !== currentUser.name && row.stage_meta?.owner_email !== currentUser.email) return false;
    if (queueFilter === "due_today" && quoteDueState(row) !== "today") return false;
    if (queueFilter === "delayed" && quoteDueState(row) !== "delayed") return false;
    if (queueFilter === "clarification" && !quoteHasClarification(row)) return false;
    if (queueFilter === "high_risk" && !quoteIsHighRisk(row)) return false;
    if (queueFilter === "high_value" && !quoteIsHighValue(row)) return false;
    if (queueFilter.startsWith("enquiry_stage:") && enquiryStageFromQuote(row) !== queueFilter.slice("enquiry_stage:".length)) return false;
    if (queueFilter.startsWith("stage:") && row.stage !== queueFilter.slice("stage:".length)) return false;
    const term = search.toLowerCase();
    return !term || row.customer.toLowerCase().includes(term) || row.project_ref.toLowerCase().includes(term) || row.quote_no.toLowerCase().includes(term);
  });

  async function openQuote(row: Quote) {
    try {
      if (quote?.id !== row.id && !canDiscardUnsavedEdits("Open another enquiry")) return;
      invalidateMaterialPlan();
      const active = await getQuote(row.id);
      setQuote(active);
      rememberRecentQuote(active);
      setSelectedRows(new Set());
      setRfiText("");
      router.push(`${sectionBasePath}?quote=${row.id}`);
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
    setEditingCell(null);
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

  function focusGridCell(rowIndex: number, colIndex: number, edit = false) {
    window.requestAnimationFrame(() => {
      const cell = draftGridRef.current?.querySelector<HTMLElement>(`[data-grid-row="${rowIndex}"][data-grid-col="${colIndex}"]`);
      if (edit) {
        const focusTarget = cell?.querySelector<HTMLElement>("input, textarea, button, [tabindex]");
        (focusTarget ?? cell)?.focus();
        if (focusTarget instanceof HTMLInputElement || focusTarget instanceof HTMLTextAreaElement) {
          focusTarget.select();
        }
        return;
      }
      cell?.focus();
    });
  }

  function isEditingGridCell(rowIndex: number, colIndex: number) {
    return editingCell?.rowIndex === rowIndex && editingCell.colIndex === colIndex;
  }

  function startEditingGridCell(rowIndex: number, colIndex: number) {
    const column = activeTableColumns[colIndex];
    if (!column || !isEditableGridColumn(column)) return false;
    setActiveCell({ rowIndex, colIndex });
    setSelectionAnchor({ rowIndex, colIndex });
    setSelectionFocus({ rowIndex, colIndex });
    setSelectedRows(new Set([rowIndex]));
    setEditingCell({ rowIndex, colIndex });
    focusGridCell(rowIndex, colIndex, true);
    return true;
  }

  function stopEditingGridCell(rowDelta = 0, colDelta = 0) {
    const currentCell = editingCell ?? activeCell;
    setEditingCell(null);
    if (!currentCell) return;
    if (rowDelta || colDelta) {
      moveActiveGridCell(rowDelta, colDelta, false);
      return;
    }
    focusGridCell(currentCell.rowIndex, currentCell.colIndex);
  }

  function toggleGridCheckbox(rowIndex: number, column: TableColumn) {
    const item = items[rowIndex];
    if (!item || column.kind !== "checkbox") return false;
    const checked = !(item.status === "regret" || item.regret === true);
    const next = [...items];
    next[rowIndex] = { ...item, regret: checked, status: checked ? "regret" : "check" };
    invalidateMaterialPlan();
    setQuote((current) => (current ? { ...current, items: next } : current));
    setHasUnsavedLocalEdits(true);
    return true;
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
    let appendedRows = 0;
    for (let rowOffset = 0; rowOffset < rowCount; rowOffset += 1) {
      let itemIndex = displayIndices[startPosition + rowOffset];
      if (itemIndex === undefined) {
        itemIndex = next.length;
        next.push(blankItem(itemIndex + 1));
        appendedRows += 1;
      }
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
    setUndoItems({ label: "Undo paste", items, local: true });
    invalidateMaterialPlan();
    setQuote((current) => (current ? { ...current, items: next } : current));
    setHasUnsavedLocalEdits(true);
    toast.success(`Pasted ${changed} cell${changed === 1 ? "" : "s"}${appendedRows ? ` and appended ${appendedRows} row${appendedRows === 1 ? "" : "s"}` : ""}`);
    return true;
  }

  function selectedGridRowIndices() {
    if (selectedRange) {
      return displayIndices.slice(selectedRange.minPosition, selectedRange.maxPosition + 1);
    }
    if (selectedIndices.length) return selectedIndices;
    return activeCell ? [activeCell.rowIndex] : [];
  }

  function insertBlankRowsAboveSelection() {
    const targetRows = selectedGridRowIndices();
    const insertAt = targetRows.length ? Math.min(...targetRows) : items.length;
    const rowCount = Math.max(1, targetRows.length);
    const next = [...items];
    next.splice(insertAt, 0, ...Array.from({ length: rowCount }, (_, index) => blankItem(insertAt + index + 1)));
    setUndoItems({ label: "Undo row insertion", items, local: true });
    invalidateMaterialPlan();
    setQuote((current) => current ? { ...current, items: renumber(next) } : current);
    setHasUnsavedLocalEdits(true);
    setSelectedRows(new Set(Array.from({ length: rowCount }, (_, index) => insertAt + index)));
    setActiveCell({ rowIndex: insertAt, colIndex: activeCell?.colIndex ?? 0 });
    setSelectionAnchor({ rowIndex: insertAt, colIndex: activeCell?.colIndex ?? 0 });
    setSelectionFocus({ rowIndex: insertAt, colIndex: activeCell?.colIndex ?? 0 });
    toast.success(`Inserted ${rowCount} blank row${rowCount === 1 ? "" : "s"}`);
  }

  function deleteGridSelectedRows() {
    const targetRows = selectedGridRowIndices();
    if (!targetRows.length) return false;
    if (!window.confirm(`Delete ${targetRows.length} selected item row(s)? You can undo this action.`)) return false;
    const selected = new Set(targetRows);
    setUndoItems({ label: "Restore deleted rows", items, local: true });
    invalidateMaterialPlan();
    setQuote((current) => current ? { ...current, items: renumber(items.filter((_, index) => !selected.has(index))) } : current);
    setHasUnsavedLocalEdits(true);
    setSelectedRows(new Set());
    setActiveCell(null);
    setSelectionAnchor(null);
    setSelectionFocus(null);
    return true;
  }

  function fillGridSelectionDown() {
    if (!selectedRange || selectedRange.maxPosition <= selectedRange.minPosition) return false;
    const sourceIndex = displayIndices[selectedRange.minPosition];
    if (sourceIndex === undefined || !items[sourceIndex]) return false;
    const next = [...items];
    let changed = 0;
    for (let position = selectedRange.minPosition + 1; position <= selectedRange.maxPosition; position += 1) {
      const rowIndex = displayIndices[position];
      if (rowIndex === undefined || !next[rowIndex]) continue;
      let row = next[rowIndex];
      for (let colIndex = selectedRange.minCol; colIndex <= selectedRange.maxCol; colIndex += 1) {
        const column = activeTableColumns[colIndex];
        if (!column || !isEditableGridColumn(column)) continue;
        row = setItemValue(row, column.field, columnValue(items[sourceIndex], column));
        changed += 1;
      }
      next[rowIndex] = row;
    }
    if (!changed) return false;
    setUndoItems({ label: "Undo fill down", items, local: true });
    invalidateMaterialPlan();
    setQuote((current) => current ? { ...current, items: next } : current);
    setHasUnsavedLocalEdits(true);
    toast.success(`Filled ${changed} cell${changed === 1 ? "" : "s"} down`);
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
    setUndoItems({ label: "Undo clear", items, local: true });
    invalidateMaterialPlan();
    setQuote((current) => (current ? { ...current, items: next } : current));
    setHasUnsavedLocalEdits(true);
    return true;
  }

  function handleGridKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!canEditLineItems) return;
    if (tableMode !== "spreadsheet") return;
    const target = event.target as HTMLElement | null;
    const targetTag = target?.tagName;
    const inCellEditor = Boolean(editingCell) || targetTag === "INPUT" || targetTag === "TEXTAREA" || targetTag === "BUTTON";
    if (editingCell) {
      if (event.key === "Escape") {
        event.preventDefault();
        stopEditingGridCell();
        return;
      }
      if (event.key === "Tab") {
        event.preventDefault();
        stopEditingGridCell(0, event.shiftKey ? -1 : 1);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        stopEditingGridCell(event.shiftKey ? -1 : 1, 0);
        return;
      }
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.shiftKey && (event.key === "+" || event.key === "=")) {
      event.preventDefault();
      insertBlankRowsAboveSelection();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "-") {
      if (deleteGridSelectedRows()) event.preventDefault();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") {
      if (fillGridSelectionDown()) event.preventDefault();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && undoItems) {
      event.preventDefault();
      void restoreUndoItems();
      return;
    }
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
    if ((event.key === "Delete" || event.key === "Backspace") && selectedCellCount >= 1) {
      if (clearSelectedGridCells()) event.preventDefault();
      return;
    }
    if (event.key === "F2" && activeCell) {
      event.preventDefault();
      startEditingGridCell(activeCell.rowIndex, activeCell.colIndex);
      return;
    }
    if (event.key === " " && activeCell && activeGridColumn?.kind === "checkbox") {
      event.preventDefault();
      toggleGridCheckbox(activeCell.rowIndex, activeGridColumn);
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
    if (event.key === "Enter") {
      event.preventDefault();
      moveActiveGridCell(event.shiftKey ? -1 : 1, 0, false);
      return;
    }
    if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.length === 1 && activeCell && activeGridColumn && isEditableGridColumn(activeGridColumn) && activeGridColumn.kind !== "select" && activeGridColumn.kind !== "checkbox") {
      event.preventDefault();
      updateItem(activeCell.rowIndex, activeGridColumn.field, event.key);
      setEditingCell(activeCell);
      focusGridCell(activeCell.rowIndex, activeCell.colIndex, true);
      return;
    }
    if (inCellEditor || event.ctrlKey || event.metaKey || event.altKey) return;
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

  function renderGridCell(index: number, item: GasketItem, column: TableColumn, colIndex: number) {
    const rawValue = item[column.field];
    const validation = validateItemField(item, column.field);
    const cellClass = column.field === "confidence" ? confidenceClass(rawValue) : validationClass(validation?.severity);
    const wrapLongCell = !compactRows && ["flags", "raw_description", "ggpl_description"].includes(column.field);
    const inputClass = tableMode === "spreadsheet"
      ? "h-8 w-full min-w-0 rounded-none border-0 bg-white px-2 py-1 text-xs shadow-none focus-visible:ring-1 focus-visible:ring-primary dark:bg-background"
      : GRID_INPUT_CLASS;
    const textareaClass = tableMode === "spreadsheet"
      ? `${wrapLongCell ? "min-h-16 resize-y" : "h-8 resize-none"} w-full min-w-0 rounded-none border-0 bg-white px-2 py-1 text-xs shadow-none outline-none focus:ring-1 focus:ring-primary dark:bg-background`
      : GRID_TEXTAREA_CLASS;
    const displayClass = `flex min-w-0 px-2 py-1 text-xs ${wrapLongCell ? "min-h-16 items-start whitespace-normal break-words" : "h-8 items-center overflow-hidden"} ${cellClass}`;
    if (!canEditLineItems) {
      if (column.field === "status") {
        const status = getString(item.status) || "missing";
        return (
          <div className={`${displayClass} gap-1.5 bg-muted/30 text-muted-foreground`} title={validation?.message || status}>
            {statusIcon[status]}
            <span className="truncate">{STATUS_LABELS[status as keyof typeof STATUS_LABELS] ?? status}</span>
          </div>
        );
      }
      const displayValue = column.field === "flags" ? notesFor(item) : columnValue(item, column);
      return (
        <div className={`${displayClass} bg-muted/30 text-muted-foreground`} title={validation?.message || displayValue}>
          <span className={wrapLongCell ? "whitespace-normal break-words" : "truncate"}>{displayValue}</span>
        </div>
      );
    }
    if (column.field === "status") {
      return (
        <Select value={getString(rawValue) || "missing"} onValueChange={(value) => updateItem(index, "status", value)}>
          <SelectTrigger className={`${tableMode === "spreadsheet" ? SHEET_SELECT_CLASS : inputClass} ${cellClass} w-full min-w-28 justify-between`} title={validation?.message || "Set row status"}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((value) => <SelectItem key={value} value={value}>{STATUS_LABELS[value]}</SelectItem>)}
          </SelectContent>
        </Select>
      );
    }
    if (tableMode === "spreadsheet" && !isEditingGridCell(index, colIndex)) {
      if (column.field === "status") {
        return (
          <div className={`${displayClass} gap-1.5`} title={getString(item.status)}>
            {statusIcon[getString(item.status)]}
            <span className="truncate capitalize">{getString(item.status)}</span>
          </div>
        );
      }
      if (column.kind === "checkbox") {
        const checked = item.status === "regret" || item.regret === true;
        return (
          <div className={`${displayClass} justify-center font-mono`} title={checked ? "TRUE" : "FALSE"}>
            {checked ? "TRUE" : "FALSE"}
          </div>
        );
      }
      if (column.field === "status") {
        return (
          <div className={`${displayClass} gap-1.5`} title={getString(item.status)}>
            {statusIcon[getString(item.status)]}
            <span className="truncate capitalize">{getString(item.status)}</span>
          </div>
        );
      }
      const displayValue = column.field === "flags" ? notesFor(item) : columnValue(item, column);
      return (
        <div className={`${displayClass} ${!isEditableGridColumn(column) ? "bg-muted/30 text-muted-foreground" : ""}`} title={validation?.message || displayValue}>
          <span className={wrapLongCell ? "whitespace-normal break-words" : "truncate"}>{displayValue}</span>
        </div>
      );
    }
    if (column.field === "status" && tableMode === "spreadsheet") {
      return (
        <Select value={getString(rawValue) || "missing"} onValueChange={(value) => updateItem(index, "status", value)}>
          <SelectTrigger className={`${SHEET_SELECT_CLASS} w-full min-w-0 justify-between ${cellClass}`} title={validation?.message}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((value) => <SelectItem key={value} value={value}>{STATUS_LABELS[value]}</SelectItem>)}
          </SelectContent>
        </Select>
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
              setHasUnsavedLocalEdits(true);
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

  async function generateMaterialBreakdown() {
    if (!canRunMaterialPhase1) {
      toast.error("Sales users cannot change material planning.");
      return;
    }
    if (!quote) return;
    const nextBreakdown = buildMaterialBreakdown(items);
    setMaterialBreakdown(nextBreakdown);
    setMaterialInputs([]);
    setMaterialPlan(null);
    await savePatch(
      {
        stage_meta: {
          ...(quote.stage_meta ?? {}),
          material_breakdown: nextBreakdown,
          material_inputs: [],
          material_breakdown_updated_at: new Date().toISOString(),
          material_plan: null,
          material_plan_status: "",
        },
      } as Partial<Quote>,
      "Material breakdown saved",
    );
  }

  async function startManualMaterialPlan() {
    if (!canEditMaterialPhase2) {
      toast.error("Only material planner users can create the purchase plan.");
      return;
    }
    if (!quote) return;
    const nextBreakdown = materialBreakdown?.length ? materialBreakdown : buildMaterialBreakdown(items);
    const nextPlan = createManualMaterialPlan(materialPhase2RowsFromBreakdown(nextBreakdown), { ...materialConfig, material_inputs: [] });
    setMaterialBreakdown(nextBreakdown);
    setMaterialInputs([]);
    setMaterialPlan(nextPlan);
    await savePatch(
      {
        stage_meta: {
          ...(quote.stage_meta ?? {}),
          material_breakdown: nextBreakdown,
          material_inputs: [],
          material_breakdown_updated_at: quote.stage_meta?.material_breakdown_updated_at ?? new Date().toISOString(),
          material_plan: nextPlan,
          material_plan_status: "draft",
          material_plan_started_at: quote.stage_meta?.material_plan_started_at ?? new Date().toISOString(),
          material_plan_started_by: quote.stage_meta?.material_plan_started_by ?? currentUser.id,
          material_plan_updated_at: new Date().toISOString(),
        },
      } as Partial<Quote>,
      "Purchase plan started",
    );
  }

  async function saveMaterialPlan(plan: MaterialPlan | null = materialPlan) {
    if (plan && !canEditMaterialPhase2) {
      toast.error("Only material planner users can save the purchase plan.");
      return;
    }
    if (!plan && !canRunMaterialPhase1) {
      toast.error("Sales users cannot change material planning.");
      return;
    }
    if (!quote && !plan) return;
    if (!quote) return;
    await savePatch(
      {
        stage_meta: {
          ...(quote.stage_meta ?? {}),
          material_breakdown: materialBreakdown ?? [],
          material_inputs: materialInputs,
          material_plan: plan,
          material_plan_status: plan ? materialPlanStatus || "draft" : "",
          material_plan_updated_at: new Date().toISOString(),
        },
      } as Partial<Quote>,
      "Material plan saved",
    );
  }

  async function clearMaterialPlan() {
    if (!canEditMaterialPhase2) {
      toast.error("Sales users cannot clear material planning.");
      return;
    }
    if (!quote) return;
    const nextStageMeta = { ...(quote.stage_meta ?? {}) };
    delete nextStageMeta.material_breakdown;
    delete nextStageMeta.material_inputs;
    delete nextStageMeta.material_breakdown_updated_at;
    delete nextStageMeta.material_plan;
    delete nextStageMeta.material_plan_updated_at;
    delete nextStageMeta.material_plan_status;
    delete nextStageMeta.material_plan_started_at;
    delete nextStageMeta.material_plan_started_by;
    delete nextStageMeta.material_plan_submitted_at;
    delete nextStageMeta.material_plan_submitted_by;
    delete nextStageMeta.material_plan_finished_at;
    delete nextStageMeta.material_plan_finished_by;
    setMaterialBreakdown(null);
    setMaterialInputs([]);
    setMaterialPlan(null);
    await savePatch({ stage_meta: nextStageMeta } as Partial<Quote>, "Material plan cleared");
  }

  function updateBreakdownRow(index: number, patch: Partial<MaterialBreakdownRow>) {
    if (!canEditWorkflow) return;
    setMaterialBreakdown((current) => {
      if (!current) return current;
      return current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row));
    });
    setMaterialPlan(null);
    setHasUnsavedLocalEdits(true);
  }

  function updatePlanRow(index: number, patch: Partial<MaterialPlan["rows"][number]>) {
    if (!canEditMaterialPhase2 || materialPhase2Finished) return;
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
      return materialPlanWithRows(current, nextRows);
    });
    setHasUnsavedLocalEdits(true);
  }

  function addMaterialPhase2Row() {
    if (!canEditMaterialPhase2 || materialPhase2Finished) return;
    setMaterialPlan((current) => {
      const base = current ?? createManualMaterialPlan([], { ...materialConfig, material_inputs: [] });
      return materialPlanWithRows(base, [...base.rows, blankMaterialPhase2Row(base.rows.length + 1)]);
    });
    setHasUnsavedLocalEdits(true);
  }

  function deleteMaterialPhase2Row(index: number) {
    if (!canEditMaterialPhase2 || materialPhase2Finished) return;
    setMaterialPlan((current) => {
      if (!current) return current;
      return materialPlanWithRows(current, current.rows.filter((_, rowIndex) => rowIndex !== index));
    });
    setHasUnsavedLocalEdits(true);
  }

  async function submitMaterialPlan() {
    if (!quote || !materialPlan || !canEditMaterialPhase2) return;
    const now = new Date().toISOString();
    await savePatch(
      {
        stage_meta: {
          ...(quote.stage_meta ?? {}),
          material_breakdown: materialBreakdown ?? [],
          material_inputs: [],
          material_plan: materialPlan,
          material_plan_status: "submitted",
          material_plan_submitted_at: now,
          material_plan_submitted_by: currentUser.id,
          material_plan_updated_at: now,
        },
      } as Partial<Quote>,
      "Purchase plan submitted",
    );
  }

  async function finishMaterialPlan() {
    if (!quote || !materialPlan || !canEditMaterialPhase2) return;
    const now = new Date().toISOString();
    const finishedPlan = materialPlanWithRows(materialPlan, materialPlan.rows.map((row) => ({ ...row, reviewed: true })));
    setMaterialPlan(finishedPlan);
    await savePatch(
      {
        stage_meta: {
          ...(quote.stage_meta ?? {}),
          material_breakdown: materialBreakdown ?? [],
          material_inputs: [],
          material_plan: finishedPlan,
          material_plan_status: "finished",
          material_plan_finished_at: now,
          material_plan_finished_by: currentUser.id,
          material_plan_updated_at: now,
        },
      } as Partial<Quote>,
      "Material plan finished",
    );
  }

  function formatStockSize(row: MaterialPlan["rows"][number]) {
    if (row.purchase_uom === "NOS" && row.width_mm === null && row.length_mm === null && row.thickness_mm === null) {
      return "Kit/set count";
    }
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
    if (row.reqd_qty_kg !== null) return `${row.reqd_qty_kg.toFixed(2)} ${row.purchase_uom?.toLowerCase() || "kg"}`;
    return "Needs dimensions";
  }

  function exportFileStem(suffix: string) {
    const base = getString(quote?.quote_no || quote?.customer || quote?.id || "material-plan")
      .replace(/[^\w.-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80) || "material-plan";
    return `${base}-${suffix}`;
  }

  function encodeExportCell(value: unknown, delimiter: "," | "\t") {
    const text = value === true ? "Yes" : value === false ? "No" : getString(value);
    if (delimiter === "\t") return text.replace(/\t/g, " ").replace(/\r?\n/g, " ");
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function rowsToText(rows: unknown[][], delimiter: "," | "\t") {
    return rows.map((row) => row.map((cell) => encodeExportCell(cell, delimiter)).join(delimiter)).join("\r\n");
  }

  function downloadRowsAsCsv(filename: string, rows: unknown[][]) {
    if (rows.length <= 1) {
      toast.error("No rows to export");
      return;
    }
    const blob = new Blob([`\uFEFF${rowsToText(rows, ",")}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function copyRowsToClipboard(label: string, rows: unknown[][]) {
    if (rows.length <= 1) {
      toast.error("No rows to copy");
      return;
    }
    try {
      await navigator.clipboard.writeText(rowsToText(rows, "\t"));
      toast.success(`${label} copied`);
    } catch {
      toast.error("Could not copy table data");
    }
  }

  function phase1ExportRows() {
    return [
      ["Review", "SL", "Gasket type", "Size (inch)", "Pressure rating", "Thickness", "Primary material", "Secondary / inner", "Outer / hardware", "Filler / facing / seals", "Qty", "UOM", "Series", "Remarks", "OD mm", "ID mm", "Source rows"],
      ...(materialBreakdown ?? []).map((row) => [
        row.reviewed,
        row.line_no,
        row.gasket_type,
        row.size_inch,
        row.pressure_rating,
        row.thickness,
        row.winding,
        row.inner_ring,
        row.outer_ring,
        row.filler,
        row.qty,
        row.uom,
        row.series,
        row.remarks,
        row.od_mm ?? "",
        row.id_mm ?? "",
        row.source_rows,
      ]),
    ];
  }

  function phase2ExportRows() {
    return [
      ["Review", "SL.NO.", "Stock type", "Stock size", "Purchase UOM", "Planned qty", "Est. purchase qty", "Available", "Reserved", "Shortage", "Suggested purchase", "Vendor", "Lead days", "Material cost", "Priority", "Source rows", "Notes", "Planner review"],
      ...(materialPlan?.rows ?? []).map((row) => [
        row.reviewed,
        row.sl_no,
        row.type,
        formatStockSize(row),
        row.purchase_uom,
        formatPlanQuantity(row),
        row.reqd_qty_sheets ?? row.reqd_qty_kg ?? "Needs dimensions",
        row.available_qty,
        row.reserved_qty,
        row.shortage_qty,
        row.suggested_purchase_qty,
        row.preferred_vendor,
        row.lead_time_days,
        row.estimated_material_cost,
        row.production_priority,
        row.source_count,
        row.notes,
        row.planner_notes,
      ]),
    ];
  }

  if (!quote) {
    return (
      <div className="space-y-3">
        <Card>
          <CardHeader className="gap-2 border-b px-3 py-2">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex min-w-0 items-center gap-2">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-background">
                  {isPoSection ? <ShoppingCart className="h-4 w-4" /> : isFinalSection ? <FileSpreadsheet className="h-4 w-4" /> : isMaterialSection ? <Layers3 className="h-4 w-4" /> : <Inbox className="h-4 w-4" />}
                </div>
                <div className="min-w-0">
                  <CardTitle className="text-base">{isPoSection ? "Purchase orders" : isFinalSection ? "Quotations" : isMaterialSection ? "Material planning" : "Enquiries"}</CardTitle>
                  <div className="text-xs text-muted-foreground">{visibleQuotes.length} workspace{visibleQuotes.length === 1 ? "" : "s"}</div>
                </div>
              </div>
              <div className="flex flex-col gap-2 md:flex-row md:items-center lg:justify-end">
                <div className="relative w-full md:w-72">
                  <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="h-9 pl-9"
                    placeholder={isPoSection ? "Search customer, project, PO" : isFinalSection ? "Search customer, project, quote no" : "Search customer, project, enquiry no"}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </div>
                <Select value={queueFilter} onValueChange={setQueueFilter}>
                  <SelectTrigger className="h-9 w-full md:w-44"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All work</SelectItem>
                    <SelectItem value="my_work">My work</SelectItem>
                    <SelectItem value="due_today">Due today</SelectItem>
                    <SelectItem value="delayed">Delayed</SelectItem>
                    <SelectItem value="clarification">Clarification</SelectItem>
                    <SelectItem value="high_risk">High risk</SelectItem>
                    {(isFinalSection || isPoSection) && <SelectItem value="high_value">High value</SelectItem>}
                    {!isFinalSection && !isPoSection && ENQUIRY_STAGES.map((stage) => (
                      <SelectItem key={stage.id} value={`enquiry_stage:${stage.id}`}>Enquiry: {stage.label}</SelectItem>
                    ))}
                    {!isFinalSection && !isPoSection && (
                      <>
                        <SelectItem value="stage:initial">Stage: enquiry</SelectItem>
                        <SelectItem value="stage:review">Stage: review</SelectItem>
                        <SelectItem value="stage:quote_prep">Stage: quote prep</SelectItem>
                      </>
                    )}
                    {isFinalSection && (
                      <>
                        <SelectItem value="stage:quote_prep">Workflow: quote prep</SelectItem>
                        <SelectItem value="stage:repricing">Workflow: repricing</SelectItem>
                        <SelectItem value="stage:sent">Workflow: sent</SelectItem>
                        <SelectItem value="stage:po">Workflow: PO</SelectItem>
                      </>
                    )}
                    {isPoSection && <SelectItem value="stage:po">Workflow: PO</SelectItem>}
                  </SelectContent>
                </Select>
                <div className="flex gap-1.5">
                  <Button className="h-9" variant="secondary" onClick={() => refreshQuotes().catch((error) => toast.error(error.message))} aria-label="Refresh quotes">
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-auto">
                <Table className="min-w-[940px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[34%]">{isPoSection ? "Order" : isFinalSection ? "Quotation" : "Enquiry"}</TableHead>
                      <TableHead className="w-40">{isFinalSection || isPoSection ? "Workflow" : "Stage"}</TableHead>
                      <TableHead className="w-56">Review</TableHead>
                      <TableHead className="w-48">{isFinalSection || isPoSection ? "Items / value" : "Items / next action"}</TableHead>
                      <TableHead className="w-28">Updated</TableHead>
                      <TableHead className="w-24 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleQuotes.map((row) => (
                    <QuoteSummaryRow key={row.id} quote={row} section={section} appUsers={appUsers} onOpen={openQuote} onDelete={removeQuote} onMetaChange={updateQueueMeta} canDelete={canEditQuote} />
                  ))}
                  {!visibleQuotes.length && (
                    <TableRow>
                      <TableCell colSpan={6} className="py-14 text-center">
                        <div className="mx-auto flex max-w-sm flex-col items-center gap-3 text-sm text-muted-foreground">
                          <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-background">
                            {isPoSection ? <ShoppingCart className="h-5 w-5" /> : isFinalSection ? <FileSpreadsheet className="h-5 w-5" /> : isMaterialSection ? <Layers3 className="h-5 w-5" /> : <Inbox className="h-5 w-5" />}
                          </div>
                          <div>{isPoSection ? "No accepted quotations have been moved to PO yet." : isFinalSection ? "No quotes are ready for quotation yet." : isMaterialSection ? "No enquiries are ready for material planning." : "No enquiries match the current search."}</div>
                          {isDraftSection && canEditQuote && (
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
    <div className="space-y-4">
      {!isQuotationSection && <div className="rounded-md border bg-card/95 p-2 lg:sticky lg:top-16 lg:z-30">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={quote.stage === "po" ? "secondary" : "outline"}>{stageLabel(quote.stage)}</Badge>
              {!isQuotationSection && <Badge variant="outline">{enquiryStageLabel(quote)}</Badge>}
              {revisionLabel(quote) && <Badge variant="outline">{revisionLabel(quote)}</Badge>}
              {saving && <span className="inline-flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving</span>}
              {!saving && hasUnsavedLocalEdits && <Badge variant="warning">Unsaved edits</Badge>}
              {!saving && !hasUnsavedLocalEdits && <Badge variant="secondary">Saved</Badge>}
              {!isQuotationSection && !enquiryMarketType && <Badge variant="warning">Export/domestic required</Badge>}
            </div>
            <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-0.5">
              <h2 className="font-mono text-base font-semibold tracking-normal text-primary">{quote.quote_no || "enq-pending"}</h2>
              <div className="min-w-0 truncate text-xs text-muted-foreground">
                {[quote.customer, quote.project_ref].filter(Boolean).join(" / ") || "No customer or project reference"}
              </div>
              {!isQuotationSection && (
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span>Owner: {selectedEnquiryOwnerLabel}</span>
                  <span>Due: {getString(quote.stage_meta?.due_date) || "Not set"}</span>
                </div>
              )}
            </div>
            {!isQuotationSection && (
              <div className="flex flex-wrap items-center gap-1.5">
                <CompactMetric icon={<FileText className="h-3.5 w-3.5" />} label="Items" value={items.length} />
                <CompactMetric className="hidden lg:inline-flex" icon={<FileSpreadsheet className="h-3.5 w-3.5" />} label="Total qty" value={totalQuantityLabel} tone="ready" />
                <CompactMetric
                  className="hidden lg:inline-flex"
                  icon={<ShieldCheck className="h-3.5 w-3.5" />}
                  label="RFQ"
                  value={`${qualityReport.score}%`}
                  tone={qualityReport.score >= 80 ? "ready" : qualityReport.score >= 60 ? "check" : "missing"}
                />
                <CompactMetric className="hidden lg:inline-flex" icon={<CheckCircle2 className="h-3.5 w-3.5" />} label="Ready" value={readyCount} tone="ready" />
                <CompactMetric icon={<AlertCircle className="h-3.5 w-3.5" />} label="Review" value={checkCount} tone={checkCount ? "check" : "neutral"} />
                <CompactMetric
                  className="hidden lg:inline-flex"
                  icon={<Ban className="h-3.5 w-3.5" />}
                  label="Risk"
                  value={qualityReport.risks.length}
                  tone={qualityReport.risks.some((risk) => risk.severity === "high") ? "missing" : qualityReport.risks.length ? "check" : "ready"}
                />
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5 lg:shrink-0 lg:justify-end">
            <Button variant="secondary" size="sm" onClick={clearWorkspace}>
              <RotateCcw className="h-4 w-4" />
              Back to list
            </Button>
            {isDraftSection && canEditQuote && (
              <>
                <Button variant="secondary" size="sm" className="hidden lg:inline-flex" onClick={createRevision}>
                  <RefreshCw className="h-4 w-4" />
                  Revision
                </Button>
                <Button size="sm" onClick={() => {
                  if (items.length) {
                    void openQuotationScreen();
                    return;
                  }
                  setIntakeCollapsed(false);
                  window.requestAnimationFrame(() => document.getElementById("enquiry-intake")?.scrollIntoView({ behavior: "smooth", block: "start" }));
                }}>
                  <ArrowRight className="h-4 w-4" />
                  {items.length ? "Continue to quotation" : "Add enquiry items"}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>}

      <div className={isQuotationSection ? "hidden" : "border bg-card"}>
        {!isQuotationSection && <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{quote.customer || "Customer not selected"}</span>
              {!quote.customer || !enquiryMarketType || !selectedEnquiryOwnerId ? <Badge variant="warning">Setup incomplete</Badge> : <Badge variant="secondary">Context ready</Badge>}
            </div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {[enquiryMarketType || "Quote type needed", selectedEnquiryOwnerLabel, getString(quote.project_ref) || "No project reference"].join(" / ")}
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Button variant="secondary" size="sm" onClick={() => setEnquirySetupOpen(true)}>
              <SlidersHorizontal className="h-4 w-4" />
              Edit setup
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setIntakeCollapsed(false)}>
              <Plus className="h-4 w-4" />
              Add items
            </Button>
          </div>
        </div>}
        <Dialog open={enquirySetupOpen} onOpenChange={setEnquirySetupOpen}>
          <DialogContent className="flex max-h-[90vh] max-w-6xl flex-col overflow-hidden">
            <DialogHeader>
              <DialogTitle>Enquiry setup</DialogTitle>
              <DialogDescription>Update customer context, ownership, quote type, and optional Outlook details.</DialogDescription>
            </DialogHeader>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        <div>
          <details className="rounded-md border bg-background p-2.5" open={Boolean(outlookThread)}>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium">
              <span className="inline-flex items-center gap-2"><Mail className="h-4 w-4" />Outlook thread</span>
              <Badge variant={outlookThread ? "secondary" : "outline"}>{outlookThread ? "Linked" : "Not linked"}</Badge>
            </summary>
            <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
              <Field
                label="Paste Outlook email link or message ID"
                value={outlookQuickInput}
                onChange={setOutlookQuickInput}
                disabled={!canAddDetails}
              />
              <div className="flex flex-wrap gap-2">
                <Button onClick={connectOutlookThread} disabled={!canAddDetails || outlookLoading || !outlookQuickInput.trim()}>
                  {outlookLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                  Connect
                </Button>
                <Button variant="secondary" onClick={() => saveOutlookThread()} disabled={!canAddDetails || (!outlookDraft.conversation_id && !outlookDraft.message_id && !outlookDraft.web_link)}>
                  <Mail className="h-4 w-4" />
                  Link thread
                </Button>
              </div>
            </div>
            {outlookThread && (
              <div className="mt-3 grid gap-2 rounded-md border bg-muted/30 p-3 text-sm md:grid-cols-3">
                <div className="min-w-0">
                  <div className="text-xs text-muted-foreground">Subject</div>
                  <div className="truncate font-medium">{outlookThread.subject || "Outlook conversation"}</div>
                </div>
                <div className="min-w-0">
                  <div className="text-xs text-muted-foreground">From</div>
                  <div className="truncate">{outlookThread.from_email || outlookThread.from_name || "-"}</div>
                </div>
                <div className="min-w-0">
                  <div className="text-xs text-muted-foreground">Linked</div>
                  <div className="truncate">{outlookThread.linked_at ? new Date(outlookThread.linked_at).toLocaleString("en-GB") : "-"}</div>
                </div>
              </div>
            )}
            <details className="mt-3 rounded-md border p-3">
              <summary className="cursor-pointer text-sm font-medium">Advanced Outlook details</summary>
              <div className="mt-3 grid gap-3 lg:grid-cols-3">
                <Field
                  label="Mailbox"
                  value={outlookDraft.mailbox_user}
                  onChange={(value) => setOutlookDraft((current) => ({ ...current, mailbox_user: value }))}
                  disabled={!canAddDetails}
                />
                <Field
                  label="Message ID"
                  value={outlookDraft.message_id}
                  onChange={(value) => setOutlookDraft((current) => ({ ...current, message_id: value }))}
                  disabled={!canAddDetails}
                />
                <Field
                  label="Conversation ID"
                  value={outlookDraft.conversation_id}
                  onChange={(value) => setOutlookDraft((current) => ({ ...current, conversation_id: value }))}
                  disabled={!canAddDetails}
                />
                <Field
                  label="Internet message ID"
                  value={outlookDraft.internet_message_id}
                  onChange={(value) => setOutlookDraft((current) => ({ ...current, internet_message_id: value }))}
                  disabled={!canAddDetails}
                />
                <Field
                  label="Outlook link"
                  value={outlookDraft.web_link}
                  onChange={(value) => setOutlookDraft((current) => ({ ...current, web_link: value }))}
                  disabled={!canAddDetails}
                />
                <Field
                  label="Subject"
                  value={outlookDraft.subject}
                  onChange={(value) => setOutlookDraft((current) => ({ ...current, subject: value }))}
                  disabled={!canAddDetails}
                />
                <Field
                  label="From"
                  value={outlookDraft.from_email || outlookDraft.from_name}
                  onChange={(value) => setOutlookDraft((current) => ({ ...current, from_email: value }))}
                  disabled={!canAddDetails}
                />
                <Field
                  label="Received"
                  value={outlookDraft.received_at}
                  onChange={(value) => setOutlookDraft((current) => ({ ...current, received_at: value }))}
                  disabled={!canAddDetails}
                />
              </div>
              <div className="mt-3">
                <Button variant="secondary" onClick={resolveOutlookThread} disabled={!canAddDetails || outlookLoading || !outlookDraft.message_id}>
                  {outlookLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Resolve message ID
                </Button>
              </div>
            </details>
            <div className="mt-3 flex flex-wrap gap-2">
              {outlookDraft.web_link && (
                <Button variant="secondary" asChild>
                  <a href={outlookDraft.web_link} target="_blank" rel="noreferrer">
                    <Mail className="h-4 w-4" />
                    Open Outlook
                  </a>
                </Button>
              )}
              <Button variant="secondary" onClick={loadOutlookThreadMessages} disabled={outlookLoading || !outlookDraft.conversation_id}>
                {outlookLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Refresh thread
              </Button>
              {outlookThread && canAddDetails && (
                <Button variant="secondary" onClick={unlinkOutlookThread}>
                  <X className="h-4 w-4" />
                  Unlink
                </Button>
              )}
            </div>
            {outlookMessages.length > 0 && (
              <div className="mt-3 overflow-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Subject</TableHead>
                      <TableHead>From</TableHead>
                      <TableHead>Received</TableHead>
                      <TableHead>Attachments</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {outlookMessages.map((message) => (
                      <TableRow key={message.message_id}>
                        <TableCell className="max-w-xl truncate">
                          {message.web_link ? <a className="text-primary hover:underline" href={message.web_link} target="_blank" rel="noreferrer">{message.subject || message.message_id}</a> : message.subject || message.message_id}
                        </TableCell>
                        <TableCell>{message.from_email || message.from_name}</TableCell>
                        <TableCell>{message.received_at ? new Date(message.received_at).toLocaleString("en-GB") : ""}</TableCell>
                        <TableCell>{message.has_attachments ? "Yes" : "No"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </details>
        </div>

        {!isQuotationSection && (
          <div className="mt-3 rounded-md border bg-background p-3">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_260px] md:items-center">
              <div>
                <div className="text-sm font-medium">Quote type</div>
                <div className="text-xs text-muted-foreground">Required before processing the enquiry or creating the final quotation.</div>
              </div>
              <div className="space-y-1.5">
                <Label>Export or domestic *</Label>
                <Select value={getString(quote.stage_meta?.market_type) || BLANK_SELECT_VALUE} onValueChange={(value) => updateQuoteDraft({ stage_meta: { ...(quote.stage_meta ?? {}), market_type: value === BLANK_SELECT_VALUE ? "" : value } })} disabled={!canAddDetails}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={BLANK_SELECT_VALUE}>Select</SelectItem>
                    <SelectItem value="export">Export</SelectItem>
                    <SelectItem value="domestic">Domestic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        )}

        {!isQuotationSection && (
          <div className="mt-3 grid gap-2 border-t pt-3 lg:grid-cols-2 2xl:grid-cols-4">
            <details className="rounded-md border bg-background p-2.5" open={!quote.customer || !quote.quote_no}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium">
                <span className="inline-flex items-center gap-2"><FileText className="h-4 w-4" />Enquiry details</span>
                <Badge variant={quote.customer && quote.quote_no ? "secondary" : "outline"}>{quote.customer && quote.quote_no ? "Saved context" : "Needs context"}</Badge>
              </summary>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="space-y-1.5">
                  <Label>Customer master</Label>
                  <Select value={getString(quote.stage_meta?.customer_master_id) || BLANK_SELECT_VALUE} onValueChange={(value) => { if (value !== BLANK_SELECT_VALUE) selectCustomer(value); }} disabled={!canAddDetails}>
                    <SelectTrigger><SelectValue placeholder="Select customer" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={BLANK_SELECT_VALUE}>Select customer</SelectItem>
                      {masterData.customers.filter((row) => row.active).map((customer) => <SelectItem key={customer.id} value={customer.id}>{customer.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <div className="text-xs text-muted-foreground">Selecting a customer fills buyer and contact details. Manual override remains available.</div>
                </div>
                <Field label="Customer name override" value={quote.customer} onChange={(value) => updateQuoteDraft({ customer: value })} disabled={!canAddDetails} />
                <Field label="Email subject" value={quote.custom_label} onChange={(value) => updateQuoteDraft({ custom_label: value })} disabled={!canAddDetails} />
                <Field label="Enq reference" value={quote.quote_no} onChange={(value) => updateQuoteDraft({ quote_no: value })} disabled={!canAddDetails} />
              </div>
            </details>

            <details className="rounded-md border bg-background p-2.5" open={currentUser.role === "sales"}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium">
                <span className="inline-flex items-center gap-2"><FileText className="h-4 w-4" />Project details</span>
                <Badge variant="outline">{quote.project_ref || getString(quote.stage_meta?.epc_name) ? "Added" : "Optional"}</Badge>
              </summary>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <Field label="Project name" value={quote.project_ref} onChange={(value) => updateQuoteDraft({ project_ref: value })} disabled={!canAddDetails} />
                <Field label="Country" value={getString(quote.stage_meta?.country)} onChange={(value) => updateQuoteDraft({ stage_meta: { ...(quote.stage_meta ?? {}), country: value } })} disabled={!canAddDetails} />
                <Field label="City" value={getString(quote.stage_meta?.city)} onChange={(value) => updateQuoteDraft({ stage_meta: { ...(quote.stage_meta ?? {}), city: value } })} disabled={!canAddDetails} />
                <div className="space-y-1.5">
                  <Label>EPC / project company</Label>
                  <Select value={getString(quote.stage_meta?.epc_name) || BLANK_SELECT_VALUE} onValueChange={(value) => updateQuoteDraft({ stage_meta: { ...(quote.stage_meta ?? {}), epc_name: value === BLANK_SELECT_VALUE ? "" : value } })} disabled={!canAddDetails}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value={BLANK_SELECT_VALUE}>Select</SelectItem>{masterData.epc_names.map((epc) => <SelectItem key={epc} value={epc}>{epc}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Bidding or firm</Label>
                  <Select value={getString(quote.stage_meta?.bid_type) || BLANK_SELECT_VALUE} onValueChange={(value) => updateQuoteDraft({ stage_meta: { ...(quote.stage_meta ?? {}), bid_type: value === BLANK_SELECT_VALUE ? "" : value } })} disabled={!canAddDetails}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={BLANK_SELECT_VALUE}>Select</SelectItem>
                      <SelectItem value="bidding">Bidding</SelectItem>
                      <SelectItem value="firm">Firm</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="mt-3 space-y-3">
                <Field
                  label="Optional internal notes"
                  value={getString(quote.stage_meta?.sales_notes)}
                  onChange={(value) => updateQuoteDraft({ stage_meta: { ...(quote.stage_meta ?? {}), sales_notes: value } })}
                  textarea
                  disabled={!canAddDetails}
                />
              </div>
            </details>

            <details className="rounded-md border bg-background p-2.5" open>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium">
                <span className="inline-flex items-center gap-2"><PanelRight className="h-4 w-4" />Assignment</span>
                <Badge variant="outline">{selectedEnquiryOwnerLabel}</Badge>
              </summary>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Sales rep</Label>
                  <Select
                    value={selectedEnquiryOwnerValue}
                    disabled={!canEditWorkflow}
                    onValueChange={(value) => {
                      if (value === CUSTOM_SALES_REP_VALUE) return;
                      const user = salesRepUsers.find((row) => row.id === value);
                      if (!user) return;
                      updateQueueMeta(quote, {
                        owner_id: user.id,
                        owner_name: user.name,
                        owner_email: user.email,
                        owner_role: user.role,
                      });
                      updateQuoteDraft({ quote_data: salesRepQuoteData(user) });
                    }}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {salesRepUsers.map((user) => (
                        <SelectItem key={user.id} value={user.id}>
                          {user.name} - {roleLabels[user.role]}
                        </SelectItem>
                      ))}
                      <SelectItem value={CUSTOM_SALES_REP_VALUE}>{selectedEnquiryOwnerLabel}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Due date</Label>
                  <Input
                    type="date"
                    value={getString(quote.stage_meta?.due_date)}
                    onChange={(event) => {
                      const stageMeta = { ...(quote.stage_meta ?? {}), due_date: event.target.value };
                      updateQuoteDraft({ stage_meta: stageMeta });
                    }}
                    onBlur={(event) => updateQueueMeta(quote, { due_date: event.target.value })}
                    disabled={!canEditWorkflow}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Enquiry stage</Label>
                  <Select value={currentEnquiryStage} onValueChange={(value) => updateQueueMeta(quote, { enquiry_stage: value as EnquiryStageId })} disabled={!canEditWorkflow}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {ENQUIRY_STAGES.map((stage) => (
                        <SelectItem key={stage.id} value={stage.id}>{stage.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Priority</Label>
                  <Select value={getString(quote.stage_meta?.priority) || "normal"} onValueChange={(value) => updateQueueMeta(quote, { priority: value })} disabled={!canEditWorkflow}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="urgent">Urgent</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="normal">Normal</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </details>

            <details className="rounded-md border bg-background p-2.5" open>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium">
                <span className="inline-flex items-center gap-2"><Users className="h-4 w-4" />With whom</span>
                <Badge variant="outline">{getString(quote.stage_meta?.with_whom) || "Unassigned"}</Badge>
              </summary>
              <div className="mt-3 space-y-1.5">
                <Label>Enquiry with</Label>
                <Select
                  value={getString(quote.stage_meta?.with_whom) || BLANK_SELECT_VALUE}
                  onValueChange={(value) => updateQueueMeta(quote, { with_whom: value === BLANK_SELECT_VALUE ? "" : value })}
                  disabled={!canEditWorkflow}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={BLANK_SELECT_VALUE}>Unassigned</SelectItem>
                    {accessSettings.with_whom_options.map((name) => (
                      <SelectItem key={name} value={name}>{name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </details>

            <details className="rounded-md border bg-background p-2.5" open>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium">
                <span className="inline-flex items-center gap-2"><FileText className="h-4 w-4" />Created by</span>
                <Badge variant="outline">{createdByRoleLabel}</Badge>
              </summary>
              <div className="mt-3 space-y-2 text-sm">
                <div className="font-medium">{createdByLabel}</div>
                <div className="text-xs text-muted-foreground">{quote.created_at ? new Date(quote.created_at).toLocaleString("en-GB") : "Created date not recorded"}</div>
              </div>
            </details>

            <details className="rounded-md border bg-background p-2.5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium">
                <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4" />Quality and risk</span>
                <Badge variant={qualityReport.score >= 80 ? "secondary" : qualityReport.score >= 60 ? "warning" : "outline"}>{qualityReport.score}%</Badge>
              </summary>
              <div className="mt-3 space-y-3">
                <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                  <span>Commercial {qualityReport.quoteScore}% / Technical {qualityReport.technicalScore}% / Risk {qualityReport.riskScore}%</span>
                  <span>{readiness}% item ready</span>
                </div>
                <ProgressBar value={qualityReport.score} />
                {qualityReport.missing.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {qualityReport.missing.slice(0, 4).map((item) => <Badge key={item} variant="outline">{item}</Badge>)}
                    {qualityReport.missing.length > 4 && <Badge variant="muted">+{qualityReport.missing.length - 4}</Badge>}
                  </div>
                )}
                <div className="space-y-2">
                  {qualityReport.risks.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No technical risks detected.</div>
                  ) : (
                    qualityReport.risks.slice(0, 3).map((risk) => (
                      <div key={`${risk.title}-${risk.detail}`} className="rounded-md bg-muted/40 px-2 py-1.5 text-xs">
                        <span className="font-medium">{risk.title}</span>
                        <span className="text-muted-foreground"> - {risk.detail}</span>
                        {risk.rows?.length ? <span className="text-muted-foreground"> Rows {risk.rows.slice(0, 6).join(", ")}</span> : null}
                      </div>
                    ))
                  )}
                  {qualityReport.risks.length > 3 && <div className="text-xs text-muted-foreground">+{qualityReport.risks.length - 3} more risk checks</div>}
                </div>
              </div>
            </details>
          </div>
        )}
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {isDraftSection && canEditQuote && (
        <Dialog open={!intakeCollapsed || startingExtraction} onOpenChange={(open) => { if (!open && !startingExtraction) setIntakeCollapsed(true); }}>
          <DialogContent className="flex max-h-[92vh] max-w-6xl flex-col overflow-hidden p-0">
            <DialogHeader className="border-b px-4 py-3">
              <DialogTitle>Add enquiry items</DialogTitle>
              <DialogDescription>Paste an email, import Excel, or add rows manually. The items will appear in the spreadsheet.</DialogDescription>
            </DialogHeader>
        <Card id="enquiry-intake" className="min-h-0 overflow-auto rounded-none border-0 shadow-none">
          <CardHeader className="hidden">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md border bg-background">
                  <Inbox className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="space-y-0.5">
                  <CardTitle className="text-base">Add customer enquiry</CardTitle>
                  <div className="text-xs text-muted-foreground">
                    {intakeCollapsed && !startingExtraction ? `${items.length} item(s) captured` : "Paste email, upload Excel, or add a quick manual row"}
                  </div>
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
          {intakeCollapsed && !startingExtraction ? null : (
            <CardContent className="p-3">
              <Tabs defaultValue="email">
                <TabsList className="grid h-auto w-full grid-cols-3 md:w-fit">
                  <TabsTrigger value="email" className="gap-2"><Mail className="h-4 w-4" />Email</TabsTrigger>
                  <TabsTrigger value="excel" className="gap-2"><FileSpreadsheet className="h-4 w-4" />Excel</TabsTrigger>
                  <TabsTrigger value="manual" className="gap-2"><Plus className="h-4 w-4" />Manual</TabsTrigger>
                </TabsList>
                <TabsContent value="email" className="mt-3">
                  <textarea
                    className="min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                    value={emailText}
                    onChange={(event) => setEmailText(event.target.value)}
                    onPaste={(event) => {
                      const text = event.clipboardData.getData("text/plain");
                      const detection = detectClipboardTable(event.clipboardData.getData("text/html"), text);
                      if (!detection) return;
                      setEmailTablePreview(detection);
                      if (!text.trim()) {
                        event.preventDefault();
                        setEmailText(rowsToTsv(detection.rows));
                      }
                    }}
                    placeholder="Paste raw customer enquiry email text"
                  />
                  {emailTablePreview && (
                    <div className="mt-3 rounded-md border border-amber-300 bg-amber-50/70 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/20">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <div className="font-medium">Detected a {emailTablePreview.source === "html" ? "formatted email" : "tab-separated"} table</div>
                          <div className="text-xs text-muted-foreground">
                            {emailTablePreview.bodyRows.length} row(s) detected. Keep the pasted text for reference, or import the table directly.
                          </div>
                        </div>
                        <Badge variant="outline">{emailTablePreview.hasHeader ? "Headers detected" : "Using standard column order"}</Badge>
                      </div>
                      <div className="mt-2 max-h-40 overflow-auto rounded border bg-background">
                        <Table className="text-xs">
                          <TableBody>
                            {emailTablePreview.rows.slice(0, 5).map((row, rowIndex) => (
                              <TableRow key={`${rowIndex}-${row.join("-")}`}>
                                {row.map((cell, cellIndex) => <TableCell key={cellIndex} className="max-w-72 whitespace-normal break-words px-2 py-1">{cell}</TableCell>)}
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" onClick={importDetectedEmailTable}>
                          <Plus className="h-4 w-4" />
                          Import detected table
                        </Button>
                        <Button variant="secondary" size="sm" onClick={() => runExtraction("email")} disabled={emailCreateDisabled} title={emailCreateTitle}>
                          Process as email text
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setEmailTablePreview(null)}>Dismiss preview</Button>
                      </div>
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button onClick={() => runExtraction("email")} disabled={emailCreateDisabled} title={emailCreateTitle}>
                      {startingExtraction ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      Create items from email
                    </Button>
                    <Button variant="secondary" onClick={() => setEmailText("")} disabled={!emailText}>
                      <X className="h-4 w-4" />
                      Clear
                    </Button>
                  </div>
                </TabsContent>
                <TabsContent value="excel" className="mt-3">
                  <div className="rounded-md border border-dashed p-3">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-background">
                          <FileUp className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div>
                          <div className="text-sm font-medium">{excelFile?.name || "Choose an Excel or CSV file"}</div>
                          <div className="text-xs text-muted-foreground">.xlsx, .xls, and .csv enquiries</div>
                        </div>
                      </div>
                      <Input className="max-w-sm" type="file" accept=".xlsx,.xls,.csv" onChange={(event) => setExcelFile(event.target.files?.[0] ?? null)} />
                    </div>
                  </div>
                  <Button className="mt-3" onClick={() => runExtraction(excelFile?.name.toLowerCase().endsWith(".csv") ? "csv" : "excel", excelFile)} disabled={excelCreateDisabled} title={excelCreateTitle}>
                    <Upload className="h-4 w-4" />
                    Create items from file
                  </Button>
                </TabsContent>
                <TabsContent value="manual" className="mt-3">
                  <div className="space-y-3" onPaste={handleManualPaste}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <div className="text-sm font-medium">Add several items at once</div>
                        <div className="text-xs text-muted-foreground">Paste Excel rows with optional headers, or add blank rows and type into the table.</div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {[1, 5, 10].map((count) => (
                          <Button key={count} variant="secondary" size="sm" onClick={() => appendManualRows(count)}>
                            <Plus className="h-4 w-4" />
                            Insert {count} row{count === 1 ? "" : "s"}
                          </Button>
                        ))}
                      </div>
                    </div>
                    <div className="overflow-auto rounded-md border">
                      <Table className="min-w-[920px] text-xs">
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-12">#</TableHead>
                            <TableHead className="w-28">Customer Sl.No</TableHead>
                            <TableHead className="w-40">Item code</TableHead>
                            <TableHead>Description</TableHead>
                            <TableHead className="w-24">Qty</TableHead>
                            <TableHead className="w-24">UOM</TableHead>
                            <TableHead className="w-16" />
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {manualRows.map((row, index) => (
                            <TableRow key={index}>
                              <TableCell>{index + 1}</TableCell>
                              <TableCell><Input value={getString(row.customer_sl_no)} onChange={(event) => updateManualRow(index, "customer_sl_no", event.target.value)} /></TableCell>
                              <TableCell><Input value={getString(row.customer_item_code)} onChange={(event) => updateManualRow(index, "customer_item_code", event.target.value)} /></TableCell>
                              <TableCell><textarea className="min-h-16 w-full min-w-96 resize-y rounded-md border bg-background px-2 py-1 text-xs" value={getString(row.raw_description)} onChange={(event) => updateManualRow(index, "raw_description", event.target.value)} /></TableCell>
                              <TableCell><Input type="number" value={getString(row.quantity)} onChange={(event) => updateManualRow(index, "quantity", event.target.value)} /></TableCell>
                              <TableCell><Input value={getString(row.uom)} onChange={(event) => updateManualRow(index, "uom", event.target.value)} /></TableCell>
                              <TableCell>
                                <Button variant="ghost" size="icon" onClick={() => setManualRows((current) => current.length === 1 ? [blankItem(1)] : current.filter((_, rowIndex) => rowIndex !== index))} title="Remove manual row">
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                    <div>
                      <Button onClick={addManualItems}>
                        <Plus className="h-4 w-4" />
                        Add {manualRows.length} row{manualRows.length === 1 ? "" : "s"} to enquiry
                      </Button>
                    </div>
                  </div>
                </TabsContent>
              </Tabs>
              {startingExtraction && (
                <div className="mt-4 rounded-md border bg-muted/40 p-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Creating item list in the background
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </Card>
          </DialogContent>
        </Dialog>
      )}

      {isDraftSection && (
        <>
          {tableMode === "guided" && (
            <details className="rounded-md border bg-card p-3">
              <summary className="cursor-pointer text-sm font-medium">Review summary and history</summary>
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
          <Card className={tableMode === "spreadsheet" ? `rounded-none shadow-none ${spreadsheetFullscreen ? "fixed inset-0 z-50 flex h-[100dvh] w-[100vw] flex-col border-0 bg-background" : ""}` : ""}>
            <CardHeader className={`sticky ${spreadsheetFullscreen ? "top-0" : "top-16"} z-20 border-b bg-card/95 ${tableMode === "spreadsheet" ? "px-3 py-2" : "px-4 py-3"}`}>
              <div className="flex flex-col gap-2 2xl:flex-row 2xl:items-center 2xl:justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md border bg-background">
                    <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="space-y-0.5">
                    <CardTitle className="text-base">Enquiry items</CardTitle>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>{items.length} items</span>
                    <span>{readyCount} ready</span>
                    <span>{actionCount} need review</span>
                    {selectedIndices.length > 0 && <Badge variant="outline">{selectedIndices.length} selected</Badge>}
                    {tableMode === "spreadsheet" && <Badge variant="muted">{selectedCellCount ? `${selectedCellCount} cells` : "Spreadsheet"}</Badge>}
                    {filterCount > 0 && <Badge variant="outline">{filterCount} grid filter{filterCount === 1 ? "" : "s"}</Badge>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                  <div className="flex shrink-0 items-center gap-1.5 border bg-background p-1">
                    <Select value={tableMode} onValueChange={(value) => setTableMode(value as "guided" | "spreadsheet")}>
                      <SelectTrigger className="h-8 w-40 border-0 bg-transparent"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="spreadsheet">Spreadsheet</SelectItem>
                        <SelectItem value="guided">Simple review</SelectItem>
                      </SelectContent>
                    </Select>
                    {tableMode === "guided" ? (
                      <Select value={columnPreset} onValueChange={setColumnPreset}>
                        <SelectTrigger className="h-8 w-40 border-0 bg-transparent"><SelectValue /></SelectTrigger>
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
                      <Badge variant="outline" className="h-8 rounded-md px-3 text-xs">
                        {activeTableColumns.length} columns
                      </Badge>
                    )}
                    <Select value={statusFilter} onValueChange={setStatusFilter}>
                      <SelectTrigger className="h-8 w-40 border-0 bg-transparent"><ListFilter className="h-4 w-4" /><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="ready">Ready</SelectItem>
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
                  </div>
                  {canEditLineItems && (
                    <>
                      <Button variant="secondary" size="sm" className="shrink-0" onClick={addBlankRow} title="Add row">
                        <Plus className="h-4 w-4" />
                        Row
                      </Button>
                    </>
                  )}
                  <Button variant="secondary" size="sm" className="shrink-0" onClick={() => setRowEditorOpen((value) => !value)} title={rowEditorOpen ? "Minimize row editor" : "Open row editor"}>
                    <PanelRight className="h-4 w-4" />
                    {rowEditorOpen ? "Hide row editor" : "Edit selected row"}
                  </Button>
                  {tableMode === "spreadsheet" && (
                    <>
                      <Button variant="secondary" size="sm" className="shrink-0" onClick={() => setCompactRows((value) => !value)} title="Toggle wrapped description rows">
                        {compactRows ? "Wrap rows" : "Compact rows"}
                      </Button>
                      <Button variant="secondary" size="sm" className="shrink-0" onClick={() => setSpreadsheetFullscreen((value) => !value)} title={spreadsheetFullscreen ? "Exit fullscreen spreadsheet" : "Open fullscreen spreadsheet"}>
                        {spreadsheetFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                        {spreadsheetFullscreen ? "Exit full screen" : "Full screen"}
                      </Button>
                    </>
                  )}
                  {canEditQuotation && (
                    <Button size="sm" className="shrink-0" onClick={openQuotationScreen} disabled={!quote || !items.length}>
                      <ArrowRight className="h-4 w-4" />
                      Quotation
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className={tableMode === "spreadsheet" ? `space-y-3 p-3 ${spreadsheetFullscreen ? "flex-1 overflow-auto" : ""}` : "space-y-4 pt-5"}>
              {!canEditLineItems && (
                <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                  Sales access is view-only for line items and quotation work. Customer details and notes can still be updated above.
                </div>
              )}
              {canEditLineItems && (
              <div className={`flex items-center gap-1.5 overflow-x-auto ${tableMode === "spreadsheet" ? "border bg-muted/20 p-1.5" : ""}`}>
                <div className="flex shrink-0 gap-1 border bg-background p-0.5">
                <Button variant="ghost" size="sm" onClick={() => reprocessRows()} disabled={rereadRowsDisabled} title={rereadRowsTitle}>
                  {startingExtraction ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
                  Re-read rows
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setSelectedRows(new Set(displayIndices))} title="Select all visible rows">
                  <CheckCircle2 className="h-4 w-4" />
                  Select
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedRows(new Set());
                    setActiveCell(null);
                    setSelectionAnchor(null);
                    setSelectionFocus(null);
                  }}
                  title="Clear row and cell selection"
                >
                  <X className="h-4 w-4" />
                  Clear
                </Button>
                <Button variant="ghost" size="sm" onClick={clearGridFilters} disabled={!filterCount} title="Clear column filters">
                  <ListFilter className="h-4 w-4" />
                  Filters
                </Button>
                </div>
                <Button variant="secondary" size="sm" className="shrink-0" onClick={toggleRegretSelected} disabled={!selectedIndices.length} title="Toggle regret for selected rows">
                  <Ban className="h-4 w-4" />
                  Regret
                </Button>
                <Button variant="destructive" size="sm" className="shrink-0" onClick={deleteSelectedRows} disabled={!selectedIndices.length}>
                  <Trash2 className="h-4 w-4" />
                  Delete{selectedIndices.length ? ` (${selectedIndices.length})` : ""}
                </Button>
                {undoItems && (
                  <Button variant="secondary" size="sm" onClick={restoreUndoItems}>
                    <Undo2 className="h-4 w-4" />
                    {undoItems.label}
                  </Button>
                )}
                {tableMode === "spreadsheet" && (
                  <details className="relative shrink-0">
                    <summary className="cursor-pointer list-none rounded-md border bg-background px-3 py-1.5 text-xs font-medium">Keyboard shortcuts</summary>
                    <div className="absolute right-0 z-40 mt-1 w-80 rounded-md border bg-background p-3 text-xs shadow-lg">
                      <div className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-1">
                        <span className="font-mono">Arrows / Tab</span><span>Move through cells</span>
                        <span className="font-mono">Shift + Arrows</span><span>Extend cell selection</span>
                        <span className="font-mono">F2</span><span>Edit active cell</span>
                        <span className="font-mono">Ctrl+C / Ctrl+V</span><span>Copy or paste rectangular cells</span>
                        <span className="font-mono">Delete</span><span>Clear selected cell contents</span>
                        <span className="font-mono">Ctrl+-</span><span>Delete selected rows with confirmation</span>
                        <span className="font-mono">Ctrl+Shift++</span><span>Insert blank rows above selection</span>
                        <span className="font-mono">Ctrl+D</span><span>Fill selected cells downward</span>
                        <span className="font-mono">Ctrl+Z</span><span>Undo last supported grid change</span>
                      </div>
                    </div>
                  </details>
                )}
              </div>
              )}

              <div className={rowEditorOpen ? "grid gap-3 xl:grid-cols-[minmax(0,1fr)_380px]" : "grid gap-3"}>
                <div className="min-w-0 space-y-3">
              <div className={`${tableMode === "spreadsheet" && pageCount === 1 ? "hidden" : "flex"} flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm`}>
                <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
                  <span>Showing {pageStart}-{pageEnd} of {displayIndices.length}</span>
                  {tableMode === "spreadsheet" && <Badge variant="muted">Paste Excel ranges</Badge>}
                  {isLargeDraft && tableMode !== "spreadsheet" && <Badge variant="muted">Compact large enquiry view</Badge>}
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

              {tableMode === "spreadsheet" && (
                <div className="grid gap-2 border bg-[#f8f8f8] p-2 text-xs dark:bg-muted/40 md:grid-cols-[132px_minmax(0,1fr)_auto]">
                  <div className="flex h-8 items-center border bg-background px-2 font-medium text-muted-foreground">
                    {activeCellAddress || "Select a cell"}
                  </div>
                  <div className="flex h-8 min-w-0 items-center border bg-background">
                    <div className="flex h-full w-14 shrink-0 items-center justify-center border-r text-muted-foreground">Value</div>
                    <input
                      className="h-full min-w-0 flex-1 border-0 bg-transparent px-2 font-mono text-xs outline-none"
                      value={activeCellValue}
                      readOnly
                      placeholder="Click any cell in the table"
                      title={activeCellValue || "Click any cell in the table"}
                    />
                  </div>
                  <div className="flex h-8 items-center gap-2 border bg-background px-2 text-muted-foreground">
                    <span>{selectedCellCount ? `${selectedCellCount} cell${selectedCellCount === 1 ? "" : "s"} selected` : "No selection"}</span>
                    {editingCell && <Badge variant="outline">Edit</Badge>}
                  </div>
                </div>
              )}

              <div
                ref={draftGridRef}
                tabIndex={0}
                className={`overflow-auto border ${tableMode === "spreadsheet" ? "h-[62vh] min-h-[460px] max-h-[760px] rounded-none bg-background" : "max-h-[620px] rounded-md"}`}
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
                      <TableHead className={`sticky left-0 z-40 h-8 w-10 border-r px-2 text-center ${tableMode === "spreadsheet" ? "bg-[#f3f3f3] text-muted-foreground dark:bg-muted" : "bg-card"}`}>
                        {tableMode === "spreadsheet" ? "" : "Sel"}
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
                          <TableCell className={`sticky left-0 z-20 border-r p-0 text-center align-middle ${tableMode === "spreadsheet" ? "bg-[#f3f3f3] text-muted-foreground dark:bg-muted" : "bg-card"}`}>
                            {tableMode === "spreadsheet" ? (
                              <button
                                type="button"
                                className={`h-full w-full px-1 text-xs ${selected ? "bg-emerald-100 text-emerald-950 dark:bg-emerald-950/40 dark:text-emerald-100" : ""}`}
                                onClick={() => {
                                  const next = new Set(selectedRows);
                                  if (next.has(index)) next.delete(index);
                                  else next.add(index);
                                  setSelectedRows(next);
                                }}
                                title={`Select row ${index + 1}`}
                              >
                                {index + 1}
                              </button>
                            ) : (
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
                            )}
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
                                    reprocessRows([index]);
                                  }}
                                  title="Re-read this row from customer text"
                                  disabled={!getString(item.raw_description).trim()}
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
                              className={`border-r p-0 align-top outline-none ${selectedCell ? "bg-emerald-50 ring-1 ring-inset ring-emerald-400/60 dark:bg-emerald-950/20" : ""} ${activeGridCell ? "ring-2 ring-inset ring-emerald-600" : ""}`}
                              onMouseDown={(event) => {
                                if (tableMode !== "spreadsheet") return;
                                if ((event.target as HTMLElement).closest("button,input,textarea,[role='combobox']")) return;
                                event.preventDefault();
                                selectGridCell(index, colIndex, event.shiftKey);
                                setIsSelectingCells(true);
                                focusGridCell(index, colIndex);
                              }}
                              onDoubleClick={(event) => {
                                if (tableMode !== "spreadsheet") return;
                                event.preventDefault();
                                if (column.kind === "checkbox") {
                                  toggleGridCheckbox(index, column);
                                  return;
                                }
                                startEditingGridCell(index, colIndex);
                              }}
                              onMouseEnter={() => {
                                if (tableMode !== "spreadsheet" || !isSelectingCells) return;
                                selectGridCell(index, colIndex, true);
                              }}
                              onFocus={() => {
                                if (tableMode !== "spreadsheet") return;
                                if (isEditingGridCell(index, colIndex)) return;
                                if (!isGridCellSelected(index, colIndex)) selectGridCell(index, colIndex, false);
                              }}
                            >
                              {renderGridCell(index, item, column, colIndex)}
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
                <details className="rounded-md border p-2">
                  <summary className="cursor-pointer text-sm font-medium">
                    <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4" />Advanced review panels</span>
                  </summary>
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

                {rowEditorOpen && <aside className={`h-fit border bg-background p-3 xl:sticky xl:top-32 xl:max-h-[calc(100vh-9rem)] xl:overflow-auto ${tableMode === "spreadsheet" ? "rounded-none" : "rounded-md"}`}>
                  <div className="flex items-start justify-between gap-3 border-b pb-3">
                    <div>
                      <div className="inline-flex items-center gap-2 text-sm font-medium"><PanelRight className="h-4 w-4" />Row editor</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {selectedItem && selectedRowIndex !== null
                          ? `Row ${selectedRowIndex + 1}`
                          : selectedIndices.length > 1
                            ? `${selectedIndices.length} rows selected`
                            : "Select one row"}
                      </div>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => setRowEditorOpen(false)} aria-label="Minimize row editor" title="Minimize row editor">
                      <Minimize2 className="h-4 w-4" />
                    </Button>
                    {selectedItem && selectedRowIndex !== null && (
                      <div className="min-w-32">
                        <Label className="mb-1.5 block text-xs text-muted-foreground">Status</Label>
                        <Select value={getString(selectedItem.status) || "missing"} onValueChange={(value) => updateItem(selectedRowIndex, "status", value)} disabled={!canEditLineItems}>
                          <SelectTrigger className={SHEET_SELECT_CLASS}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {STATUS_OPTIONS.map((value) => <SelectItem key={value} value={value}>{STATUS_LABELS[value]}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
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
                        ? "Select one row to edit its details here."
                        : "Click a row or select a cell to edit its details here."}
                    </div>
                  )}
                </aside>}
              </div>

              <div className="grid min-w-0 gap-3">
                <details className="group min-w-0 rounded-md border bg-background">
                  <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-3 py-2">
                    <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-90" />
                        Extraction summary
                        <Badge variant={extractionSummaryStale ? "warning" : "secondary"}>{extractionSummaryStale ? "Stale - regenerate" : "Current"}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                        <span>{extractionSummaryRows.reduce((total, row) => total + row.count, 0)} matched item(s)</span>
                        <span>{unmatchedSummaryItemRows.length} unmatched row(s)</span>
                      </div>
                    </div>
                    {canEditLineItems && (
                      <div className="flex gap-1.5">
                        <Button size="sm" onClick={(event) => { event.preventDefault(); regenerateExtractionSummary(); }}>
                          <RefreshCw className="h-4 w-4" />
                          Update summary
                        </Button>
                      </div>
                    )}
                  </summary>
                  <div className="border-t px-3 py-2">
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span>Grouped from processed rows. Manual notes are retained when regenerated.</span>
                      {canEditLineItems && (
                        <div className="flex flex-wrap gap-1.5">
                          <Button variant="secondary" size="sm" onClick={addBlankRow}>
                            <Plus className="h-4 w-4" />
                            Item row
                          </Button>
                          <Button variant="secondary" size="sm" onClick={saveExtractionSummaryNotes}>
                            <Save className="h-4 w-4" />
                            Save notes
                          </Button>
                        </div>
                      )}
                    </div>
                  <div className="max-h-72 max-w-full overflow-auto border bg-background">
                    <Table className={`${SHEET_TABLE_CLASS} min-w-[760px]`}>
                      <TableHeader className={SHEET_HEADER_CLASS}>
                        <TableRow>
                          <TableHead className={SHEET_ROW_HEADER_CLASS} />
                          <TableHead className={`${SHEET_HEAD_CLASS} min-w-56`}>Summary item</TableHead>
                          <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Count</TableHead>
                          <TableHead className={`${SHEET_HEAD_CLASS} min-w-56`}>Note 1</TableHead>
                          <TableHead className={`${SHEET_HEAD_CLASS} min-w-56`}>Note 2</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {extractionSummaryRows.length > 0 ? extractionSummaryRows.map((row, index) => (
                          <TableRow key={`${row.item}-${index}`}>
                            <TableCell className={SHEET_ROW_HEADER_CLASS}>{index + 1}</TableCell>
                            <TableCell className={SHEET_CELL_CLASS}>
                              <div className="min-w-56 whitespace-normal break-words px-2 py-1">{row.item}</div>
                            </TableCell>
                            <TableCell className={SHEET_CELL_CLASS}>
                              <div className="px-2 py-1 text-right font-medium">{row.count}</div>
                            </TableCell>
                            <TableCell className={SHEET_CELL_CLASS}>
                              <textarea
                                className={`${SHEET_TEXTAREA_CLASS} h-8 min-h-8 resize-none`}
                                value={row.note1}
                                onChange={(event) => updateExtractionSummaryNote(row.item, "note1", event.target.value)}
                                placeholder="Add note"
                                disabled={!canEditLineItems}
                              />
                            </TableCell>
                            <TableCell className={SHEET_CELL_CLASS}>
                              <textarea
                                className={`${SHEET_TEXTAREA_CLASS} h-8 min-h-8 resize-none`}
                                value={row.note2}
                                onChange={(event) => updateExtractionSummaryNote(row.item, "note2", event.target.value)}
                                placeholder="Add note"
                                disabled={!canEditLineItems}
                              />
                            </TableCell>
                          </TableRow>
                        )) : (
                          <TableRow>
                            <TableCell className={SHEET_CELL_CLASS} colSpan={5}>No matched items yet.</TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                  </div>
                </details>
                <details className="group rounded-md border bg-background lg:col-span-2">
                  <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-3 py-2">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-90" />
                      Missing-field clarification
                      {rfiText && <Badge variant="secondary">Email ready</Badge>}
                    </div>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={(event) => { event.preventDefault(); buildClarificationEmail(); }}
                    >
                      Create email
                    </Button>
                  </summary>
                  <div className="border-t p-3">
                    <textarea
                      className="min-h-16 w-full rounded-md border bg-background px-3 py-2 text-sm"
                      value={getString(quote.stage_meta?.clarification_note)}
                      onChange={(event) => {
                        const stageMeta = { ...(quote.stage_meta ?? {}), clarification_note: event.target.value };
                        setQuote((current) => (current ? { ...current, stage_meta: stageMeta } : current));
                        setHasUnsavedLocalEdits(true);
                      }}
                      placeholder="What should the customer clarify?"
                    />
                    <textarea
                      className="mt-2 min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm"
                      value={rfiText}
                      onChange={(event) => setRfiText(event.target.value)}
                      placeholder="Created email text will appear here"
                    />
                    {rfiText && (
                      <a
                        className="mt-2 inline-flex h-8 items-center rounded-md border px-3 text-sm"
                        download="rfi-enquiry.txt"
                        href={`data:text/plain;charset=utf-8,${encodeURIComponent(rfiText)}`}
                      >
                        Download email text
                      </a>
                    )}
                  </div>
                </details>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/20 px-3 py-2">
                <div className="min-w-0">
                  <div className="text-xs font-medium">Material planning</div>
                  <div className="text-xs text-muted-foreground">
                    {quote.stage_meta?.material_planning_enabled === true ? "Included in material planning." : "Press to add this enquiry to material planning."}
                  </div>
                </div>
                <Button
                  variant={quote.stage_meta?.material_planning_enabled === true ? "secondary" : "default"}
                  size="sm"
                  onClick={() => updateQueueMeta(quote, {
                    material_planning_enabled: true,
                    material_planning_enabled_at: new Date().toISOString(),
                  })}
                  disabled={quote.stage_meta?.material_planning_enabled === true}
                >
                  <Layers3 className="h-4 w-4" />
                  {quote.stage_meta?.material_planning_enabled === true ? "Added to material" : "Add to material planning"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {isMaterialSection && (
        <Card className="overflow-hidden">
          <CardHeader className="border-b px-4 py-3">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md border bg-background">
                  <Layers3 className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="space-y-0.5">
                  <CardTitle className="text-base">Material planning</CardTitle>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant={materialBreakdown?.length ? "secondary" : "outline"}>Material needed</Badge>
                    <Badge variant={materialPhase2Finished ? "secondary" : materialPlan ? "warning" : "outline"}>Purchase plan{materialPlanStatus ? ` ${materialPlanStatus}` : ""}</Badge>
                    <span>{items.length} enquiry item(s)</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {(materialBreakdown || materialPlan) && canEditMaterialPhase2 && !materialPhase2Finished && (
                  <Button variant="secondary" size="sm" onClick={clearMaterialPlan}>
                    <X className="h-4 w-4" />
                    Clear
                  </Button>
                )}
                <Button variant="secondary" size="sm" onClick={generateMaterialBreakdown} disabled={!items.length || !canRunMaterialPhase1}>
                  <Layers3 className="h-4 w-4" />
                  {materialBreakdown ? "Update material needed" : "Create material needed"}
                </Button>
                <Button variant={materialPlan ? "secondary" : "default"} size="sm" onClick={startManualMaterialPlan} disabled={!items.length || !materialBreakdown?.length || !canEditMaterialPhase2 || materialPhase2Finished}>
                  <ArrowRight className="h-4 w-4" />
                  {materialPlan ? "Reset purchase plan" : "Create purchase plan"}
                </Button>
                {materialPlan && canEditMaterialPhase2 && !materialPhase2Finished && (
                  <Button variant="secondary" size="sm" onClick={submitMaterialPlan}>
                    <Send className="h-4 w-4" />
                    Save purchase plan
                  </Button>
                )}
                {materialPlan && canEditMaterialPhase2 && !materialPhase2Finished && (
                  <Button size="sm" onClick={finishMaterialPlan}>
                    <CheckCircle2 className="h-4 w-4" />
                    Finish planning
                  </Button>
                )}
                <Button variant="secondary" size="sm" onClick={() => copyRowsToClipboard("Material needed", phase1ExportRows())} disabled={!materialBreakdown?.length}>
                  <Copy className="h-4 w-4" />
                  Copy needed
                </Button>
                <Button variant="secondary" size="sm" onClick={() => downloadRowsAsCsv(`${exportFileStem("phase-1-breakdown")}.csv`, phase1ExportRows())} disabled={!materialBreakdown?.length}>
                  <Download className="h-4 w-4" />
                  CSV needed
                </Button>
                <Button variant="secondary" size="sm" onClick={() => copyRowsToClipboard("Purchase plan", phase2ExportRows())} disabled={!materialPlan}>
                  <Copy className="h-4 w-4" />
                  Copy plan
                </Button>
                <Button variant="secondary" size="sm" onClick={() => downloadRowsAsCsv(`${exportFileStem("phase-2-material-plan")}.csv`, phase2ExportRows())} disabled={!materialPlan}>
                  <Download className="h-4 w-4" />
                  CSV plan
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 p-3">
            {quote?.stage_meta?.material_plan_stale === true ? (
              <div className="flex items-start gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <div className="font-medium">Material plan needs recalculation</div>
                  <div className="mt-1 text-xs">Enquiry items changed after planning. The previous plan remains visible for reference. Update material needed before saving or finishing the purchase plan.</div>
                </div>
              </div>
            ) : null}
            {!materialBreakdown?.length ? (
              <div className="flex items-center gap-3 rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
                <Layers3 className="h-4 w-4 shrink-0" />
                <span>Create the material needed list to consolidate rows by size, rating, thickness, materials, filler, quantity, series, and remarks.</span>
              </div>
            ) : (
              <details className="rounded-md border p-3" open>
                <summary className="cursor-pointer text-sm font-medium">
                  <span className="inline-flex items-center gap-2"><Layers3 className="h-4 w-4" />Material needed</span>
                </summary>
                <div className="mt-3 max-h-[520px] overflow-auto border bg-background">
                  <Table className={SHEET_TABLE_CLASS}>
                    <TableHeader className={SHEET_HEADER_CLASS}>
                      <TableRow>
                        <TableHead className={SHEET_ROW_HEADER_CLASS} />
                        <TableHead className={`${SHEET_HEAD_CLASS} w-20`}>Review</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-16`}>SL</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-32`}>Type</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Size (inch)</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-32`}>Pressure rating</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Thickness</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-36`}>Primary material</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-36`}>Secondary / inner</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-36`}>Outer / hardware</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-44`}>Filler / facing / seals</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Qty</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-24`}>UOM</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-32`}>Series</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} min-w-56`}>Remarks</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>OD mm</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>ID mm</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Source rows</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {materialBreakdown.map((row, index) => (
                        <TableRow key={`${row.line_no}-${row.size_inch}-${row.pressure_rating}-${index}`} className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/10">
                          <TableCell className={SHEET_ROW_HEADER_CLASS}>{index + 1}</TableCell>
                          <TableCell className={`${SHEET_CELL_CLASS} text-center`}>
                            <input
                              type="checkbox"
                              checked={row.reviewed}
                              onChange={(event) => updateBreakdownRow(index, { reviewed: event.target.checked })}
                              aria-label={`Mark breakdown row ${index + 1} reviewed`}
                            />
                          </TableCell>
                          <TableCell className={SHEET_CELL_CLASS}>{row.line_no}</TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-28`} value={row.gasket_type} onChange={(event) => updateBreakdownRow(index, { gasket_type: event.target.value.toUpperCase() })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} value={row.size_inch} onChange={(event) => updateBreakdownRow(index, { size_inch: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-28`} value={row.pressure_rating} onChange={(event) => updateBreakdownRow(index, { pressure_rating: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} value={row.thickness} onChange={(event) => updateBreakdownRow(index, { thickness: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-32`} value={row.winding} onChange={(event) => updateBreakdownRow(index, { winding: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-32`} value={row.inner_ring} onChange={(event) => updateBreakdownRow(index, { inner_ring: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-32`} value={row.outer_ring} onChange={(event) => updateBreakdownRow(index, { outer_ring: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-40`} value={row.filler} onChange={(event) => updateBreakdownRow(index, { filler: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} type="number" value={getString(row.qty)} onChange={(event) => updateBreakdownRow(index, { qty: Number(event.target.value) || 0 })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-20`} value={row.uom} onChange={(event) => updateBreakdownRow(index, { uom: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-28`} value={row.series} onChange={(event) => updateBreakdownRow(index, { series: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-52`} value={row.remarks} onChange={(event) => updateBreakdownRow(index, { remarks: event.target.value })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} type="number" value={getString(row.od_mm)} onChange={(event) => updateBreakdownRow(index, { od_mm: Number(event.target.value) || null })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} type="number" value={getString(row.id_mm)} onChange={(event) => updateBreakdownRow(index, { id_mm: Number(event.target.value) || null })} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}>{row.source_rows}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                <div className="mt-3 text-xs leading-5 text-muted-foreground">
                  Review and correct this list before creating the purchase plan. If OD/ID is blank, the purchase plan can still estimate from nominal size, but it will mark the row for review.
                </div>
              </details>
            )}

            {!materialPlan ? (
              <div className="flex items-center gap-3 rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
                <ArrowRight className="h-4 w-4 shrink-0" />
                <span>Material planner users can create the purchase plan after reviewing material needed. The purchase plan tracks stock, quantity, vendor, shortage, and planner notes.</span>
              </div>
            ) : (
              <>
                <div className="space-y-1 text-center">
                  <div className="text-base font-semibold uppercase tracking-tight">
                    {quote?.customer || quote?.quote_no || "Untitled enquiry"} - REG : {quote?.quote_no || quote?.id || "N/A"} / {quote?.project_ref || "N/A"} / {quote?.custom_label || "GASKETS"}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    The purchase plan is manually maintained by the material planner. Add, delete, and edit rows before saving or finishing planning.
                  </div>
                </div>

                <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Rows</div>
                    <div className="text-lg font-semibold">{materialPlan.totals.component_count}</div>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">Sheet qty</div>
                    <div className="text-lg font-semibold">{materialPlan.totals.sheet_count.toFixed(0)}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Weight qty</div>
                    <div className="text-lg font-semibold">{materialPlan.totals.total_weight_kg.toFixed(3)} kg</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Shortage rows</div>
                    <div className="text-lg font-semibold">{materialPlan.rows.filter((row) => row.shortage_qty > 0).length}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Suggested purchase</div>
                    <div className="text-lg font-semibold">{materialPlan.rows.reduce((sum, row) => sum + row.suggested_purchase_qty, 0).toFixed(2)}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Material cost</div>
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
                    <summary className="cursor-pointer text-sm font-medium">
                      <span className="inline-flex items-center gap-2"><ShoppingCart className="h-4 w-4" />Grouped purchase summary</span>
                    </summary>
                    <div className="mt-3 overflow-auto border bg-background">
                      <Table className={SHEET_TABLE_CLASS}>
                        <TableHeader className={SHEET_HEADER_CLASS}>
                          <TableRow>
                            <TableHead className={SHEET_ROW_HEADER_CLASS} />
                            <TableHead className={`${SHEET_HEAD_CLASS} min-w-96`}>Material / thickness / vendor</TableHead>
                            <TableHead className={`${SHEET_HEAD_CLASS} w-24`}>Rows</TableHead>
                            <TableHead className={`${SHEET_HEAD_CLASS} w-32`}>Shortage</TableHead>
                            <TableHead className={`${SHEET_HEAD_CLASS} w-40`}>Suggested purchase</TableHead>
                            <TableHead className={`${SHEET_HEAD_CLASS} w-36`}>Est. cost</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {(materialPlan.grouped_summary ?? []).map((row, index) => (
                            <TableRow key={row.group} className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/10">
                              <TableCell className={SHEET_ROW_HEADER_CLASS}>{index + 1}</TableCell>
                              <TableCell className={`${SHEET_CELL_CLASS} font-medium`}>{row.group}</TableCell>
                              <TableCell className={SHEET_CELL_CLASS}>{row.rows}</TableCell>
                              <TableCell className={SHEET_CELL_CLASS}>{row.shortage_qty.toFixed(2)}</TableCell>
                              <TableCell className={SHEET_CELL_CLASS}>{row.suggested_purchase_qty.toFixed(2)}</TableCell>
                              <TableCell className={SHEET_CELL_CLASS}>{row.estimated_material_cost.toFixed(2)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </details>
                )}

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm">
                  <div className="text-muted-foreground">
                    {canEditMaterialPhase2 && !materialPhase2Finished ? "Edit purchase-plan rows directly, then save or finish planning." : "The purchase plan is view-only for this user or status."}
                  </div>
                  {canEditMaterialPhase2 && !materialPhase2Finished && (
                    <Button variant="secondary" size="sm" onClick={addMaterialPhase2Row}>
                      <Plus className="h-4 w-4" />
                      Row
                    </Button>
                  )}
                </div>

                <div className="max-h-[620px] overflow-auto border bg-background">
                  <Table className={SHEET_TABLE_CLASS}>
                    <TableHeader className={SHEET_HEADER_CLASS}>
                      <TableRow>
                        <TableHead className={SHEET_ROW_HEADER_CLASS} />
                        <TableHead className={`${SHEET_HEAD_CLASS} w-20`}>Review</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-16`}>SL.NO.</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} min-w-72`}>Stock type</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Width</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Length</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Thk</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>UOM</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-36`}>Planned qty</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-32`}>Available</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-32`}>Reserved</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-32`}>Shortage</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-40`}>Suggested purchase</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-40`}>Vendor</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-32`}>Lead days</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-40`}>Material cost</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-36`}>Priority</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-28`}>Source rows</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} min-w-96`}>Notes / planner review</TableHead>
                        <TableHead className={`${SHEET_HEAD_CLASS} w-20`}>Delete</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {materialPlan.rows.map((row, index) => (
                        <TableRow key={`${row.sl_no}-${row.type}-${index}`} className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/10">
                          <TableCell className={SHEET_ROW_HEADER_CLASS}>{index + 1}</TableCell>
                          <TableCell className={`${SHEET_CELL_CLASS} text-center`}>
                            <input
                              type="checkbox"
                              checked={row.reviewed}
                              onChange={(event) => updatePlanRow(index, { reviewed: event.target.checked })}
                              disabled={!canEditMaterialPhase2 || materialPhase2Finished}
                              aria-label={`Mark row ${index + 1} reviewed`}
                            />
                          </TableCell>
                          <TableCell className={SHEET_CELL_CLASS}>{row.sl_no}</TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-72 font-medium`} value={row.type} onChange={(event) => updatePlanRow(index, { type: event.target.value })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} type="number" value={getString(row.width_mm)} onChange={(event) => updatePlanRow(index, { width_mm: Number(event.target.value) || null })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} value={getString(row.length_mm)} onChange={(event) => updatePlanRow(index, { length_mm: event.target.value.toUpperCase() === "COIL" ? "COIL" : Number(event.target.value) || null })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} type="number" value={getString(row.thickness_mm)} onChange={(event) => updatePlanRow(index, { thickness_mm: Number(event.target.value) || null })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}>
                            <Select
                              value={row.purchase_uom}
                              disabled={!canEditMaterialPhase2 || materialPhase2Finished}
                              onValueChange={(value) => {
                                const purchaseUom = value as MaterialPhase2Row["purchase_uom"];
                                const required = materialPhase2RequiredQty(row);
                                updatePlanRow(index, {
                                  purchase_uom: purchaseUom,
                                  reqd_qty_sheets: purchaseUom === "SHEETS" ? required : null,
                                  reqd_qty_kg: purchaseUom === "SHEETS" ? null : required,
                                });
                              }}
                            >
                              <SelectTrigger className={`${SHEET_SELECT_CLASS} w-24`}><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {MATERIAL_PHASE2_UOMS.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell className={SHEET_CELL_CLASS}>
                            <Input
                              className={`${SHEET_INPUT_CLASS} w-28`}
                              type="number"
                              value={getString(materialPhase2RequiredQty(row))}
                              onChange={(event) => {
                                const quantity = Number(event.target.value) || 0;
                                updatePlanRow(index, row.purchase_uom === "SHEETS" ? { reqd_qty_sheets: quantity, reqd_qty_kg: null } : { reqd_qty_sheets: null, reqd_qty_kg: quantity });
                              }}
                              disabled={!canEditMaterialPhase2 || materialPhase2Finished}
                            />
                          </TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-28`} type="number" value={getString(row.available_qty)} onChange={(event) => updatePlanRow(index, { available_qty: Number(event.target.value) })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-28`} type="number" value={getString(row.reserved_qty)} onChange={(event) => updatePlanRow(index, { reserved_qty: Number(event.target.value) })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={`${SHEET_CELL_CLASS} ${row.shortage_qty > 0 ? "font-medium text-red-600" : ""}`}>{row.shortage_qty.toFixed(2)}</TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-32`} type="number" value={getString(row.suggested_purchase_qty)} onChange={(event) => updatePlanRow(index, { suggested_purchase_qty: Number(event.target.value) })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-36`} value={row.preferred_vendor} onChange={(event) => updatePlanRow(index, { preferred_vendor: event.target.value })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-24`} type="number" value={getString(row.lead_time_days)} onChange={(event) => updatePlanRow(index, { lead_time_days: Number(event.target.value) })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-32`} type="number" value={getString(row.estimated_material_cost)} onChange={(event) => updatePlanRow(index, { estimated_material_cost: Number(event.target.value) })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={SHEET_CELL_CLASS}>
                            <Select value={row.production_priority} onValueChange={(value) => updatePlanRow(index, { production_priority: value as MaterialPlan["rows"][number]["production_priority"] })} disabled={!canEditMaterialPhase2 || materialPhase2Finished}>
                              <SelectTrigger className={`${SHEET_SELECT_CLASS} w-32`}><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="low">Low</SelectItem>
                                <SelectItem value="normal">Normal</SelectItem>
                                <SelectItem value="high">High</SelectItem>
                                <SelectItem value="urgent">Urgent</SelectItem>
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell className={SHEET_CELL_CLASS}><Input className={`${SHEET_INPUT_CLASS} w-20`} type="number" value={getString(row.source_count)} onChange={(event) => updatePlanRow(index, { source_count: Number(event.target.value) || 0 })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} /></TableCell>
                          <TableCell className={`${SHEET_CELL_CLASS} align-top`}>
                            <Input className={`${SHEET_INPUT_CLASS} mb-1 w-96`} value={row.notes} onChange={(event) => updatePlanRow(index, { notes: event.target.value })} disabled={!canEditMaterialPhase2 || materialPhase2Finished} />
                            <textarea
                              className={SHEET_TEXTAREA_CLASS}
                              value={row.planner_notes}
                              onChange={(event) => updatePlanRow(index, { planner_notes: event.target.value })}
                              placeholder="Planner notes"
                              disabled={!canEditMaterialPhase2 || materialPhase2Finished}
                            />
                          </TableCell>
                          <TableCell className={`${SHEET_CELL_CLASS} text-center`}>
                            {canEditMaterialPhase2 && !materialPhase2Finished && (
                              <Button variant="ghost" size="icon" onClick={() => deleteMaterialPhase2Row(index)} aria-label={`Delete phase 2 row ${index + 1}`}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                <details className="rounded-md border p-3">
                  <summary className="cursor-pointer text-sm font-medium">
                    <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4" />Assumptions and review basis</span>
                  </summary>
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

      {isQuotationSection && (
        <Card className="overflow-hidden">
          <CardHeader className="space-y-3 border-b px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md border bg-background">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="space-y-0.5">
                  <CardTitle className="text-base">Quotation preparation</CardTitle>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>{quote.customer || quote.quote_no || "Untitled enquiry"}</span>
                    <Badge variant={quotationStageBadgeVariant(quotationStage)}>{quotationStageMeta.label}</Badge>
                    <Badge variant={approvalBadgeVariant(approval.status)}>{approval.status}</Badge>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" size="sm" onClick={closeQuotationScreen}>
                  <RotateCcw className="h-4 w-4" />
                  Back to enquiry
                </Button>
                {canEditQuotation && (
                  <>
                    <Button size="sm" onClick={() => exportCurrent("pdf")} disabled={!canExportFinal}>
                      {exporting === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                      PDF
                    </Button>
                  </>
                )}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="secondary" size="sm">
                      <MoreHorizontal className="h-4 w-4" />
                      More
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => exportCurrent("pdf", "preview")} disabled={!canExportQuotes}>
                      <FileText className="mr-2 h-4 w-4" />
                      Preview PDF
                    </DropdownMenuItem>
                    {canEditQuotation && <DropdownMenuItem onSelect={() => exportCurrent("xlsx")} disabled={!canExportFinal}>
                      <FileSpreadsheet className="mr-2 h-4 w-4" />
                      Download Excel
                    </DropdownMenuItem>}
                    {canEditQuotation && <DropdownMenuItem onSelect={markSent} disabled={approval.status !== "approved" || quote.stage === "sent"}>
                      <Send className="mr-2 h-4 w-4" />
                      Mark as sent
                    </DropdownMenuItem>}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 p-3">
            <div className="space-y-3">
              <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
                <div className="rounded-md border bg-background p-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                        <Badge variant={quotationStageBadgeVariant(quotationStage)}>{quotationStageIndex + 1}. {quotationStageMeta.label}</Badge>
                        <Badge variant={quote.customer && quote.project_ref ? "secondary" : "outline"}>{quote.customer && quote.project_ref ? "Context ready" : "Needs context"}</Badge>
                        <Badge variant={approvalBadgeVariant(approval.status)}>{approval.status}</Badge>
                      </div>
                      <div className="mt-2 truncate text-sm">
                        {quote.customer || "Customer not added"}
                        <span className="text-muted-foreground"> / {quote.project_ref || getString(qd.quote_no) || quote.id}</span>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{quotationStageMeta.description}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="secondary" size="sm" onClick={() => setQuotationSetupOpen(true)}>
                        <SlidersHorizontal className="h-4 w-4" />
                        Edit setup
                      </Button>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <CompactMetric icon={<FileText className="h-3.5 w-3.5" />} label="Rows" value={items.length} />
                    <CompactMetric icon={<FileSpreadsheet className="h-3.5 w-3.5" />} label="Qty" value={totalQuantityLabel} tone="ready" />
                    <CompactMetric icon={<Download className="h-3.5 w-3.5" />} label="Total" value={`${grandTotal.toFixed(2)} ${currency}`} tone="ready" />
                    <CompactMetric
                      icon={<ShieldCheck className="h-3.5 w-3.5" />}
                      label="Approval"
                      value={approval.status}
                      tone={pricingSummary.approvalRequired ? "check" : approval.status === "approved" ? "ready" : "neutral"}
                    />
                  </div>
                </div>

                <details className="rounded-md border bg-background">
                  <summary className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2">
                    <span className="text-sm font-medium">Step checklist</span>
                    <span className="text-xs text-muted-foreground">{quotationChecklist.filter((item) => item.done).length}/{quotationChecklist.length} done</span>
                  </summary>
                  <div className="grid gap-2 border-t p-3">
                    {quotationChecklist.map((item) => (
                      <div key={item.label} className="flex items-center gap-2 rounded-md border bg-muted/20 px-2 py-1.5 text-xs">
                        {item.done ? <Check className="h-4 w-4 text-emerald-600" /> : <Circle className="h-4 w-4 text-muted-foreground" />}
                        <span className={item.done ? "text-foreground" : "text-muted-foreground"}>{item.label}</span>
                      </div>
                    ))}
                  </div>
                </details>
              </div>

              <Tabs defaultValue="pricing" className="min-w-0 space-y-3">
                <TabsList className="grid h-auto grid-cols-2 md:grid-cols-5">
                  <TabsTrigger value="pricing" className="gap-2"><SlidersHorizontal className="h-4 w-4" />Pricing</TabsTrigger>
                  <TabsTrigger value="items" className="gap-2"><FileSpreadsheet className="h-4 w-4" />Items</TabsTrigger>
                  <TabsTrigger value="terms" className="gap-2"><ListFilter className="h-4 w-4" />Terms</TabsTrigger>
                  <TabsTrigger value="approval" className="gap-2"><ShieldCheck className="h-4 w-4" />Approval</TabsTrigger>
                  <TabsTrigger value="setup" className="gap-2"><FileText className="h-4 w-4" />Setup</TabsTrigger>
                </TabsList>

                <TabsContent value="setup" className="space-y-3">
                  <div className="rounded-md border bg-background p-3">
                    <div className="mb-3 flex items-center gap-2 text-sm font-medium"><FileText className="h-4 w-4" />Quotation identity</div>
                    <div className="grid gap-3 md:grid-cols-4">
                      <Field label="Quote no" value={getString(qd.quote_no)} onChange={(value) => updateQd("quote_no", value)} disabled={!canEditQuotation} />
                      <Field label="Quote date" value={getString(qd.quote_date)} onChange={(value) => updateQd("quote_date", value)} disabled={!canEditQuotation} />
                      <Field label="Revision no" value={getString(qd.rev_no)} onChange={(value) => updateQd("rev_no", value)} disabled={!canEditQuotation} />
                      <Field label="Revision date" value={getString(qd.rev_date)} onChange={(value) => updateQd("rev_date", value)} disabled={!canEditQuotation} />
                    </div>
                  </div>

                  <div className="grid gap-3 rounded-md border bg-muted/20 p-3 md:grid-cols-2">
                    <label className="flex items-start gap-3 text-sm">
                      <input className="mt-1" type="checkbox" checked={Boolean(qd.include_customer_sl_no)} onChange={(event) => updateQd("include_customer_sl_no", event.target.checked)} disabled={!canEditQuotation} />
                      <span>
                        <span className="block font-medium">Use customer SL No. in quotation PDF</span>
                        <span className="block text-xs text-muted-foreground">When enabled, customer SL No. replaces the default serial number.</span>
                      </span>
                    </label>
                    <label className="flex items-start gap-3 text-sm">
                      <input className="mt-1" type="checkbox" checked={Boolean(qd.include_customer_item_code)} onChange={(event) => updateQd("include_customer_item_code", event.target.checked)} disabled={!canEditQuotation} />
                      <span>
                        <span className="block font-medium">Add customer item code to quotation PDF</span>
                        <span className="block text-xs text-muted-foreground">Keep disabled when the customer code is only for internal matching.</span>
                      </span>
                    </label>
                  </div>

                  <div className="rounded-md border bg-background p-3">
                    <div className="mb-3 flex items-center gap-2 text-sm font-medium"><FileText className="h-4 w-4" />Buyer details</div>
                    <div className="grid gap-3 lg:grid-cols-[1.1fr_1fr]">
                      <div className="grid gap-3 md:grid-cols-2">
                        <Field label="Buyer name" value={getString(qd.buyer_name)} onChange={(value) => updateQd("buyer_name", value)} disabled={!canAddDetails} />
                        <Field label="PIN code" value={getString(qd.buyer_pin_code)} onChange={(value) => updateQd("buyer_pin_code", value)} disabled={!canAddDetails} />
                        <Field label="Address line 1" value={getString(qd.buyer_address_line1)} onChange={(value) => updateQd("buyer_address_line1", value)} disabled={!canAddDetails} />
                        <Field label="Address line 2" value={getString(qd.buyer_address_line2)} onChange={(value) => updateQd("buyer_address_line2", value)} disabled={!canAddDetails} />
                        <Field label="City" value={getString(qd.buyer_city)} onChange={(value) => updateQd("buyer_city", value)} disabled={!canAddDetails} />
                        <Field label="State" value={getString(qd.buyer_state)} onChange={(value) => updateQd("buyer_state", value)} disabled={!canAddDetails} />
                        <Field label="Country" value={getString(qd.buyer_country)} onChange={(value) => updateQd("buyer_country", value)} disabled={!canAddDetails} />
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <Field label="Customer enquiry no" value={getString(qd.customer_enq_no)} onChange={(value) => updateQd("customer_enq_no", value)} disabled={!canAddDetails} />
                        <Field label="Sender's name" value={getString(qd.attention)} onChange={(value) => updateQd("attention", value)} disabled={!canAddDetails} />
                        <Field label="Designation" value={getString(qd.designation)} onChange={(value) => updateQd("designation", value)} disabled={!canAddDetails} />
                        <Field label="Mobile number" value={getString(qd.mobile_no || qd.contact_no)} onChange={(value) => updateQd("mobile_no", value)} disabled={!canAddDetails} />
                        <Field label="Telephone number" value={getString(qd.telephone_no)} onChange={(value) => updateQd("telephone_no", value)} disabled={!canAddDetails} />
                        <Field label="Email" value={getString(qd.email)} onChange={(value) => updateQd("email", value)} disabled={!canAddDetails} />
                      </div>
                    </div>
                  </div>

                </TabsContent>

                <TabsContent value="pricing" className="space-y-3">
                  <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-5">
                    <div className="rounded-md border bg-background p-3"><div className="text-xs text-muted-foreground">Subtotal</div><div className="text-lg font-semibold">{subtotal.toFixed(2)}</div></div>
                    <div className="rounded-md border bg-background p-3"><div className="text-xs text-muted-foreground">Approved discount</div><div className="text-lg font-semibold">{discount.toFixed(2)}</div></div>
                    <div className="rounded-md border bg-background p-3"><div className="text-xs text-muted-foreground">GST</div><div className="text-lg font-semibold">{gst.toFixed(2)}</div></div>
                    <div className="rounded-md border bg-background p-3"><div className="text-xs text-muted-foreground">Grand total</div><div className="text-lg font-semibold">{grandTotal.toFixed(2)}</div></div>
                    <div className="rounded-md border bg-background p-3"><div className="text-xs text-muted-foreground">Cost total</div><div className="text-lg font-semibold">{pricingSummary.costTotal.toFixed(2)}</div></div>
                  </div>

                  <div className="rounded-md border bg-background p-3">
                    <div className="mb-3 flex items-center gap-2 text-sm font-medium"><SlidersHorizontal className="h-4 w-4" />Commercial controls</div>
                    <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
                      <div className="space-y-1.5">
                        <Label>Currency</Label>
                        <Select value={currency} onValueChange={(value) => updateQd("currency", value)} disabled={!canEditQuotation}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>{currencies.map((cur) => <SelectItem key={cur} value={cur}>{cur}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                      <Field label="FX rate" value={getString(qd.fx_rate)} onChange={(value) => updateQd("fx_rate", Number(value))} type="number" disabled={!canEditQuotation} />
                      <Field label="Approved discount %" value={getString(qd.discount_pct)} onChange={(value) => updateQd("discount_pct", Number(value))} type="number" disabled={!canEditQuotation} />
                      <div className="space-y-1.5">
                        <Label>GST type</Label>
                        <Select value={getString(qd.gst_type || "IGST")} onValueChange={(value) => updateQd("gst_type", value)} disabled={currency !== "INR" || !canEditQuotation}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="IGST">IGST</SelectItem>
                            <SelectItem value="CGST+SGST">CGST+SGST</SelectItem>
                            <SelectItem value="UGST">UGST</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <Field label="GST %" value={getString(qd.gst_pct)} onChange={(value) => updateQd("gst_pct", Number(value))} type="number" disabled={!canEditQuotation} />
                    </div>
                  </div>

                  {pricingSummary.approvalRequired && (
                    <div className="rounded-md border border-amber-200 bg-amber-50/70 p-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/25 dark:text-amber-100">
                      <div className="font-medium">Commercial approval required</div>
                      <ul className="mt-2 space-y-1 text-xs">
                        {pricingSummary.approvalReasons.map((reason) => <li key={reason}>- {reason}</li>)}
                      </ul>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="items" className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm">
                    <div className="text-muted-foreground">Showing {items.length ? finalPageStartIndex + 1 : 0}-{finalPageEndIndex} of {items.length} quotation row(s).</div>
                    <div className="flex items-center gap-2">
                      <Button variant="secondary" size="sm" onClick={() => setFinalPage((page) => Math.max(0, page - 1))} disabled={safeFinalPage <= 0}>Previous</Button>
                      <span className="text-xs text-muted-foreground">Page {safeFinalPage + 1} of {finalPageCount}</span>
                      <Button variant="secondary" size="sm" onClick={() => setFinalPage((page) => Math.min(finalPageCount - 1, page + 1))} disabled={safeFinalPage >= finalPageCount - 1}>Next</Button>
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
                              <TableCell><Input className="w-24" value={getString(item.customer_sl_no)} onChange={(event) => updateItem(index, "customer_sl_no", event.target.value)} disabled={!canEditLineItems} /></TableCell>
                              <TableCell><Input className="w-36" value={getString(item.customer_item_code)} onChange={(event) => updateItem(index, "customer_item_code", event.target.value)} disabled={!canEditLineItems} /></TableCell>
                              <TableCell className="min-w-96 text-xs">
                                {item.status === "regret" ? (
                                  "REGRET - CANNOT PRODUCE"
                                ) : (
                                  <div className="space-y-1">
                                    <div>{getString(item.raw_description || item.ggpl_description)}</div>
                                    {item.ggpl_description && item.ggpl_description !== item.raw_description && <div className="text-muted-foreground">GGPL: {getString(item.ggpl_description)}</div>}
                                  </div>
                                )}
                              </TableCell>
                              <TableCell><Input className="w-24" type="number" value={getString(item.quantity)} onChange={(event) => updateItem(index, "quantity", event.target.value)} disabled={!canEditLineItems} /></TableCell>
                              <TableCell>{getString(item.uom || "NOS")}</TableCell>
                              <TableCell>
                                <Input className="w-28" type="number" value={getString(costPrices[index] ?? 0)} disabled={!canEditQuotation} onChange={(event) => {
                                  const next = [...costPrices];
                                  next[index] = Number(event.target.value);
                                  updateQd("cost_prices", next);
                                }} />
                              </TableCell>
                              <TableCell>
                                <Input className="w-28" type="number" value={getString(targetMargins[index] ?? 0)} disabled={!canEditQuotation} onChange={(event) => {
                                  const next = [...targetMargins];
                                  next[index] = Number(event.target.value);
                                  updateQd("target_margins_pct", next);
                                }} />
                              </TableCell>
                              <TableCell>
                                <Input className="w-32" type="number" value={getString(price)} disabled={!canEditQuotation} onChange={(event) => {
                                  const next = [...unitPrices];
                                  next[index] = Number(event.target.value);
                                  updateQd("unit_prices", next);
                                }} />
                              </TableCell>
                              <TableCell>{converted.toFixed(2)}</TableCell>
                              <TableCell className={pricingLine?.marginPct !== null && pricingLine?.marginPct !== undefined && pricingLine.marginPct < 0 ? "text-red-600" : ""}>
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
                </TabsContent>

                <TabsContent value="terms" className="space-y-3">
                  <div className="rounded-md border bg-background p-3">
                    <div className="mb-3 flex items-center gap-2 text-sm font-medium"><ListFilter className="h-4 w-4" />Commercial and technical terms</div>
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
                          disabled={!canEditQuotation && key !== "technical_notes"}
                        />
                      ))}
                    </div>
                    <div className="mt-4 grid gap-3">
                      <Field
                        label="Technical Deviation / Remarks"
                        value={getString(qd.technical_deviation_remarks)}
                        onChange={(value) => updateQd("technical_deviation_remarks", value)}
                        textarea
                        disabled={!canEditQuotation}
                      />
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="approval" className="space-y-3">
                  <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
                    <div className="rounded-md border bg-background p-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 text-sm font-medium"><ShieldCheck className="h-4 w-4" />Approval workflow</div>
                          <div className="mt-1 text-xs text-muted-foreground">Current user: {currentUser.name} ({roleLabels[currentUser.role]})</div>
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
                            {qualityReport.risks.slice(0, 8).map((risk) => (
                              <div key={`${risk.title}-${risk.detail}`} className="text-xs">
                                <span className={risk.severity === "high" ? "font-medium text-red-600" : "font-medium text-amber-700"}>{risk.title}</span>
                                <span className="text-muted-foreground"> - {risk.detail}</span>
                                {risk.rows?.length ? <span className="text-muted-foreground"> Rows {risk.rows.slice(0, 8).join(", ")}</span> : null}
                              </div>
                            ))}
                            {qualityReport.risks.length > 8 && <div className="text-xs text-muted-foreground">+ {qualityReport.risks.length - 8} more risk checks</div>}
                          </div>
                        </div>
                      )}
                      {approval.requested_by && <div className="mt-2 text-xs text-muted-foreground">Requested by {approval.requested_by}{approval.requested_at ? ` on ${new Date(approval.requested_at).toLocaleString()}` : ""}</div>}
                      {approval.decided_by && <div className="mt-1 text-xs text-muted-foreground">{approval.status === "approved" ? "Approved" : "Rejected"} by {approval.decided_by}{approval.decided_at ? ` on ${new Date(approval.decided_at).toLocaleString()}` : ""}</div>}
                      {approval.comments && <div className="mt-2 rounded-md bg-muted/40 p-2 text-xs">{approval.comments}</div>}
                      {approval.required_changes && <div className="mt-2 rounded-md bg-muted/40 p-2 text-xs">Required changes: {approval.required_changes}</div>}
                    </div>

                    <div className="rounded-md border bg-background p-3">
                      <Label>Approval comments</Label>
                      <textarea
                        className="mt-1 min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                        value={approvalComment}
                        onChange={(event) => setApprovalComment(event.target.value)}
                        placeholder="Reason, exception approval, price override, or rejection comments"
                        disabled={!canEditQuotation}
                      />
                      <div className="mt-3 flex flex-wrap gap-2">
                        {canEditQuotation && (
                          <>
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
                          </>
                        )}
                      </div>
                      {!canApprove && <div className="mt-2 text-xs text-muted-foreground">Only admin or approver users can approve or reject.</div>}
                      {!canExportFinal && <div className="mt-1 text-xs text-muted-foreground">Quotation export is locked only for commercial approval items such as margin or discount exceptions.</div>}
                    </div>
                  </div>
                </TabsContent>
              </Tabs>

              <Dialog open={quotationSetupOpen} onOpenChange={setQuotationSetupOpen}>
                <DialogContent className="max-h-[90vh] max-w-5xl overflow-auto">
                  <DialogHeader>
                    <DialogTitle>Quotation setup</DialogTitle>
                    <DialogDescription>Set customer context, workflow stage, sales representative, and notes.</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="grid gap-3 lg:grid-cols-[1fr_1fr_minmax(240px,0.75fr)] lg:items-end">
                      <Field label="Customer" value={quote.customer} onChange={(value) => updateQuoteDraft({ customer: value })} disabled={!canAddDetails} />
                      <Field label="Project / PO reference" value={quote.project_ref} onChange={(value) => updateQuoteDraft({ project_ref: value })} disabled={!canAddDetails} />
                      <div className="space-y-1.5">
                        <Label>Quotation stage</Label>
                        <Select value={quotationStage} onValueChange={(value) => setQuotationStage(value as QuotationStageId)} disabled={!canEditWorkflow}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {QUOTATION_STAGES.map((stage, index) => (
                              <SelectItem key={stage.id} value={stage.id}>{index + 1}. {stage.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="grid gap-3 border-t pt-4 md:grid-cols-2 xl:grid-cols-4">
                      <div className="space-y-1.5">
                        <Label>Sales rep</Label>
                        <Select
                          value={salesRepUsers.some((user) => user.id === getString(qd.sales_rep_user_id)) ? getString(qd.sales_rep_user_id) : CUSTOM_SALES_REP_VALUE}
                          onValueChange={selectSalesRep}
                          disabled={!canEditQuotation}
                        >
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {salesRepUsers.map((user) => (
                              <SelectItem key={user.id} value={user.id}>
                                {user.name} - {roleLabels[user.role]}
                              </SelectItem>
                            ))}
                            <SelectItem value={CUSTOM_SALES_REP_VALUE}>{quotationSalesRepLabel}</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <Field label="Rep designation" value={getString(qd.rep_designation)} onChange={(value) => updateQd("rep_designation", value)} disabled={!canEditQuotation} />
                      <Field label="Rep contact" value={getString(qd.rep_contact)} onChange={(value) => updateQd("rep_contact", value)} disabled={!canEditQuotation} />
                      <Field label="Rep email" value={getString(qd.rep_email)} onChange={(value) => updateQd("rep_email", value)} disabled={!canEditQuotation} />
                    </div>

                    <div className="border-t pt-4">
                      <Field
                        label="Sales notes / extra details"
                        value={getString(quote.stage_meta?.sales_notes)}
                        onChange={(value) => updateQuoteDraft({ stage_meta: { ...(quote.stage_meta ?? {}), sales_notes: value } })}
                        textarea
                        disabled={!canAddDetails}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="secondary" onClick={() => setQuotationSetupOpen(false)}>Close</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </CardContent>
        </Card>
      )}

      {canSaveProgress && (
        <div className="fixed bottom-4 right-28 z-50 sm:right-32">
          <Button
            className="h-10 shadow-none"
            onClick={() => saveCurrentProgress()}
            disabled={saveProgressDisabled}
            title={saveProgressTitle}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save
            <span className="hidden rounded border border-primary-foreground/30 px-1.5 py-0.5 text-[10px] opacity-80 sm:inline">Ctrl+S</span>
          </Button>
        </div>
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
