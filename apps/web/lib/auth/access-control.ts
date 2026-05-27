import type { AppRole } from "@/lib/auth/users";

export const ACCESS_SETTINGS_CHANGED_EVENT = "gq-access-settings-changed";
const ACCESS_SETTINGS_KEY = "gq_access_settings";

export type AppCapability =
  | "view_dashboard"
  | "view_enquiry"
  | "view_material_planning"
  | "view_quotation"
  | "view_purchase_orders"
  | "view_doc_assistant"
  | "view_history"
  | "view_settings"
  | "create_enquiry"
  | "edit_sales_details"
  | "edit_workflow"
  | "edit_line_items"
  | "edit_quotation"
  | "edit_material_phase2"
  | "approve_quotes"
  | "export_quotes"
  | "manage_users";

export type RolePermissionMap = Record<AppRole, Record<AppCapability, boolean>>;

export type AccessSettings = {
  with_whom_options: string[];
  role_permissions: RolePermissionMap;
};

export const capabilityLabels: Record<AppCapability, string> = {
  view_dashboard: "Dashboard",
  view_enquiry: "Enquiry page",
  view_material_planning: "Material planning page",
  view_quotation: "Quotation page",
  view_purchase_orders: "Customer PO page",
  view_doc_assistant: "Document assistant",
  view_history: "Activity history",
  view_settings: "Settings page",
  create_enquiry: "Create enquiry",
  edit_sales_details: "Edit sales details",
  edit_workflow: "Edit workflow",
  edit_line_items: "Edit line items",
  edit_quotation: "Edit quotation",
  edit_material_phase2: "Edit material planning rows",
  approve_quotes: "Approve quotes",
  export_quotes: "Export quotes",
  manage_users: "Manage users",
};

export const pageCapabilities = [
  "view_dashboard",
  "view_enquiry",
  "view_material_planning",
  "view_quotation",
  "view_purchase_orders",
  "view_doc_assistant",
  "view_history",
  "view_settings",
] as const satisfies readonly AppCapability[];

export const actionCapabilities = [
  "create_enquiry",
  "edit_sales_details",
  "edit_workflow",
  "edit_line_items",
  "edit_quotation",
  "edit_material_phase2",
  "approve_quotes",
  "export_quotes",
  "manage_users",
] as const satisfies readonly AppCapability[];

export const allCapabilities = [...pageCapabilities, ...actionCapabilities];

const appRoles: AppRole[] = ["admin", "management", "approver", "sales", "estimation", "technical", "planning", "material_planner", "purchase", "viewer"];

function permissions(enabled: AppCapability[]): Record<AppCapability, boolean> {
  const allowed = new Set(enabled);
  return Object.fromEntries(allCapabilities.map((capability) => [capability, allowed.has(capability)])) as Record<AppCapability, boolean>;
}

export const defaultAccessSettings: AccessSettings = {
  with_whom_options: ["Ashwin sir", "GTQ", "Estimation", "Arun Sir"],
  role_permissions: {
    admin: permissions(allCapabilities),
    management: permissions([
      "view_dashboard", "view_enquiry", "view_material_planning", "view_quotation", "view_purchase_orders", "view_doc_assistant", "view_history",
      "create_enquiry", "edit_sales_details", "edit_workflow", "edit_line_items", "edit_quotation", "approve_quotes", "export_quotes",
    ]),
    approver: permissions([
      "view_dashboard", "view_quotation", "view_purchase_orders", "view_history",
      "edit_workflow", "edit_line_items", "edit_quotation", "approve_quotes", "export_quotes",
    ]),
    sales: permissions([
      "view_dashboard", "view_enquiry", "view_quotation", "view_purchase_orders", "view_doc_assistant", "view_history",
      "edit_sales_details",
    ]),
    estimation: permissions([
      "view_dashboard", "view_enquiry", "view_doc_assistant", "view_history",
      "create_enquiry", "edit_workflow", "edit_line_items", "edit_quotation", "export_quotes",
    ]),
    technical: permissions([
      "view_dashboard", "view_enquiry", "view_doc_assistant", "view_history",
      "create_enquiry", "edit_workflow", "edit_line_items", "edit_quotation", "export_quotes",
    ]),
    planning: permissions([
      "view_dashboard", "view_material_planning", "view_purchase_orders", "view_history",
      "create_enquiry", "edit_workflow", "edit_line_items", "edit_quotation", "export_quotes",
    ]),
    material_planner: permissions([
      "view_dashboard", "view_material_planning", "view_purchase_orders", "view_history",
      "create_enquiry", "edit_workflow", "edit_line_items", "edit_quotation", "edit_material_phase2", "export_quotes",
    ]),
    purchase: permissions([
      "view_dashboard", "view_material_planning", "view_purchase_orders", "view_history",
      "create_enquiry", "edit_workflow", "edit_line_items", "edit_quotation", "export_quotes",
    ]),
    viewer: permissions(["view_history"]),
  },
};

function hasStorage() {
  return typeof window !== "undefined" && Boolean(window.localStorage);
}

function notifyChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(ACCESS_SETTINGS_CHANGED_EVENT));
  }
}

function cleanOptions(values: unknown): string[] {
  if (!Array.isArray(values)) return defaultAccessSettings.with_whom_options;
  const seen = new Set<string>();
  return values
    .map((value) => String(value ?? "").trim())
    .filter((value) => {
      const key = value.toLowerCase();
      if (!value || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

export function normalizeAccessSettings(settings?: Partial<AccessSettings> | null): AccessSettings {
  const rawPermissions = (settings?.role_permissions ?? {}) as Partial<RolePermissionMap>;
  const role_permissions = Object.fromEntries(appRoles.map((role) => {
    const base = defaultAccessSettings.role_permissions[role];
    const raw = (rawPermissions[role] ?? {}) as Partial<Record<AppCapability, boolean>>;
    const merged = Object.fromEntries(allCapabilities.map((capability) => [
      capability,
      typeof raw[capability] === "boolean" ? raw[capability] : base[capability],
    ])) as Record<AppCapability, boolean>;
    if (role === "admin") {
      for (const capability of allCapabilities) {
        merged[capability] = true;
      }
    }
    return [role, merged];
  })) as RolePermissionMap;
  return {
    with_whom_options: cleanOptions(settings?.with_whom_options),
    role_permissions,
  };
}

export function getAccessSettings(): AccessSettings {
  if (!hasStorage()) return defaultAccessSettings;
  const raw = window.localStorage.getItem(ACCESS_SETTINGS_KEY);
  if (!raw) {
    window.localStorage.setItem(ACCESS_SETTINGS_KEY, JSON.stringify(defaultAccessSettings));
    return defaultAccessSettings;
  }
  try {
    const normalized = normalizeAccessSettings(JSON.parse(raw) as Partial<AccessSettings>);
    window.localStorage.setItem(ACCESS_SETTINGS_KEY, JSON.stringify(normalized));
    return normalized;
  } catch {
    window.localStorage.setItem(ACCESS_SETTINGS_KEY, JSON.stringify(defaultAccessSettings));
    return defaultAccessSettings;
  }
}

export function saveAccessSettings(settings: Partial<AccessSettings>) {
  if (!hasStorage()) return;
  window.localStorage.setItem(ACCESS_SETTINGS_KEY, JSON.stringify(normalizeAccessSettings(settings)));
  notifyChanged();
}

export function canRole(role: AppRole, capability: AppCapability, settings = getAccessSettings()) {
  if (role === "admin") return true;
  return Boolean(settings.role_permissions[role]?.[capability]);
}
