/** Auth cookie + token helpers for the Next.js dashboard. */

export const AUTH_COOKIE_NAME = "evalsure_access_token";

export const AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

export function isProtectedPath(pathname: string): boolean {
  if (
    pathname === "/login" ||
    pathname === "/register" ||
    pathname.startsWith("/api/auth/") ||
    pathname.startsWith("/_next/") ||
    pathname === "/favicon.ico"
  ) {
    return false;
  }
  const protectedPrefixes = [
    "/dashboard",
    "/projects",
    "/datasets",
    "/experiments",
    "/runs",
    "/traces",
    "/settings",
  ];
  if (pathname === "/") return true;
  return protectedPrefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
