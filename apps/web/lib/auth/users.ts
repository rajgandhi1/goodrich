"use client";

export type AppRole = "admin" | "management" | "approver" | "sales" | "estimation" | "technical" | "planning" | "material_planner" | "purchase" | "viewer";

export type AppUser = {
  id: string;
  name: string;
  email: string;
  password?: string;
  role: AppRole;
  active: boolean;
};

const USERS_KEY = "gq_app_users";
const CURRENT_USER_KEY = "gq_current_user_id";
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

const validRoles: AppRole[] = ["admin", "management", "approver", "sales", "estimation", "technical", "planning", "material_planner", "purchase", "viewer"];

const defaultAdmin: AppUser = {
  id: "shashnam",
  name: "Shashnam",
  email: "shashnam@flosil.com",
  password: "admin",
  role: "admin",
  active: true,
};

const defaultUsers: AppUser[] = [defaultAdmin];

function hasStorage() {
  return typeof window !== "undefined" && Boolean(window.localStorage);
}

function notifyChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(USERS_CHANGED_EVENT));
  }
}

function normalizeUsername(value: string) {
  const clean = String(value || "").trim().toLowerCase();
  const withoutDomain = clean.includes("@") ? clean.split("@")[0] : clean;
  return withoutDomain.replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "user";
}

function normalizeUser(user: Partial<AppUser>, fallbackId: string): AppUser {
  const id = normalizeUsername(String(user.id || user.email || fallbackId || "user"));
  const role = validRoles.includes(String(user.role) as AppRole) ? user.role as AppRole : "sales";
  return {
    id,
    name: String(user.name || user.email || id).trim(),
    email: String(user.email || "").trim().toLowerCase(),
    password: String(user.password ?? (id === defaultAdmin.id ? defaultAdmin.password : "")).trim(),
    role,
    active: user.active !== false,
  };
}

function uniqueUsers(users: AppUser[]) {
  const byId = new Map<string, AppUser>();
  for (const user of users) {
    const existing = byId.get(user.id);
    if (!existing) {
      byId.set(user.id, user);
      continue;
    }
    byId.set(user.id, {
      ...existing,
      ...user,
      password: user.password || existing.password,
      role: existing.role === "admin" ? existing.role : user.role,
      active: existing.active || user.active,
    });
  }
  return Array.from(byId.values());
}

export function getAppUsers(): AppUser[] {
  if (!hasStorage()) return defaultUsers;
  const raw = window.localStorage.getItem(USERS_KEY);
  if (!raw) {
    window.localStorage.setItem(USERS_KEY, JSON.stringify(defaultUsers));
    window.localStorage.setItem(CURRENT_USER_KEY, defaultAdmin.id);
    return defaultUsers;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<AppUser>[];
    const users = uniqueUsers(parsed
      .map((user, index) => normalizeUser(user, `user-${index + 1}`))
      .filter((user) => user.id !== "local-admin" && user.email.toLowerCase() !== "admin@goodrich.local"));
    for (const seed of defaultUsers) {
      const existing = users.find((user) => user.id === seed.id || user.email.toLowerCase() === seed.email.toLowerCase());
      if (existing) {
        existing.id = seed.id;
        existing.role = "admin";
        existing.active = true;
        existing.password = existing.password || seed.password;
      } else {
        users.unshift(seed);
      }
    }
    if (!users.some((user) => user.role === "admin" && user.active)) {
      users.unshift(defaultAdmin);
    }
    const current = window.localStorage.getItem(CURRENT_USER_KEY);
    const currentUsername = normalizeUsername(current || "");
    if (!current || current === "local-admin" || !users.some((user) => user.id === currentUsername && user.active)) {
      window.localStorage.setItem(CURRENT_USER_KEY, defaultAdmin.id);
    } else if (current !== currentUsername) {
      window.localStorage.setItem(CURRENT_USER_KEY, currentUsername);
    }
    window.localStorage.setItem(USERS_KEY, JSON.stringify(users));
    return users;
  } catch {
    window.localStorage.setItem(USERS_KEY, JSON.stringify(defaultUsers));
    window.localStorage.setItem(CURRENT_USER_KEY, defaultAdmin.id);
    return defaultUsers;
  }
}

export function saveAppUsers(users: AppUser[]) {
  if (!hasStorage()) return;
  const existingPasswords = new Map(getAppUsers().map((user) => [user.id, user.password || ""]));
  const normalized = uniqueUsers(users.map((user, index) => {
    const normalizedUser = normalizeUser(user, `user-${index + 1}`);
    return {
      ...normalizedUser,
      password: normalizedUser.password || existingPasswords.get(normalizedUser.id) || "",
    };
  }));
  window.localStorage.setItem(USERS_KEY, JSON.stringify(normalized));
  const current = window.localStorage.getItem(CURRENT_USER_KEY);
  if (!current || !normalized.some((user) => user.id === current && user.active)) {
    const next = normalized.find((user) => user.active)?.id ?? defaultAdmin.id;
    window.localStorage.setItem(CURRENT_USER_KEY, next);
  }
  notifyChanged();
}

export function getCurrentAppUser(): AppUser {
  const users = getAppUsers();
  if (!hasStorage()) return users[0] ?? defaultAdmin;
  const currentId = window.localStorage.getItem(CURRENT_USER_KEY);
  const current = users.find((user) => user.id === currentId && user.active) ?? users.find((user) => user.active) ?? defaultAdmin;
  window.localStorage.setItem(CURRENT_USER_KEY, current.id);
  return current;
}

export function setCurrentAppUser(userId: string) {
  if (!hasStorage()) return;
  const users = getAppUsers();
  const next = users.find((user) => user.id === normalizeUsername(userId) && user.active);
  if (next) {
    window.localStorage.setItem(CURRENT_USER_KEY, next.id);
    notifyChanged();
  }
}

export function findAppUserByUsername(username?: string) {
  const cleanUsername = normalizeUsername(String(username || ""));
  return getAppUsers().find((user) => user.id === cleanUsername || user.email.toLowerCase() === String(username || "").trim().toLowerCase());
}

export function resolveAppUserName(values: unknown | unknown[], users: AppUser[] = getAppUsers(), fallback = "") {
  const candidates = (Array.isArray(values) ? values : [values])
    .map((value) => String(value ?? "").trim())
    .filter(Boolean);

  for (const candidate of candidates) {
    const lower = candidate.toLowerCase();
    const username = normalizeUsername(candidate);
    const user = users.find((row) =>
      row.id.toLowerCase() === lower ||
      row.id === username ||
      row.email.toLowerCase() === lower ||
      normalizeUsername(row.email) === username ||
      row.name.toLowerCase() === lower,
    );
    if (user) return user.name || user.id;
  }

  const first = candidates[0] ?? "";
  if (!first) return fallback;
  return first.includes("@") ? first.split("@")[0] : first;
}

export function authenticateAppUser(username?: string, password?: string) {
  if (!hasStorage()) return;
  const user = findAppUserByUsername(username);
  if (!user || !user.active || !user.password || user.password !== String(password || "")) {
    return undefined;
  }
  window.localStorage.setItem(CURRENT_USER_KEY, user.id);
  notifyChanged();
  return user;
}

export function ensureLoginUser(username?: string) {
  if (!hasStorage()) return;
  const existing = findAppUserByUsername(username);
  if (existing?.active) {
    window.localStorage.setItem(CURRENT_USER_KEY, existing.id);
    notifyChanged();
  }
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
