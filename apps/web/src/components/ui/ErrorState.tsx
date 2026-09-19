import Link from "next/link";
import { ApiError } from "@/lib/api/client";

export function ErrorState({
  error,
  retryHref,
}: {
  error: unknown;
  retryHref?: string;
}) {
  let title = "Something went wrong";
  let detail = "An unexpected error occurred.";

  if (error instanceof ApiError) {
    if (error.status === 0) {
      title = "API unavailable";
      detail = error.message;
    } else if (error.status === 401 || error.status === 403) {
      title = "Unauthorized";
      detail = "Sign in at /login, or configure a server-only JWT session.";
    } else if (error.status === 404) {
      title = "Not found";
      detail = error.message;
    } else {
      title = `API error (${error.status})`;
      detail = error.message;
    }
  } else if (error instanceof Error) {
    detail = error.message;
  }

  return (
    <div className="rounded border border-rose-800/50 bg-rose-950/30 px-4 py-5">
      <p className="text-sm font-medium text-rose-200">{title}</p>
      <p className="mt-2 text-sm text-rose-100/80">{detail}</p>
      {retryHref ? (
        <Link
          href={retryHref}
          className="mt-4 inline-block rounded border border-rose-700/60 px-3 py-1.5 text-xs text-rose-100 hover:bg-rose-950/50"
        >
          Retry
        </Link>
      ) : null}
    </div>
  );
}
