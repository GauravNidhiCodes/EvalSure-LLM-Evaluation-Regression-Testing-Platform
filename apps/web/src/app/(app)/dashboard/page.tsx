import Link from "next/link";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError } from "@/lib/api/client";
import { listProjects } from "@/lib/api/projects";
import { listExperiments, listProjectRuns } from "@/lib/api/experiments";
import { getAccessToken } from "@/lib/auth/session";
import { formatDate, formatScore, shortId } from "@/lib/format";
import type { EvaluationRun, Experiment, Project } from "@/types/api";

export const dynamic = "force-dynamic";

async function loadOverview(): Promise<{
  projects: Project[];
  experiments: Experiment[];
  runs: EvaluationRun[];
}> {
  const projects = await listProjects();
  const experimentBatches = await Promise.all(
    projects.map((p) => listExperiments(p.id).catch(() => [] as Experiment[])),
  );
  const experiments = experimentBatches.flat();
  const runBatches = await Promise.all(
    projects.slice(0, 10).map((p) => listProjectRuns(p.id).catch(() => [] as EvaluationRun[])),
  );
  const runs = runBatches.flat().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  return { projects, experiments, runs };
}

export default async function DashboardPage() {
  if (!(await getAccessToken())) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">Dashboard</h1>
        <ErrorState
          error={new ApiError("Sign in to load dashboard data.", 401)}
          retryHref="/login"
        />
      </div>
    );
  }

  try {
    const { projects, experiments, runs } = await loadOverview();
    const recent = runs.slice(0, 8);
    const latestRegression = recent.find((r) => r.regression_status !== "NOT_EVALUATED");

    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold">Dashboard</h1>
          <p className="mt-1 text-sm text-muted">
            Overview from existing EVALSURE list APIs (no invented aggregates).
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Projects" value={String(projects.length)} href="/projects" />
          <StatCard label="Experiments" value={String(experiments.length)} href="/experiments" />
          <StatCard label="Recent runs loaded" value={String(runs.length)} href="/runs" />
          <div className="rounded border border-border bg-panel px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-muted">Latest regression</p>
            <div className="mt-2">
              {latestRegression ? (
                <StatusBadge status={latestRegression.regression_status} kind="regression" />
              ) : (
                <span className="text-sm text-muted">No evaluated runs</span>
              )}
            </div>
          </div>
        </div>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">Recent evaluation runs</h2>
            <Link href="/runs" className="text-xs text-accent hover:underline">
              View all
            </Link>
          </div>
          {recent.length === 0 ? (
            <EmptyState title="No evaluation runs yet." />
          ) : (
            <DataTable
              headers={["Run", "Status", "Regression", "Metrics", "Created"]}
            >
              {recent.map((run) => (
                <tr key={run.id} className="hover:bg-elevated/40">
                  <td className="px-3 py-2 font-mono text-xs">
                    <Link href={`/runs/${run.id}`} className="text-accent hover:underline">
                      {shortId(run.id)}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={run.regression_status} kind="regression" />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted">
                    {Object.entries(run.metric_aggregates || {})
                      .slice(0, 2)
                      .map(([name, agg]) => `${name}=${formatScore(agg.average)}`)
                      .join(" · ") || "—"}
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
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">Dashboard</h1>
        <ErrorState error={error} retryHref="/dashboard" />
      </div>
    );
  }
}

function StatCard({
  label,
  value,
  href,
}: {
  label: string;
  value: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="rounded border border-border bg-panel px-4 py-3 transition hover:border-accent/40"
    >
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-2 font-mono text-2xl text-ink">{value}</p>
    </Link>
  );
}
