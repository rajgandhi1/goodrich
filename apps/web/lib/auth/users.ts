export type AppRole = "admin" | "management" | "approver" | "sales" | "estimation" | "technical" | "planning" | "material_planner" | "purchase" | "viewer";

export type AppUser = {
  id: string;
  name: string;
  email: string;
  designation?: string;
  contact?: string;
  password?: string;
  role: AppRole;
  active: boolean;
};

export const USERS_CHANGED_EVENT = "gq-users-changed";

export const roleLabels: Record<AppRole, string> = {
  admin: "Admin",
  management: "Management",
  approver: "Approver",
  sales: "Sales",
  estimation: "Estimation",
  technical: "Technical",
  planning: "Planning",
  material_planner: "Material planner",
  purchase: "Purchase",
  viewer: "Viewer",
};

const defaultUser: AppUser = {
  id: "local-user",
  name: "Local user",
  email: "",
  designation: "",
  contact: "",
  role: "sales",
  active: true,
};

let currentUser: AppUser = defaultUser;

function notifyChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(USERS_CHANGED_EVENT));
  }
}

function normalizeUser(user: Partial<AppUser> | null | undefined): AppUser {
  return {
    ...defaultUser,
    id: String(user?.id || defaultUser.id).trim().toLowerCase(),
    name: String(user?.name || user?.id || defaultUser.name).trim(),
    email: String(user?.email || "").trim().toLowerCase(),
    designation: String(user?.designation || "").trim(),
    contact: String(user?.contact || "").trim(),
    role: (Object.keys(roleLabels).includes(String(user?.role)) ? user?.role : defaultUser.role) as AppRole,
    active: user?.active !== false,
  };
}

export function getAppUsers(): AppUser[] {
  return [];
}

export function saveAppUsers(_users: AppUser[]) {
  void _users;
  notifyChanged();
}

export function getCurrentAppUser(): AppUser {
  return currentUser;
}

export function setCurrentAppUser(user: AppUser) {
  currentUser = normalizeUser(user);
  notifyChanged();
}

export function clearCurrentAppUser() {
  currentUser = defaultUser;
  notifyChanged();
}

export function findAppUserByUsername(_username?: string) {
  void _username;
  return undefined;
}

export function resolveAppUserName(values: unknown | unknown[], users: AppUser[] = [], fallback = "") {
  const candidates = (Array.isArray(values) ? values : [values])
    .map((value) => String(value ?? "").trim())
    .filter(Boolean);

  for (const candidate of candidates) {
    const lower = candidate.toLowerCase();
    const user = users.find((row) =>
      row.id.toLowerCase() === lower ||
      row.email.toLowerCase() === lower ||
      row.name.toLowerCase() === lower,
    );
    if (user) return user.name || user.id;
  }

  const first = candidates[0] ?? "";
  if (!first) return fallback;
  return first.includes("@") ? first.split("@")[0] : first;
}

export function authenticateAppUser(_username?: string, _password?: string) {
  void _username;
  void _password;
  return undefined;
}

export function ensureLoginUser(_username?: string) {
  void _username;
  notifyChanged();
}

export function canManageUsers(role: AppRole) {
  return role === "admin";
}

export function canApproveQuotes(role: AppRole) {
  return role === "admin" || role === "approver" || role === "management";
}

export function canEditQuotes(role: AppRole) {
  return role !== "viewer" && role !== "sales";
}
