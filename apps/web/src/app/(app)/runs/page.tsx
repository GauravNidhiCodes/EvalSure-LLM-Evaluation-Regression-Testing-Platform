import Link from "next/link";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { listProjectRuns } from "@/lib/api/experiments";
import { listProjects } from "@/lib/api/projects";
import { formatDate, shortId } from "@/lib/format";
import type { EvaluationRun } from "@/types/api";

export default async function RunsIndexPage() {
  try {
    const projects = await listProjects();
    const batches = await Promise.all(
      projects.map((p) => listProjectRuns(p.id).catch(() => [] as EvaluationRun[])),
    );
    const runs = batches.flat().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-semibold">Runs</h1>
          <p className="mt-1 text-sm text-muted">
            Evaluation runs aggregated from experiment endpoints.
          </p>
        </div>
        {runs.length === 0 ? (
          <EmptyState title="No evaluation runs yet." />
        ) : (
          <DataTable headers={["Run", "Project", "Status", "Regression", "Created"]}>
            {runs.map((run) => (
              <tr key={run.id} className="hover:bg-elevated/40">
                <td className="px-3 py-2 font-mono text-xs">
                  <Link href={`/runs/${run.id}`} className="text-accent hover:underline">
                    {shortId(run.id)}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted">
                  <Link
                    href={`/projects/${run.project_id}`}
                    className="text-accent hover:underline"
                  >
                    {shortId(run.project_id)}
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
      </div>
    );
  } catch (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">Runs</h1>
        <ErrorState error={error} retryHref="/runs" />
      </div>
    );
  }
}
