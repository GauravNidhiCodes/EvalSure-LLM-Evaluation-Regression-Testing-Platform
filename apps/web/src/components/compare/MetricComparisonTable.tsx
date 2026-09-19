"use client";

import { formatScore } from "@/lib/format";
import { deltaArrow, metricStatusLabel, type MetricComparisonRow } from "@/lib/compare";

export function MetricComparisonTable({ rows }: { rows: MetricComparisonRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="rounded border border-dashed border-border px-4 py-6 text-center text-sm text-muted">
        No comparable metrics available.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-border">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead className="bg-elevated/80 text-[11px] uppercase tracking-wide text-muted">
          <tr>
            <th className="border-b border-border px-3 py-2">Metric</th>
            <th className="border-b border-border px-3 py-2">Baseline</th>
            <th className="border-b border-border px-3 py-2">Current</th>
            <th className="border-b border-border px-3 py-2">Delta</th>
            <th className="border-b border-border px-3 py-2">Threshold</th>
            <th className="border-b border-border px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-panel/40">
          {rows.map((row) => (
            <tr key={row.metric} className="hover:bg-elevated/40">
              <td className="px-3 py-2 font-mono text-xs">{row.metric}</td>
              <td className="px-3 py-2 font-mono text-xs">{formatScore(row.baseline)}</td>
              <td className="px-3 py-2 font-mono text-xs">{formatScore(row.current)}</td>
              <td className="px-3 py-2 font-mono text-xs">
                <span className="mr-1 text-muted" aria-hidden>
                  {deltaArrow(row.delta)}
                </span>
                {formatScore(row.delta)}
              </td>
              <td className="px-3 py-2 font-mono text-xs">
                {row.threshold !== null ? `-${formatScore(row.threshold)}` : "—"}
              </td>
              <td className="px-3 py-2">
                <MetricStatusPill status={row.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricStatusPill({ status }: { status: MetricComparisonRow["status"] }) {
  const label = metricStatusLabel(status);
  const styles =
    status === "REGRESSED"
      ? "border-rose-700/60 bg-rose-950/40 text-rose-300"
      : status === "IMPROVED"
        ? "border-emerald-700/60 bg-emerald-950/40 text-emerald-300"
        : status === "WITHIN_LIMIT" || status === "DEGRADED"
          ? "border-amber-700/60 bg-amber-950/40 text-amber-200"
          : "border-border bg-elevated text-muted";
  return (
    <span className={`inline-flex rounded border px-1.5 py-0.5 font-mono text-[11px] ${styles}`}>
      {label}
    </span>
  );
}
