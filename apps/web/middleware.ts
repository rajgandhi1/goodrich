import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/reset-password", "/auth/callback"];
const SESSION_COOKIE = process.env.AUTH_COOKIE_NAME ?? "ggpl_session";

function base64UrlToBytes(value: string) {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
}

async function verifySessionCookie(value?: string) {
  if (!value || !value.includes(".")) return false;
  const [payload, signature] = value.split(".", 2);
  const secret = process.env.AUTH_SECRET ?? "dev-only-change-me";
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const expected = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload)));
  const actual = base64UrlToBytes(signature);
  if (actual.length !== expected.length) return false;
  let diff = 0;
  for (let index = 0; index < actual.length; index += 1) diff |= actual[index] ^ expected[index];
  if (diff !== 0) return false;
  try {
    const claims = JSON.parse(new TextDecoder().decode(base64UrlToBytes(payload))) as { exp?: number };
    return Number(claims.exp || 0) > Math.floor(Date.now() / 1000);
  } catch {
    return false;
  }
}

async function hasAuthCookie(request: NextRequest) {
  if (await verifySessionCookie(request.cookies.get(SESSION_COOKIE)?.value)) return true;
  return request.cookies.getAll().some((cookie) => cookie.name.startsWith("sb-") && cookie.value.length > 0);
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
  const isAuthed = await hasAuthCookie(request);

  if (!isAuthed && !isPublic) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthed && pathname === "/login") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
