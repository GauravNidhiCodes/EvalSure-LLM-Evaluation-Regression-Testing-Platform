/** Dashboard configuration — secrets stay server-side. */

export function getApiBaseUrl(): string {
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
