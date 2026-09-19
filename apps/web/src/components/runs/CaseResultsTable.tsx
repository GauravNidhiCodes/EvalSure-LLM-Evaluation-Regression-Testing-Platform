"use client";

import { useState } from "react";
import { JsonPreview } from "@/components/ui/JsonPreview";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatScore } from "@/lib/format";
import type { CaseResult } from "@/types/api";

export function CaseResultsTable({ results }: { results: CaseResult[] }) {
  const [selected, setSelected] = useState<string | null>(null);
  const active = results.find((r) => r.id === selected) ?? null;

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded border border-border">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead className="bg-elevated/80 text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="border-b border-border px-3 py-2">Test case</th>
              <th className="border-b border-border px-3 py-2">Status</th>
              <th className="border-b border-border px-3 py-2">Metrics</th>
              <th className="border-b border-border px-3 py-2">Regression</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-panel/40">
            {results.map((result) => (
              <tr
                key={result.id}
                className={`cursor-pointer hover:bg-elevated/40 ${
                  selected === result.id ? "bg-elevated/60" : ""
                }`}
                onClick={() => setSelected(result.id === selected ? null : result.id)}
              >
                <td className="px-3 py-2 font-mono text-xs">
                  {result.external_id || result.test_case_id}
                </td>
                <td className="px-3 py-2">
                  <StatusBadge status={result.status} kind="case" />
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted">
                  {Object.entries(result.metric_scores || {})
                    .map(([name, entry]) => {
                      const score =
                        typeof entry === "object" &&
                        entry !== null &&
                        "score" in entry
                          ? (entry as { score: unknown }).score
                          : entry;
                      return `${name}=${formatScore(score)}`;
                    })
                    .join(" · ") || "—"}
                </td>
                <td className="px-3 py-2 text-xs">
                  {result.is_regression ? (
                    <span className="text-rose-300">regressed</span>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {active ? (
        <div className="rounded border border-border bg-panel p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-medium">
              Case detail · {active.external_id || active.test_case_id}
            </h3>
            <StatusBadge status={active.status} kind="case" />
          </div>
          {active.error_message ? (
            <p className="mt-3 text-sm text-rose-300">{active.error_message}</p>
          ) : null}
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Actual output</p>
              <div className="mt-2">
                <JsonPreview value={active.actual_output} label="actual" compact={false} />
              </div>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Metric scores</p>
              <div className="mt-2">
                <JsonPreview value={active.metric_scores} label="scores" compact={false} />
              </div>
            </div>
          </div>
          <p className="mt-3 text-xs text-muted">
            Input / expected live on the dataset version test case ({active.test_case_id}).
            Regression flag: {active.is_regression ? "true" : "false"}.
          </p>
        </div>
      ) : null}
    </div>
  );
}
