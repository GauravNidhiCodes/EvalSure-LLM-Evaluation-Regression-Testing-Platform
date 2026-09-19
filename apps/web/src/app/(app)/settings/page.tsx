import Link from "next/link";
import { hasSession } from "@/lib/auth/session";
import { getApiBaseUrl } from "@/lib/config";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const apiUrl = getApiBaseUrl();
  const authenticated = await hasSession();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="mt-1 text-sm text-muted">
          Connection and session status. Tokens are never shown in the UI.
        </p>
      </div>
      <dl className="space-y-3 rounded border border-border bg-panel p-4 text-sm">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">NEXT_PUBLIC_API_URL</dt>
          <dd className="mt-1 font-mono text-xs">{apiUrl}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Session</dt>
          <dd className="mt-1 font-mono text-xs">
            {authenticated ? "authenticated (cookie or server env JWT)" : "not authenticated"}
          </dd>
        </div>
      </dl>
      <p className="text-sm text-muted">
        Web dashboard uses JWT (httpOnly cookie after{" "}
        <Link href="/login" className="text-accent hover:underline">
          /login
        </Link>
        ). SDK/CLI use project API keys under project settings. Optional{" "}
        <code className="font-mono text-xs">EVALSURE_ACCESS_TOKEN</code> in{" "}
        <code className="font-mono text-xs">.env.local</code> remains a server-only fallback for CI.
      </p>
    </div>
  );
}
