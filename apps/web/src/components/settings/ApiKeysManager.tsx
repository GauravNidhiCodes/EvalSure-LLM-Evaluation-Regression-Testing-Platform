"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { createProjectApiKey, revokeProjectApiKey } from "@/lib/api/api-keys";
import { formatDate } from "@/lib/format";
import type { ApiKeyMeta } from "@/types/api";

export function ApiKeysManager({
  projectId,
  initialKeys,
}: {
  projectId: string;
  initialKeys: ApiKeyMeta[];
}) {
  const router = useRouter();
  const [name, setName] = useState("local-development");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [oneTimeKey, setOneTimeKey] = useState<string | null>(null);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setOneTimeKey(null);
    setCreating(true);
    try {
      const result = await createProjectApiKey(projectId, name);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setOneTimeKey(result.created.api_key);
      setName("local-development");
      router.refresh();
    } finally {
      setCreating(false);
    }
  }

  async function onRevoke(keyId: string) {
    setError(null);
    setRevokingId(keyId);
    try {
      const result = await revokeProjectApiKey(projectId, keyId);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      router.refresh();
    } finally {
      setRevokingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={onCreate} className="flex flex-wrap items-end gap-3 rounded border border-border bg-panel p-4">
        <div className="min-w-[16rem] flex-1">
          <label htmlFor="key-name" className="block text-xs uppercase tracking-wide text-muted">
            Key name
          </label>
          <input
            id="key-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="mt-1 w-full rounded border border-border bg-canvas px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </div>
        <button
          type="submit"
          disabled={creating}
          className="rounded border border-accent/40 bg-accent/15 px-3 py-2 text-sm font-medium text-accent hover:bg-accent/25 disabled:opacity-60"
        >
          {creating ? "Creating…" : "Create API key"}
        </button>
      </form>

      {oneTimeKey ? (
        <div className="space-y-2 rounded border border-amber-800/50 bg-amber-950/20 px-4 py-4">
          <p className="text-sm font-semibold text-amber-100">This key will not be shown again.</p>
          <p className="text-xs text-amber-200/80">
            Copy it now for SDK/CLI use. It is not stored in the browser.
          </p>
          <pre className="max-h-32 overflow-auto rounded border border-border bg-canvas p-3 font-mono text-xs text-ink">
            {oneTimeKey}
          </pre>
          <button
            type="button"
            className="text-xs text-muted hover:text-ink"
            onClick={() => setOneTimeKey(null)}
          >
            Dismiss
          </button>
        </div>
      ) : null}

      {error ? (
        <p className="rounded border border-rose-800/50 bg-rose-950/30 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <div className="overflow-x-auto rounded border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-elevated/80 text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="border-b border-border px-3 py-2 text-left">Name</th>
              <th className="border-b border-border px-3 py-2 text-left">Prefix</th>
              <th className="border-b border-border px-3 py-2 text-left">Created</th>
              <th className="border-b border-border px-3 py-2 text-left">Status</th>
              <th className="border-b border-border px-3 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-panel/40">
            {initialKeys.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted">
                  No API keys yet.
                </td>
              </tr>
            ) : (
              initialKeys.map((key) => (
                <tr key={key.id}>
                  <td className="px-3 py-2">{key.name}</td>
                  <td className="px-3 py-2 font-mono text-xs">{key.key_prefix}…</td>
                  <td className="px-3 py-2 text-xs text-muted">{formatDate(key.created_at)}</td>
                  <td className="px-3 py-2 font-mono text-xs uppercase">{key.status}</td>
                  <td className="px-3 py-2">
                    {key.status === "active" ? (
                      <button
                        type="button"
                        disabled={revokingId === key.id}
                        onClick={() => onRevoke(key.id)}
                        className="text-xs text-rose-300 hover:underline disabled:opacity-60"
                      >
                        {revokingId === key.id ? "Revoking…" : "Revoke"}
                      </button>
                    ) : (
                      <span className="text-xs text-muted">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
