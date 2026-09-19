"use client";

import { useState } from "react";
import { previewJson } from "@/lib/format";

export function JsonPreview({
  value,
  label = "JSON",
  compact = true,
}: {
  value: unknown;
  label?: string;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(!compact);

  if (value === null || value === undefined) {
    return <span className="text-muted">—</span>;
  }

  return (
    <div className="min-w-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="font-mono text-xs text-accent hover:underline"
      >
        {open ? "Hide" : "Show"} {label}
        {!open ? `: ${previewJson(value)}` : ""}
      </button>
      {open ? (
        <pre className="mt-2 max-h-64 overflow-auto rounded border border-border bg-canvas p-2 font-mono text-[11px] text-muted">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
