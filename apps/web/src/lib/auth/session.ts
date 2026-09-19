import { cookies } from "next/headers";
import { AUTH_COOKIE_NAME } from "@/lib/auth/constants";

/** Server-only JWT: httpOnly cookie first, then optional env fallback for CI/dev. */
export async function getAccessToken(): Promise<string | undefined> {
  const jar = await cookies();
  const fromCookie = jar.get(AUTH_COOKIE_NAME)?.value?.trim();
  if (fromCookie) return fromCookie;
  const fromEnv = process.env.EVALSURE_ACCESS_TOKEN?.trim();
  return fromEnv || undefined;
}

export async function hasSession(): Promise<boolean> {
  return Boolean(await getAccessToken());
}
