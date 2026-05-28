"use client";

import type { AppUser } from "@/lib/auth/users";
import type { AccessSettings } from "@/lib/auth/access-control";

export type QuoteStage = "initial" | "review" | "quote_prep" | "repricing" | "sent" | "po";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export type GasketItem = Record<string, unknown> & {
  line_no?: number | null;
  customer_sl_no?: string | number | null;
  customer_item_code?: string | null;
  clarification_note?: string | null;
  drawing_required?: boolean | null;
  is_non_gasket?: boolean | null;
  duplicate_group_id?: string | null;
  quantity?: number | null;
  uom?: string;
  raw_description?: string;
  gasket_type?: string;
  size?: string | null;
  rating?: string | null;
  moc?: string | null;
  face_type?: string | null;
  thickness_mm?: number | null;
  standard?: string | null;
  sw_winding_material?: string | null;
  sw_filler?: string | null;
  sw_inner_ring?: string | null;
  sw_outer_ring?: string | null;
  rtj_groove_type?: string | null;
  rtj_hardness_bhn?: number | null;
  ggpl_description?: string;
  status?: string | null;
  status_source?: string | null;
  flags?: string[];
  regret?: boolean;
};

export type Quote = {
  id: string;
  org_id: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  version: number;
  quote_no: string;
  customer: string;
  project_ref: string;
  custom_label: string;
  items: GasketItem[];
  quote_data: Record<string, unknown>;
  stage: QuoteStage;
  stage_meta: Record<string, unknown>;
  stage_history: Array<{
    stage: QuoteStage;
    at: string;
    reason: string;
    metadata: Record<string, unknown>;
    user_id: string;
  }>;
  n_items: number;
  n_ready: number;
  n_check: number;
  n_missing: number;
  n_regret: number;
};

export type VendorEnquiryStatus = "draft" | "sent" | "replied" | "selected" | "rejected";

export type VendorEnquiry = {
  id: string;
  quote_id: string;
  quote_no: string;
  customer: string;
  vendor_name: string;
  contact: string;
  material_group: string;
  quantity: number;
  required_date: string;
  status: VendorEnquiryStatus;
  quoted_price: number;
  lead_time_days: number;
  remarks: string;
  source: "quote_items" | "material_plan";
  created_at: string;
  updated_at: string;
};

export type JobRead = {
  id: string;
  org_id: string;
  status: JobStatus;
  source_type: string;
  quote_id: string | null;
  progress: number;
  message: string;
  items: GasketItem[];
  skipped_count: number;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type JobStatusRead = {
  id: string;
  status: JobStatus;
  source_type: string;
  quote_id: string | null;
  progress: number;
  message: string;
  parsed_count: number;
  skipped_count: number;
  error: string | null;
  updated_at: string;
};

export type SignedUrl = {
  signed_url: string;
  filename: string;
  content_type: string;
};

export type OutlookLinkedMessage = {
  mailbox_user: string;
  message_id: string;
  conversation_id: string;
  internet_message_id: string;
  web_link: string;
  subject: string;
  from_name: string;
  from_email: string;
  received_at: string;
  sent_at: string;
  has_attachments: boolean;
  linked_at: string;
  linked_by: string;
};

export type DashboardMetrics = {
  total_quotes: number;
  items_processed: number;
  pending_review: number;
  quotes_sent: number;
  converted_to_po: number;
  conversion_rate: number;
  win_rate: number;
  avg_time_to_sent_days: number;
  total_quote_value: number;
  stage_counts: Record<string, number>;
  gasket_type_distribution: Record<string, number>;
  new_enquiries_today?: number;
  clarification_required?: number;
  delayed_enquiries?: number;
  pending_approval?: number;
  high_value_enquiries?: number;
  owner_workload?: Array<{ owner_id: string; owner_name: string; open_count: number; delayed_count: number; value: number }>;
  due_today?: number;
  open_quote_value?: number;
  generated_at?: string;
};

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const API_TARGET = API_BASE || "the same-origin /api/v1 proxy";
const ORG_ID = process.env.NEXT_PUBLIC_ORG_ID ?? "local-org";

export const ITEM_FIELDS = [
  "line_no",
  "customer_sl_no",
  "customer_item_code",
  "clarification_note",
  "drawing_required",
  "is_non_gasket",
  "duplicate_group_id",
  "quantity",
  "uom",
  "raw_description",
  "is_gasket",
  "size",
  "size_type",
  "od_mm",
  "id_mm",
  "rating",
  "gasket_type",
  "moc",
  "face_type",
  "thickness_mm",
  "standard",
  "special",
  "confidence",
  "sw_winding_material",
  "sw_filler",
  "sw_inner_ring",
  "sw_outer_ring",
  "rtj_groove_type",
  "rtj_hardness_bhn",
  "rtj_hardness_spec",
  "ring_no",
  "kamm_core_material",
  "kamm_surface_material",
  "kamm_covering_layer",
  "kamm_rib",
  "kamm_core_thk",
  "kamm_integral_outer_ring",
  "dji_filler",
  "dji_rib",
  "dji_face_type",
  "dji_id_first",
  "isk_style",
  "isk_type",
  "isk_fire_safety",
  "isk_gasket_material",
  "isk_core_material",
  "isk_sleeve_material",
  "isk_washer_material",
  "isk_primary_seal",
  "isk_secondary_seal",
  "isk_insulating_washer",
  "isk_standard_explicit",
  "ggpl_description",
  "status",
  "flags",
  "size_norm",
] as const;

export const BULK_EDIT_FIELDS = [
  "gasket_type",
  "moc",
  "rating",
  "face_type",
  "rtj_groove_type",
  "thickness_mm",
  "rtj_hardness_bhn",
  "uom",
  "sw_winding_material",
  "sw_filler",
  "sw_outer_ring",
  "sw_inner_ring",
  "standard",
] as const;

function headers(extra?: HeadersInit): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Org-Id": ORG_ID,
    ...extra,
  };
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status text.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, { credentials: "include", ...init });
  } catch (error) {
    const suffix = error instanceof Error && error.message ? ` (${error.message})` : "";
    throw new Error(`Could not reach the API through ${API_TARGET}. Start the FastAPI server or set NEXT_PUBLIC_API_BASE_URL.${suffix}`);
  }
}

export async function listQuotes(): Promise<Quote[]> {
  return parse<Quote[]>(
    await apiFetch(`${API_BASE}/api/v1/quotes?summary=true`, { headers: headers({ "Content-Type": "application/json" }) }),
  );
}

export async function getQuote(id: string): Promise<Quote> {
  return parse<Quote>(await apiFetch(`${API_BASE}/api/v1/quotes/${id}`, { headers: headers() }));
}

export async function createQuote(payload: Partial<Quote>): Promise<Quote> {
  return parse<Quote>(
    await apiFetch(`${API_BASE}/api/v1/quotes`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload),
    }),
  );
}

export async function patchQuote(id: string, payload: Partial<Quote>): Promise<Quote> {
  return parse<Quote>(
    await apiFetch(`${API_BASE}/api/v1/quotes/${id}`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify(payload),
    }),
  );
}

export async function deleteQuote(id: string): Promise<void> {
  await parse<{ message: string }>(
    await apiFetch(`${API_BASE}/api/v1/quotes/${id}`, {
      method: "DELETE",
      headers: headers(),
    }),
  );
}

export async function bulkRecompute(id: string, rows: GasketItem[]): Promise<GasketItem[]> {
  return parse<GasketItem[]>(
    await apiFetch(`${API_BASE}/api/v1/quotes/${id}/items/bulk-recompute`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ rows }),
    }),
  );
}

export async function reprocessText(id: string, descriptions: string[]): Promise<GasketItem[]> {
  return parse<GasketItem[]>(
    await apiFetch(`${API_BASE}/api/v1/quotes/${id}/items/reprocess-text`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ descriptions, source_type: "email" }),
    }),
  );
}

export async function rfiDraft(id: string): Promise<{ text: string; groups: Record<string, number[]> }> {
  return parse(await apiFetch(`${API_BASE}/api/v1/quotes/${id}/rfi-draft`, { method: "POST", headers: headers() }));
}

export async function createExtraction(params: {
  quoteId: string;
  sourceType: "email" | "excel";
  text?: string;
  file?: File | null;
  customer: string;
  projectRef: string;
}): Promise<{ job_id: string; status: JobStatus }> {
  if (params.file) {
    const form = new FormData();
    form.set("file", params.file);
    form.set("source_type", params.sourceType);
    form.set("quote_id", params.quoteId);
    form.set("customer", params.customer);
    form.set("project_ref", params.projectRef);
    return parse(
      await apiFetch(`${API_BASE}/api/v1/extractions`, {
        method: "POST",
        headers: { "X-Org-Id": ORG_ID },
        body: form,
      }),
    );
  }
  return parse(
    await apiFetch(`${API_BASE}/api/v1/extractions`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        source_type: params.sourceType,
        text: params.text,
        quote_id: params.quoteId,
        customer: params.customer,
        project_ref: params.projectRef,
      }),
    }),
  );
}

export async function getJob(id: string): Promise<JobRead> {
  return parse<JobRead>(await apiFetch(`${API_BASE}/api/v1/jobs/${id}`, { headers: headers() }));
}

export async function getJobStatus(id: string): Promise<JobStatusRead> {
  return parse<JobStatusRead>(await apiFetch(`${API_BASE}/api/v1/jobs/${id}/status`, { headers: headers() }));
}

export async function exportQuote(id: string, type: "pdf" | "xlsx"): Promise<SignedUrl> {
  return parse<SignedUrl>(
    await apiFetch(`${API_BASE}/api/v1/quotes/${id}/exports/${type}`, {
      method: "POST",
      headers: headers(),
    }),
  );
}

export async function advanceQuoteStage(
  id: string,
  stage: QuoteStage,
  reason: string,
  metadata: Record<string, unknown>,
): Promise<Quote> {
  return parse<Quote>(
    await apiFetch(`${API_BASE}/api/v1/quotes/${id}/stage`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ stage, reason, metadata }),
    }),
  );
}

export async function resolveOutlookMessage(params: { mailboxUser: string; messageId: string }): Promise<OutlookLinkedMessage> {
  return parse<OutlookLinkedMessage>(
    await apiFetch(`${API_BASE}/api/v1/outlook/messages/resolve`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ mailbox_user: params.mailboxUser, message_id: params.messageId }),
    }),
  );
}

export async function listOutlookThreadMessages(params: { mailboxUser: string; conversationId: string }): Promise<OutlookLinkedMessage[]> {
  return parse<OutlookLinkedMessage[]>(
    await apiFetch(`${API_BASE}/api/v1/outlook/threads/messages`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ mailbox_user: params.mailboxUser, conversation_id: params.conversationId }),
    }),
  );
}

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  return parse<DashboardMetrics>(await apiFetch(`${API_BASE}/api/v1/dashboard/metrics`, { headers: headers() }));
}

export async function convertUnits(
  type: string,
  value: number,
  fromUnit: string,
  toUnit: string,
): Promise<{ result: number; display: string }> {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/converter/${type}`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ value, from_unit: fromUnit, to_unit: toUnit }),
    }),
  );
}

export async function chatCompletion(messages: Array<{ role: string; content: string }>) {
  return parse<{ message: { role: string; content: string } }>(
    await apiFetch(`${API_BASE}/api/v1/chat/completions`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ messages }),
    }),
  );
}

export async function listAppUsers(): Promise<AppUser[]> {
  return parse<AppUser[]>(await apiFetch(`${API_BASE}/api/v1/users`, { headers: headers() }));
}

export async function getCurrentAppUserRemote(): Promise<AppUser> {
  return parse<AppUser>(await apiFetch(`${API_BASE}/api/v1/auth/me`, { headers: { "Content-Type": "application/json" } }));
}

export async function loginAppUser(username: string, password: string): Promise<AppUser> {
  return parse<AppUser>(
    await apiFetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Org-Id": ORG_ID,
      },
      body: JSON.stringify({ username, password }),
    }),
  );
}

export async function logoutAppUser(): Promise<void> {
  await apiFetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

export async function getAccessSettingsRemote(): Promise<AccessSettings> {
  return parse<AccessSettings>(await apiFetch(`${API_BASE}/api/v1/access-settings`, { headers: headers() }));
}

export async function putAccessSettingsRemote(payload: AccessSettings): Promise<AccessSettings> {
  return parse<AccessSettings>(
    await apiFetch(`${API_BASE}/api/v1/access-settings`, {
      method: "PUT",
      headers: headers(),
      body: JSON.stringify(payload),
    }),
  );
}

export async function createAppUser(payload: Omit<AppUser, "id"> & { id?: string }): Promise<AppUser> {
  return parse<AppUser>(
    await apiFetch(`${API_BASE}/api/v1/users`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        user_id: payload.id,
        name: payload.name,
        designation: payload.designation,
        contact: payload.contact,
        email: payload.email,
        password: payload.password,
        role: payload.role,
        active: payload.active,
      }),
    }),
  );
}

export async function patchAppUser(id: string, payload: Partial<AppUser>): Promise<AppUser> {
  return parse<AppUser>(
    await apiFetch(`${API_BASE}/api/v1/users/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify(payload),
    }),
  );
}

export async function deleteAppUser(id: string): Promise<void> {
  await parse<{ message: string }>(
    await apiFetch(`${API_BASE}/api/v1/users/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: headers(),
    }),
  );
}

export async function uploadDocAssistantSession(files: FileList): Promise<{ id: string; document_names: string[] }> {
  const form = new FormData();
  Array.from(files).forEach((file) => form.append("files", file));
  return parse(
    await apiFetch(`${API_BASE}/api/v1/doc-assistant/sessions/upload`, {
      method: "POST",
      headers: { "X-Org-Id": ORG_ID },
      body: form,
    }),
  );
}

export async function createDocSession(documents: Record<string, string>): Promise<{ id: string; document_names: string[] }> {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/doc-assistant/sessions`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ documents }),
    }),
  );
}

export async function askDocAssistant(sessionId: string, question: string): Promise<{ answer: string }> {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/doc-assistant/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ question }),
    }),
  );
}

export async function removeDocAssistantDocument(sessionId: string, documentName: string): Promise<{ id: string; document_names: string[] }> {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/doc-assistant/sessions/${sessionId}/documents/${encodeURIComponent(documentName)}`, {
      method: "DELETE",
      headers: headers(),
    }),
  );
}

export async function clearDocAssistantSession(sessionId: string): Promise<void> {
  await parse<{ message: string }>(
    await apiFetch(`${API_BASE}/api/v1/doc-assistant/sessions/${sessionId}`, {
      method: "DELETE",
      headers: headers(),
    }),
  );
}

export function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
