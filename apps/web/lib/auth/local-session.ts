import { clearCurrentAppUser } from "@/lib/auth/users";

export function setLocalSession() {
  // The API sets the real httpOnly session cookie during login.
}

export function clearLocalSession() {
  clearCurrentAppUser();
}
