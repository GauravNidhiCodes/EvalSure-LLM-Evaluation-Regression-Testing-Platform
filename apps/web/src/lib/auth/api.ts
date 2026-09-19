import { getApiBaseUrl, getApiPrefix } from "@/lib/config";

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
};

export class AuthRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthRequestError";
    this.status = status;
  }
}

function detailMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join("; ");
    }
  }
  return fallback;
}

/** Server-side call to FastAPI auth endpoints (no token stored in response helpers). */
export async function requestAuthToken(
  path: "/auth/login" | "/auth/register",
  body: { email: string; password: string },
): Promise<AuthTokenResponse> {
  const url = `${getApiBaseUrl()}${getApiPrefix()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new AuthRequestError("Unable to reach EVALSURE API.", 0);
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new AuthRequestError(
      detailMessage(payload, response.statusText || "Authentication failed"),
      response.status,
    );
  }

  return payload as AuthTokenResponse;
}
