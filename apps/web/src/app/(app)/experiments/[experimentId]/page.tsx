import Link from "next/link";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  getExperiment,
  listExperimentRuns,
  listRegressionPolicies,
} from "@/lib/api/experiments";
import { formatDate, shortId } from "@/lib/format";

export default async function ExperimentDetailPage({
  params,
}: {
  params: Promise<{ experimentId: string }>;
}) {
  const { experimentId } = await params;
  try {
    const [experiment, runs, policies] = await Promise.all([
      getExperiment(experimentId),
      listExperimentRuns(experimentId),
      listRegressionPolicies(experimentId).catch(() => []),
    ]);
    return (
      <div className="space-y-6">
        <PageHeaderLinks
          items={[
            { href: `/projects/${experiment.project_id}`, label: "Project" },
            { href: `/projects/${experiment.project_id}/experiments`, label: "Experiments" },
            { href: `/experiments/${experiment.id}`, label: experiment.name },
          ]}
        />
        <div>
          <h1 className="text-lg font-semibold">{experiment.name}</h1>
          <p className="mt-1 text-sm text-muted">{experiment.description || "No description"}</p>
        </div>
        <dl className="grid gap-3 rounded border border-border bg-panel p-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Experiment ID</dt>
            <dd className="mt-1 break-all font-mono text-xs">{experiment.id}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Baseline run</dt>
            <dd className="mt-1 font-mono text-xs">
              {experiment.baseline_run_id ? (
                <Link
                  href={`/runs/${experiment.baseline_run_id}`}
                  className="text-accent hover:underline"
                >
                  {experiment.baseline_run_id}
                </Link>
              ) : (
                "—"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Created</dt>
            <dd className="mt-1">{formatDate(experiment.created_at)}</dd>
          </div>
        </dl>

        <section className="space-y-3">
          <h2 className="text-sm font-medium">Regression policies</h2>
          {policies.length === 0 ? (
            <EmptyState title="No regression policies configured." />
          ) : (
            <DataTable
              headers={["Metric", "Max drop", "Min aggregate", "Max regressed cases"]}
            >
              {policies.map((policy) => (
                <tr key={policy.id} className="hover:bg-elevated/40">
                  <td className="px-3 py-2 font-mono text-xs">{policy.metric_name}</td>
                  <td className="px-3 py-2 font-mono text-xs">{policy.max_allowed_drop}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {policy.min_aggregate_score ?? "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {policy.max_regressed_cases ?? "—"}
                  </td>
                </tr>
              ))}
            </DataTable>
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium">Evaluation runs</h2>
          {runs.length === 0 ? (
            <EmptyState title="No runs for this experiment." />
          ) : (
            <DataTable headers={["Run", "Status", "Regression", "Created"]}>
              {runs.map((run) => (
                <tr key={run.id} className="hover:bg-elevated/40">
                  <td className="px-3 py-2 font-mono text-xs">
                    <Link href={`/runs/${run.id}`} className="text-accent hover:underline">
                      {shortId(run.id)}
                      {run.is_baseline ? " (baseline)" : ""}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={run.regression_status} kind="regression" />
                  </td>
                  <td className="px-3 py-2 text-xs text-muted">{formatDate(run.created_at)}</td>
                </tr>
              ))}
            </DataTable>
          )}
        </section>
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/experiments/${experimentId}`} />;
  }
}
