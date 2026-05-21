"use client";

export type AppRole = "admin" | "management" | "approver" | "sales" | "estimation" | "technical" | "planning" | "purchase" | "viewer";

export type AppUser = {
  id: string;
  name: string;
  email: string;
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
  purchase: "Purchase",
  viewer: "Viewer",
};

const validRoles: AppRole[] = ["admin", "management", "approver", "sales", "estimation", "technical", "planning", "purchase", "viewer"];

const defaultAdmin: AppUser = {
  id: "shashnam@flosil.com",
  name: "Shashnam",
  email: "shashnam@flosil.com",
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

function normalizeUser(user: Partial<AppUser>, fallbackId: string): AppUser {
  const id = String(user.id || fallbackId || crypto.randomUUID()).trim();
  const role = validRoles.includes(String(user.role) as AppRole) ? user.role as AppRole : "sales";
  return {
    id,
    name: String(user.name || user.email || id).trim(),
    email: String(user.email || "").trim(),
    role,
    active: user.active !== false,
  };
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
    const users = parsed
      .map((user, index) => normalizeUser(user, `user-${index + 1}`))
      .filter((user) => user.id !== "local-admin" && user.email.toLowerCase() !== "admin@goodrich.local");
    for (const seed of defaultUsers) {
      const existing = users.find((user) => user.id === seed.id || user.email.toLowerCase() === seed.email.toLowerCase());
      if (existing) {
        existing.role = "admin";
        existing.active = true;
      } else {
        users.unshift(seed);
      }
    }
    if (!users.some((user) => user.role === "admin" && user.active)) {
      users.unshift(defaultAdmin);
    }
    const current = window.localStorage.getItem(CURRENT_USER_KEY);
    if (!current || current === "local-admin" || !users.some((user) => user.id === current && user.active)) {
      window.localStorage.setItem(CURRENT_USER_KEY, defaultAdmin.id);
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
  const normalized = users.map((user, index) => normalizeUser(user, `user-${index + 1}`));
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
  const next = users.find((user) => user.id === userId && user.active);
  if (next) {
    window.localStorage.setItem(CURRENT_USER_KEY, next.id);
    notifyChanged();
  }
}

export function ensureLoginUser(email?: string) {
  if (!hasStorage()) return;
  const cleanEmail = String(email || "").trim().toLowerCase();
  if (!cleanEmail) {
    getAppUsers();
    return;
  }
  const users = getAppUsers();
  const existing = users.find((user) => user.email.toLowerCase() === cleanEmail);
  if (existing) {
    window.localStorage.setItem(CURRENT_USER_KEY, existing.id);
    notifyChanged();
    return;
  }
  const user: AppUser = {
    id: cleanEmail,
    name: cleanEmail.split("@")[0] || cleanEmail,
    email: cleanEmail,
    role: users.some((row) => row.role === "admin") ? "sales" : "admin",
    active: true,
  };
  saveAppUsers([...users, user]);
  window.localStorage.setItem(CURRENT_USER_KEY, user.id);
  notifyChanged();
}

export function canManageUsers(role: AppRole) {
  return role === "admin";
}

export function canApproveQuotes(role: AppRole) {
  return role === "admin" || role === "approver" || role === "management";
}

export function canEditQuotes(role: AppRole) {
  return role !== "viewer";
}
