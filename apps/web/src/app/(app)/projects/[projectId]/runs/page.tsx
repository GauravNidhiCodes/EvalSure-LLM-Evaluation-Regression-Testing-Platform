import Link from "next/link";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { listProjectRuns } from "@/lib/api/experiments";
import { getProject } from "@/lib/api/projects";
import { formatDate, shortId } from "@/lib/format";

export default async function ProjectRunsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  try {
    const [project, runs] = await Promise.all([
      getProject(projectId),
      listProjectRuns(projectId),
    ]);
    return (
      <div className="space-y-4">
        <PageHeaderLinks
          items={[
            { href: "/projects", label: "Projects" },
            { href: `/projects/${projectId}`, label: project.name },
            { href: `/projects/${projectId}/runs`, label: "Runs" },
          ]}
        />
        <div>
          <h1 className="text-lg font-semibold">Runs</h1>
          <p className="mt-1 text-sm text-muted">
            Aggregated from experiment run lists (no dedicated project-runs endpoint).
          </p>
        </div>
        {runs.length === 0 ? (
          <EmptyState title="No evaluation runs yet." />
        ) : (
          <DataTable
            headers={["Run", "Experiment", "Dataset version", "Status", "Regression", "Created"]}
          >
            {runs.map((run) => (
              <tr key={run.id} className="hover:bg-elevated/40">
                <td className="px-3 py-2 font-mono text-xs">
                  <Link href={`/runs/${run.id}`} className="text-accent hover:underline">
                    {shortId(run.id)}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted">
                  {run.experiment_id ? (
                    <Link
                      href={`/experiments/${run.experiment_id}`}
                      className="text-accent hover:underline"
                    >
                      {shortId(run.experiment_id)}
                    </Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted">
                  {run.dataset_version
                    ? `v${run.dataset_version.version}`
                    : shortId(run.dataset_version_id)}
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
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/projects/${projectId}/runs`} />;
  }
}
