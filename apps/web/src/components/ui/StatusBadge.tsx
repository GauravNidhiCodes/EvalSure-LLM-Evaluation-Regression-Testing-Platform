import type { CaseResultStatus, RegressionStatus, RunStatus } from "@/types/api";

const RUN_STYLES: Record<RunStatus, string> = {
  COMPLETED: "border-emerald-700/60 bg-emerald-950/40 text-emerald-300",
  FAILED: "border-rose-700/60 bg-rose-950/40 text-rose-300",
  PENDING: "border-amber-700/60 bg-amber-950/40 text-amber-200",
  RUNNING: "border-sky-700/60 bg-sky-950/40 text-sky-300",
};

const REGRESSION_STYLES: Record<RegressionStatus, string> = {
  PASS: "border-emerald-700/60 bg-emerald-950/40 text-emerald-300",
  FAIL: "border-rose-700/60 bg-rose-950/40 text-rose-300",
  NOT_EVALUATED: "border-border bg-elevated text-muted",
};

const CASE_STYLES: Record<CaseResultStatus, string> = {
  COMPLETED: "border-emerald-700/60 bg-emerald-950/40 text-emerald-300",
  FAILED: "border-rose-700/60 bg-rose-950/40 text-rose-300",
  PENDING: "border-amber-700/60 bg-amber-950/40 text-amber-200",
};

export function StatusBadge({
  status,
  kind = "run",
}: {
  status: string;
  kind?: "run" | "regression" | "case";
}) {
  const styles =
    kind === "regression"
      ? REGRESSION_STYLES[status as RegressionStatus]
      : kind === "case"
        ? CASE_STYLES[status as CaseResultStatus]
        : RUN_STYLES[status as RunStatus];

  return (
    <span
      className={`inline-flex rounded border px-1.5 py-0.5 font-mono text-[11px] uppercase tracking-wide ${
        styles ?? "border-border bg-elevated text-muted"
      }`}
    >
      {status}
    </span>
  );
}
