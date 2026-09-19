import Link from "next/link";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { listProjectRuns } from "@/lib/api/experiments";
import { listProjects } from "@/lib/api/projects";
import { shortId } from "@/lib/format";
import type { EvaluationRun } from "@/types/api";

export default async function TracesIndexPage() {
  try {
    const projects = await listProjects();
    const batches = await Promise.all(
      projects.map((p) => listProjectRuns(p.id).catch(() => [] as EvaluationRun[])),
    );
    const runs = batches
      .flat()
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .slice(0, 30);

    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-semibold">Traces</h1>
          <p className="mt-1 text-sm text-muted">
            Select a run to inspect chronological evaluation events.
          </p>
        </div>
        {runs.length === 0 ? (
          <EmptyState title="No traces available." description="Complete an evaluation run first." />
        ) : (
          <ul className="divide-y divide-border rounded border border-border bg-panel">
            {runs.map((run) => (
              <li key={run.id}>
                <Link
                  href={`/runs/${run.id}/traces`}
                  className="flex items-center justify-between px-3 py-3 text-sm hover:bg-elevated/40"
                >
                  <span className="font-mono text-xs text-accent">{shortId(run.id)}</span>
                  <span className="text-xs text-muted">{run.status}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  } catch (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">Traces</h1>
        <ErrorState error={error} retryHref="/traces" />
      </div>
    );
  }
}
