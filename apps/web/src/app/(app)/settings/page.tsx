import { getAccessToken, getApiBaseUrl } from "@/lib/config";

export const dynamic = "force-dynamic";

export default function SettingsPage() {
  const apiUrl = getApiBaseUrl();
  const hasToken = Boolean(getAccessToken());

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="mt-1 text-sm text-muted">
          Read-only connection settings. Authentication UI is intentionally not built yet.
        </p>
      </div>
      <dl className="space-y-3 rounded border border-border bg-panel p-4 text-sm">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">NEXT_PUBLIC_API_URL</dt>
          <dd className="mt-1 font-mono text-xs">{apiUrl}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">EVALSURE_ACCESS_TOKEN</dt>
          <dd className="mt-1 font-mono text-xs">
            {hasToken ? "configured (server-only, value hidden)" : "not set"}
          </dd>
        </div>
      </dl>
      <p className="text-sm text-muted">
        Copy <code className="font-mono text-xs">apps/web/.env.example</code> to{" "}
        <code className="font-mono text-xs">.env.local</code>. Obtain a JWT via{" "}
        <code className="font-mono text-xs">POST /api/v1/auth/login</code>. Never put secrets in{" "}
        <code className="font-mono text-xs">NEXT_PUBLIC_*</code> variables.
      </p>
    </div>
  );
}
