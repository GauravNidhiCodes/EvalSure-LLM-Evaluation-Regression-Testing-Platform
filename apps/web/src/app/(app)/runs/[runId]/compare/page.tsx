import Link from "next/link";
import { CaseComparisonPanel } from "@/components/compare/CaseComparisonPanel";
import { MetricComparisonTable } from "@/components/compare/MetricComparisonTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { JsonPreview } from "@/components/ui/JsonPreview";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError } from "@/lib/api/client";
import { listTestCases } from "@/lib/api/datasets";
import { getExperiment, listExperimentRuns, listRegressionPolicies } from "@/lib/api/experiments";
import { getRun, listCaseResults } from "@/lib/api/runs";
import {
  buildCaseComparisons,
  buildMetricComparisons,
  summarizeMetricComparisons,
} from "@/lib/compare";
import { formatDate, shortId } from "@/lib/format";
import type { EvaluationRun, TestCase } from "@/types/api";

export const dynamic = "force-dynamic";

export default async function RunComparePage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;

  try {
    const current = await getRun(runId);
    const baselineId = current.baseline_run_id ?? current.regression?.baseline_run_id ?? null;

    if (!baselineId) {
      return (
        <div className="space-y-4">
          <PageHeaderLinks
            items={[
              { href: `/runs/${runId}`, label: `Run ${shortId(runId)}` },
              { href: `/runs/${runId}/compare`, label: "Compare" },
            ]}
          />
          <h1 className="text-lg font-semibold">Run comparison</h1>
          <EmptyState
            title="No baseline configured for this run."
            description="Assign a baseline on the experiment, then re-open comparison."
          />
          <Link href={`/runs/${runId}`} className="text-sm text-accent hover:underline">
            Back to run
          </Link>
        </div>
      );
    }

    let baseline: EvaluationRun;
    try {
      baseline = await getRun(baselineId);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return (
          <div className="space-y-4">
            <h1 className="text-lg font-semibold">Run comparison</h1>
            <EmptyState
              title="Baseline run unavailable."
              description={`Baseline ${baselineId} could not be loaded.`}
            />
          </div>
        );
      }
      throw error;
    }

    const [currentResults, baselineResults, experiment, policies, historyRuns] =
      await Promise.all([
        listCaseResults(current.id),
        listCaseResults(baseline.id),
        current.experiment_id
          ? getExperiment(current.experiment_id).catch(() => null)
          : Promise.resolve(null),
        current.experiment_id
          ? listRegressionPolicies(current.experiment_id).catch(() => [])
          : Promise.resolve([]),
        current.experiment_id
          ? listExperimentRuns(current.experiment_id).catch(() => [] as EvaluationRun[])
          : Promise.resolve([] as EvaluationRun[]),
      ]);

    const regression = current.regression;
    const preferredMetrics = [
      ...policies.map((p) => p.metric_name),
      ...Object.keys(regression?.aggregate || {}),
    ];

    const metricRows = buildMetricComparisons(current, baseline, regression);
    const summary = summarizeMetricComparisons(metricRows, current.regression_status);
    const caseRows = buildCaseComparisons(
      currentResults,
      baselineResults,
      regression,
      preferredMetrics,
    );

    const incompatibleDatasets =
      current.dataset_version_id !== baseline.dataset_version_id;

    let testCasesById: Record<string, TestCase> = {};
    try {
      const cases = await listTestCases(current.dataset_version_id);
      testCasesById = Object.fromEntries(cases.map((c) => [c.id, c]));
    } catch {
      testCasesById = {};
    }

    const historyMetric =
      preferredMetrics[0] ??
      metricRows[0]?.metric ??
      Object.keys(current.metric_aggregates || {})[0] ??
      null;

    return (
      <div className="space-y-6">
        <PageHeaderLinks
          items={[
            { href: `/runs/${current.id}`, label: `Run ${shortId(current.id)}` },
            { href: `/runs/${current.id}/compare`, label: "Compare" },
          ]}
        />

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold">Run comparison</h1>
            <p className="mt-1 text-sm text-muted">
              Current vs experiment baseline — regression data from the EVALSURE API.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={current.status} />
            <StatusBadge status={current.regression_status} kind="regression" />
          </div>
        </div>

        <dl className="grid gap-3 rounded border border-border bg-panel p-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <Info label="Current run">
            <Link href={`/runs/${current.id}`} className="font-mono text-xs text-accent hover:underline">
              {current.id}
            </Link>
          </Info>
          <Info label="Baseline">
            <Link href={`/runs/${baseline.id}`} className="font-mono text-xs text-accent hover:underline">
              {baseline.id}
            </Link>
          </Info>
          <Info label="Experiment">
            {experiment ? (
              <Link href={`/experiments/${experiment.id}`} className="text-accent hover:underline">
                {experiment.name}
              </Link>
            ) : current.experiment_id ? (
              shortId(current.experiment_id)
            ) : (
              "—"
            )}
          </Info>
          <Info label="Dataset (current)">
            {current.dataset_version
              ? `v${current.dataset_version.version}`
              : shortId(current.dataset_version_id)}
          </Info>
          <Info label="Dataset (baseline)">
            {baseline.dataset_version
              ? `v${baseline.dataset_version.version}`
              : shortId(baseline.dataset_version_id)}
          </Info>
          <Info label="Current status">{current.status}</Info>
          <Info label="Regression">
            <StatusBadge status={current.regression_status} kind="regression" />
          </Info>
        </dl>

        {incompatibleDatasets ? (
          <div className="rounded border border-amber-800/40 bg-amber-950/20 px-4 py-3 text-sm text-amber-100/90">
            These runs use different dataset versions and some test cases cannot be compared.
            Incompatible cases are marked NOT_COMPARABLE — not as regressions.
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard label="Metrics evaluated" value={String(summary.metricsEvaluated)} />
          <SummaryCard label="Metrics improved" value={String(summary.metricsImproved)} />
          <SummaryCard label="Metrics degraded" value={String(summary.metricsDegraded)} />
          <div className="rounded border border-border bg-panel px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-muted">Regression status</p>
            <div className="mt-2">
              <StatusBadge status={summary.regressionStatus} kind="regression" />
            </div>
          </div>
        </div>

        <RegressionBanner
          status={current.regression_status}
          regression={regression}
          metricsChecked={metricRows.length}
        />

        <section className="space-y-3">
          <h2 className="text-sm font-medium">Metric comparison</h2>
          <MetricComparisonTable rows={metricRows} />
        </section>

        <MetricHistory
          runs={historyRuns}
          metric={historyMetric}
          baselineId={baseline.id}
          currentId={current.id}
        />

        <CaseComparisonPanel rows={caseRows} testCasesById={testCasesById} />

        <details className="rounded border border-border bg-panel p-3">
          <summary className="cursor-pointer text-sm text-muted">Raw JSON (debug)</summary>
          <div className="mt-3 space-y-3">
            <JsonPreview
              value={{
                current_run_id: current.id,
                baseline_run_id: baseline.id,
                regression_status: current.regression_status,
                metric_rows: metricRows,
                regressed_case_count: regression?.regressed_case_count ?? 0,
                notes: regression?.notes ?? [],
              }}
              label="comparison summary"
              compact={false}
            />
          </div>
        </details>
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/runs/${runId}/compare`} />;
  }
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1">{children}</dd>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-panel px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-2 font-mono text-2xl text-ink">{value}</p>
    </div>
  );
}

function RegressionBanner({
  status,
  regression,
  metricsChecked,
}: {
  status: string;
  regression: EvaluationRun["regression"];
  metricsChecked: number;
}) {
  if (status === "FAIL") {
    const violated = (regression?.violations || []).length;
    const metrics = Object.keys(regression?.aggregate || {}).filter(
      (m) => regression?.aggregate?.[m]?.violated,
    );
    return (
      <div className="space-y-2 rounded border border-rose-800/50 bg-rose-950/25 px-4 py-4">
        <p className="text-sm font-semibold text-rose-200">REGRESSION DETECTED</p>
        <ul className="space-y-1 text-sm text-rose-100/85">
          <li>Violated policies: {violated || metrics.length}</li>
          <li>Regressed cases: {regression?.regressed_case_count ?? 0}</li>
          <li>Affected metrics: {metrics.length ? metrics.join(", ") : "—"}</li>
        </ul>
        {Object.keys(regression?.aggregate || {}).length > 0 ? (
          <ul className="mt-2 space-y-1 font-mono text-xs text-rose-100/75">
            {Object.entries(regression?.aggregate || {}).map(([name, data]) => (
              <li key={name}>
                {name}: baseline={String(data.baseline)} current={String(data.current)} delta=
                {String(data.delta)} threshold={String(data.threshold)}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  if (status === "PASS") {
    return (
      <div className="rounded border border-emerald-800/40 bg-emerald-950/20 px-4 py-4 text-sm text-emerald-100/90">
        <p className="font-semibold">NO REGRESSION DETECTED</p>
        <p className="mt-1 text-emerald-200/80">Metrics checked: {metricsChecked}</p>
      </div>
    );
  }

  const notes = regression?.notes?.length
    ? regression.notes.join(" ")
    : "No baseline, no policies, or evaluate-regression has not been run.";

  return (
    <div className="rounded border border-border bg-elevated/40 px-4 py-4 text-sm text-muted">
      <p className="font-medium text-ink">Regression NOT_EVALUATED</p>
      <p className="mt-1">{notes}</p>
    </div>
  );
}

function MetricHistory({
  runs,
  metric,
  baselineId,
  currentId,
}: {
  runs: EvaluationRun[];
  metric: string | null;
  baselineId: string;
  currentId: string;
}) {
  if (!metric || runs.length === 0) {
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-medium">Metric history</h2>
        <EmptyState title="Metric history unavailable" />
      </section>
    );
  }

  const points = runs
    .slice()
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
    .map((run) => ({
      id: run.id,
      created_at: run.created_at,
      average: run.metric_aggregates?.[metric]?.average,
      label:
        run.id === currentId ? "current" : run.id === baselineId ? "baseline" : shortId(run.id),
    }))
    .filter((p) => typeof p.average === "number");

  if (points.length < 2) {
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-medium">Metric history ({metric})</h2>
        <EmptyState title="Metric history unavailable" description="Need multiple runs with aggregates." />
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium">Metric history · {metric}</h2>
      <div className="overflow-x-auto rounded border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-elevated/80 text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="border-b border-border px-3 py-2 text-left">Run</th>
              <th className="border-b border-border px-3 py-2 text-left">Date</th>
              <th className="border-b border-border px-3 py-2 text-left">Average</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-panel/40">
            {points.map((point) => (
              <tr key={point.id} className="hover:bg-elevated/40">
                <td className="px-3 py-2 font-mono text-xs">
                  <Link href={`/runs/${point.id}`} className="text-accent hover:underline">
                    {point.label}
                  </Link>
                </td>
                <td className="px-3 py-2 text-xs text-muted">{formatDate(point.created_at)}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {typeof point.average === "number" ? point.average.toFixed(4) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
