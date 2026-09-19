"use client";

import { useMemo, useState } from "react";
import { JsonPreview } from "@/components/ui/JsonPreview";
import { deltaArrow, type CaseComparisonRow } from "@/lib/compare";
import { formatScore, shortId } from "@/lib/format";
import type { TestCase } from "@/types/api";

export function CaseComparisonPanel({
  rows,
  testCasesById,
}: {
  rows: CaseComparisonRow[];
  testCasesById: Record<string, TestCase>;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = useMemo(
    () => rows.find((r) => r.test_case_id === selectedId) ?? null,
    [rows, selectedId],
  );
  const testCase = selected ? testCasesById[selected.test_case_id] : undefined;
  const regressed = rows.filter((r) => r.status === "REGRESSED");

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h2 className="text-sm font-medium">Regressed test cases</h2>
        {regressed.length === 0 ? (
          <p className="rounded border border-dashed border-border px-4 py-6 text-center text-sm text-muted">
            No regressed cases reported by the API.
          </p>
        ) : (
          <CaseTable
            rows={regressed}
            onSelect={(id) => setSelectedId(id === selectedId ? null : id)}
            selectedId={selectedId}
          />
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">All comparable cases</h2>
        <CaseTable
          rows={rows}
          onSelect={(id) => setSelectedId(id === selectedId ? null : id)}
          selectedId={selectedId}
        />
      </section>

      {selected ? (
        <CaseDetail
          row={selected}
          testCase={testCase}
          onClose={() => setSelectedId(null)}
        />
      ) : null}
    </div>
  );
}

function CaseTable({
  rows,
  onSelect,
  selectedId,
}: {
  rows: CaseComparisonRow[];
  onSelect: (id: string) => void;
  selectedId: string | null;
}) {
  return (
    <div className="overflow-x-auto rounded border border-border">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead className="bg-elevated/80 text-[11px] uppercase tracking-wide text-muted">
          <tr>
            <th className="border-b border-border px-3 py-2">Test case</th>
            <th className="border-b border-border px-3 py-2">Metric</th>
            <th className="border-b border-border px-3 py-2">Baseline</th>
            <th className="border-b border-border px-3 py-2">Current</th>
            <th className="border-b border-border px-3 py-2">Delta</th>
            <th className="border-b border-border px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-panel/40">
          {rows.map((row) => (
            <tr
              key={`${row.test_case_id}-${row.metric ?? "none"}`}
              className={`cursor-pointer hover:bg-elevated/40 ${
                selectedId === row.test_case_id ? "bg-elevated/60" : ""
              }`}
              onClick={() => onSelect(row.test_case_id)}
            >
              <td className="px-3 py-2 font-mono text-xs">
                {row.external_id || shortId(row.test_case_id)}
              </td>
              <td className="px-3 py-2 font-mono text-xs">{row.metric ?? "—"}</td>
              <td className="px-3 py-2 font-mono text-xs">{formatScore(row.baseline_score)}</td>
              <td className="px-3 py-2 font-mono text-xs">{formatScore(row.current_score)}</td>
              <td className="px-3 py-2 font-mono text-xs">
                <span className="mr-1 text-muted" aria-hidden>
                  {deltaArrow(row.delta)}
                </span>
                {formatScore(row.delta)}
              </td>
              <td className="px-3 py-2">
                <CaseStatusPill status={row.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CaseStatusPill({ status }: { status: CaseComparisonRow["status"] }) {
  const styles =
    status === "REGRESSED"
      ? "border-rose-700/60 bg-rose-950/40 text-rose-300"
      : status === "IMPROVED"
        ? "border-emerald-700/60 bg-emerald-950/40 text-emerald-300"
        : status === "DEGRADED"
          ? "border-amber-700/60 bg-amber-950/40 text-amber-200"
          : status === "NOT_COMPARABLE"
            ? "border-border bg-elevated text-muted"
            : "border-border bg-elevated text-muted";
  return (
    <span className={`inline-flex rounded border px-1.5 py-0.5 font-mono text-[11px] ${styles}`}>
      {status}
    </span>
  );
}

function CaseDetail({
  row,
  testCase,
  onClose,
}: {
  row: CaseComparisonRow;
  testCase: TestCase | undefined;
  onClose: () => void;
}) {
  return (
    <div className="rounded border border-accent/30 bg-panel p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">Case detail</h3>
          <p className="mt-1 font-mono text-xs text-muted">
            {row.external_id || row.test_case_id}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-border px-2 py-1 text-xs text-muted hover:text-ink"
        >
          Close
        </button>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <ScrollBlock label="INPUT">
          {testCase ? <pre>{JSON.stringify(testCase.input, null, 2)}</pre> : "Test case input unavailable."}
        </ScrollBlock>
        <ScrollBlock label="EXPECTED">
          {testCase?.expected != null ? (
            <pre>{JSON.stringify(testCase.expected, null, 2)}</pre>
          ) : (
            "Expected output unavailable."
          )}
        </ScrollBlock>
        <ScrollBlock label="BASELINE OUTPUT">
          {row.baseline_result?.actual_output != null ? (
            <pre>{JSON.stringify(row.baseline_result.actual_output, null, 2)}</pre>
          ) : (
            "Baseline case output unavailable."
          )}
        </ScrollBlock>
        <ScrollBlock label="CURRENT OUTPUT">
          {row.current_result?.actual_output != null ? (
            <pre>{JSON.stringify(row.current_result.actual_output, null, 2)}</pre>
          ) : (
            "Current case output unavailable."
          )}
        </ScrollBlock>
      </div>

      <div className="mt-4 overflow-x-auto rounded border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-elevated/80 text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2 text-left">Metric</th>
              <th className="px-3 py-2 text-left">Baseline</th>
              <th className="px-3 py-2 text-left">Current</th>
              <th className="px-3 py-2 text-left">Delta</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="px-3 py-2 font-mono text-xs">{row.metric ?? "—"}</td>
              <td className="px-3 py-2 font-mono text-xs">{formatScore(row.baseline_score)}</td>
              <td className="px-3 py-2 font-mono text-xs">{formatScore(row.current_score)}</td>
              <td className="px-3 py-2 font-mono text-xs">{formatScore(row.delta)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-sm">
        <span className="text-muted">Regression: </span>
        {row.reason || (row.status === "REGRESSED" ? "regressed" : row.status)}
      </p>

      <div className="mt-4">
        <JsonPreview
          value={{
            test_case_id: row.test_case_id,
            status: row.status,
            metric: row.metric,
            baseline_score: row.baseline_score,
            current_score: row.current_score,
            delta: row.delta,
            reason: row.reason,
          }}
          label="Raw JSON"
        />
      </div>
    </div>
  );
}

function ScrollBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded border border-border bg-canvas">
      <div className="border-b border-border px-3 py-1.5 text-[11px] uppercase tracking-wide text-muted">
        {label}
      </div>
      <div className="max-h-48 overflow-auto p-3 font-mono text-[11px] text-muted whitespace-pre-wrap">
        {children}
      </div>
    </div>
  );
}
