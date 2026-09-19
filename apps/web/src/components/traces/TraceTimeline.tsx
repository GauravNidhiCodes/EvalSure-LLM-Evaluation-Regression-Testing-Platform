"use client";

import { useState } from "react";
import { JsonPreview } from "@/components/ui/JsonPreview";
import { formatDate, shortId } from "@/lib/format";
import type { TraceEvent } from "@/types/api";

export function TraceTimeline({ events }: { events: TraceEvent[] }) {
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <ol className="space-y-2">
      {events.map((event) => {
        const open = openId === event.id;
        return (
          <li key={event.id} className="rounded border border-border bg-panel">
            <button
              type="button"
              className="flex w-full flex-wrap items-center gap-3 px-3 py-2 text-left hover:bg-elevated/40"
              onClick={() => setOpenId(open ? null : event.id)}
            >
              <span className="font-mono text-[11px] text-muted">
                {formatDate(event.timestamp)}
              </span>
              <span className="rounded border border-border bg-elevated px-1.5 py-0.5 font-mono text-[11px] text-accent">
                {event.event_type}
              </span>
              <span className="font-mono text-[11px] text-muted">
                {event.case_result_id ? `case ${shortId(event.case_result_id)}` : "run"}
              </span>
            </button>
            {open ? (
              <div className="border-t border-border px-3 py-3">
                <JsonPreview value={event.data} label="event data" compact={false} />
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
