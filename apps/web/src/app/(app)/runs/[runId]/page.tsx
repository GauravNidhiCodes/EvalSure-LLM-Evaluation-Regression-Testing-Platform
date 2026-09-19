import Link from "next/link";
import { CaseResultsTable } from "@/components/runs/CaseResultsTable";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getRun, listCaseResults } from "@/lib/api/runs";
import { formatDate, formatScore, shortId } from "@/lib/format";
import type { RegressedCase, RegressionInfo } from "@/types/api";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  try {
    const [run, results] = await Promise.all([getRun(runId), listCaseResults(runId)]);
    const aggregates = Object.entries(run.metric_aggregates || {});
    const regression = run.regression;

    return (
      <div className="space-y-6">
        <PageHeaderLinks
          items={[
            { href: `/projects/${run.project_id}/runs`, label: "Runs" },
            { href: `/runs/${run.id}`, label: shortId(run.id) },
          ]}
        />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold">Run detail</h1>
            <p className="mt-1 break-all font-mono text-xs text-muted">{run.id}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={run.status} />
            <StatusBadge status={run.regression_status} kind="regression" />
            {run.status === "COMPLETED" &&
            (run.baseline_run_id || run.regression?.baseline_run_id) ? (
              <Link
                href={`/runs/${run.id}/compare`}
                className="rounded border border-accent/40 bg-accent/10 px-2 py-1 text-xs font-medium text-accent hover:bg-accent/20"
              >
                Compare with Baseline
              </Link>
            ) : null}
            <Link
              href={`/runs/${run.id}/traces`}
              className="rounded border border-border px-2 py-1 text-xs text-accent hover:bg-elevated"
            >
              Traces
            </Link>
          </div>
        </div>

        <dl className="grid gap-3 rounded border border-border bg-panel p-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <Info label="Experiment">
            {run.experiment_id ? (
              <Link href={`/experiments/${run.experiment_id}`} className="text-accent hover:underline">
                {shortId(run.experiment_id)}
              </Link>
            ) : (
              "—"
            )}
          </Info>
          <Info label="Dataset version">
            {run.dataset_version
              ? `v${run.dataset_version.version} (${shortId(run.dataset_version.id)})`
              : shortId(run.dataset_version_id)}
          </Info>
          <Info label="Baseline run">
            {run.baseline_run_id ? (
              <Link href={`/runs/${run.baseline_run_id}`} className="text-accent hover:underline">
                {shortId(run.baseline_run_id)}
              </Link>
            ) : (
              "—"
            )}
          </Info>
          <Info label="Created">{formatDate(run.created_at)}</Info>
          <Info label="Started">{formatDate(run.started_at)}</Info>
          <Info label="Finished">{formatDate(run.finished_at)}</Info>
          <Info label="Cases">
            {run.completed_cases}/{run.total_cases} completed · {run.failed_cases} failed ·{" "}
            {run.pending_cases} pending
          </Info>
          {run.error_message ? <Info label="Error">{run.error_message}</Info> : null}
        </dl>

        <section className="space-y-3">
          <h2 className="text-sm font-medium">Metrics</h2>
          {aggregates.length === 0 ? (
            <EmptyState title="No metric aggregates for this run." />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {aggregates.map(([name, stats]) => (
                <div key={name} className="rounded border border-border bg-panel p-4">
                  <p className="font-mono text-sm text-ink">{name}</p>
                  <dl className="mt-3 space-y-1 text-xs text-muted">
                    <div className="flex justify-between">
                      <dt>Average</dt>
                      <dd className="font-mono text-ink">{formatScore(stats.average)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt>Minimum</dt>
                      <dd className="font-mono text-ink">{formatScore(stats.minimum)}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt>Maximum</dt>
                      <dd className="font-mono text-ink">{formatScore(stats.maximum)}</dd>
                    </div>
                  </dl>
                </div>
              ))}
            </div>
          )}
        </section>

        <RegressionSection regression={regression} status={run.regression_status} />

        <section className="space-y-3">
          <h2 className="text-sm font-medium">Case results</h2>
          {results.length === 0 ? (
            <EmptyState title="No case results submitted." />
          ) : (
            <CaseResultsTable results={results} />
          )}
        </section>
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/runs/${runId}`} />;
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

function RegressionSection({
  regression,
  status,
}: {
  regression: RegressionInfo | null;
  status: string;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium">Regression</h2>
        <StatusBadge status={status} kind="regression" />
      </div>
      {!regression || status === "NOT_EVALUATED" ? (
        <EmptyState
          title="Regression not evaluated."
          description="No baseline, no policies, or evaluate-regression has not been run."
        />
      ) : status === "PASS" ? (
        <div className="rounded border border-emerald-800/40 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-100/90">
          No configured regression policy was violated.
          {regression.baseline_run_id ? (
            <span className="mt-1 block font-mono text-xs text-emerald-200/70">
              Baseline {regression.baseline_run_id}
            </span>
          ) : null}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded border border-rose-800/40 bg-rose-950/20 px-4 py-3 text-sm text-rose-100/90">
            Regression FAIL · {regression.regressed_case_count} regressed case(s)
          </div>
          {Object.keys(regression.aggregate || {}).length > 0 ? (
            <DataTable
              headers={["Metric", "Baseline", "Current", "Delta", "Threshold", "Violated"]}
            >
              {Object.entries(regression.aggregate).map(([metric, data]) => (
                <tr key={metric} className="hover:bg-elevated/40">
                  <td className="px-3 py-2 font-mono text-xs">{metric}</td>
                  <td className="px-3 py-2 font-mono text-xs">{formatScore(data.baseline)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{formatScore(data.current)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{formatScore(data.delta)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{formatScore(data.threshold)}</td>
                  <td className="px-3 py-2 text-xs">
                    {data.violated ? (
                      <span className="text-rose-300">yes</span>
                    ) : (
                      <span className="text-muted">no</span>
                    )}
                  </td>
                </tr>
              ))}
            </DataTable>
          ) : null}
          {(regression.regressed_cases as RegressedCase[]).length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted">
                Regressed cases
              </h3>
              <DataTable
                headers={["Test case", "Metric", "Baseline", "Current", "Delta", "Reason"]}
              >
                {(regression.regressed_cases as RegressedCase[]).map((item, index) => (
                  <tr key={`${item.test_case_id}-${item.metric}-${index}`} className="hover:bg-elevated/40">
                    <td className="px-3 py-2 font-mono text-xs">{shortId(item.test_case_id)}</td>
                    <td className="px-3 py-2 font-mono text-xs">{item.metric}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {formatScore(item.baseline_score)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {formatScore(item.current_score)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{formatScore(item.delta)}</td>
                    <td className="px-3 py-2 text-xs text-muted">{item.reason}</td>
                  </tr>
                ))}
              </DataTable>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
