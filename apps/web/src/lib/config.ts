/** Dashboard configuration — secrets stay server-side. */

/**
 * Browser clients use NEXT_PUBLIC_API_URL (typically http://localhost:8000).
 * Server-side (RSC / route handlers) may use EVALSURE_API_INTERNAL_URL so Docker
 * Compose can reach the `api` service as http://api:8000.
 */
export function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    const internal = process.env.EVALSURE_API_INTERNAL_URL?.trim();
    if (internal) {
      return internal.replace(/\/$/, "");
    }
  }
  const url = process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000";
  return url.replace(/\/$/, "");
}

export function getApiPrefix(): string {
  return "/api/v1";
}

/** @deprecated Prefer async getAccessToken from @/lib/auth/session */
export function getAccessTokenFromEnv(): string | undefined {
  const token = process.env.EVALSURE_ACCESS_TOKEN?.trim();
  return token || undefined;
}
