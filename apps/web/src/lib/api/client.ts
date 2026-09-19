import { getAccessToken, getApiBaseUrl, getApiPrefix } from "@/lib/config";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export type ApiFetchOptions = {
  method?: string;
  body?: unknown;
  /** Override default Bearer token for this request. */
  token?: string | null;
  cache?: RequestCache;
  next?: NextFetchRequestConfig;
};

function buildHeaders(token?: string | null): HeadersInit {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const auth = token === null ? undefined : token ?? getAccessToken();
  if (auth) {
    headers.Authorization = `Bearer ${auth}`;
  }
  return headers;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const base = getApiBaseUrl();
  const prefix = getApiPrefix();
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const url = `${base}${prefix}${normalized}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers: buildHeaders(options.token),
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: options.cache ?? "no-store",
      next: options.next,
    });
  } catch {
    throw new ApiError(
      `Unable to reach EVALSURE API at ${base}. Is the backend running?`,
      0,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    let message = response.statusText || "API request failed";
    if (typeof payload === "object" && payload !== null && "detail" in payload) {
      const detail = (payload as { detail: unknown }).detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((item) =>
            typeof item === "object" && item !== null && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : String(item),
          )
          .join("; ");
      } else if (detail !== undefined) {
        message = String(detail);
      }
    }
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}
