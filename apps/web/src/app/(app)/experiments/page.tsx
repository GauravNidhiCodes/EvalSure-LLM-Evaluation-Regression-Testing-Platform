import Link from "next/link";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { listExperiments } from "@/lib/api/experiments";
import { listProjects } from "@/lib/api/projects";
import { shortId } from "@/lib/format";
import type { Experiment, Project } from "@/types/api";

export default async function ExperimentsIndexPage() {
  try {
    const projects = await listProjects();
    const rows: Array<{ project: Project; experiments: Experiment[] }> = [];
    for (const project of projects) {
      const experiments = await listExperiments(project.id).catch(() => [] as Experiment[]);
      if (experiments.length) rows.push({ project, experiments });
    }
    const total = rows.reduce((sum, row) => sum + row.experiments.length, 0);

    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-semibold">Experiments</h1>
          <p className="mt-1 text-sm text-muted">Experiments across projects.</p>
        </div>
        {total === 0 ? (
          <EmptyState title="No experiments yet." />
        ) : (
          <div className="space-y-4">
            {rows.map(({ project, experiments }) => (
              <section key={project.id} className="rounded border border-border bg-panel p-4">
                <Link
                  href={`/projects/${project.id}/experiments`}
                  className="text-sm font-medium text-accent hover:underline"
                >
                  {project.name}
                </Link>
                <ul className="mt-3 space-y-2">
                  {experiments.map((exp) => (
                    <li key={exp.id} className="flex flex-wrap items-center gap-3 text-sm">
                      <Link href={`/experiments/${exp.id}`} className="text-ink hover:text-accent">
                        {exp.name}
                      </Link>
                      <span className="font-mono text-xs text-muted">
                        baseline {exp.baseline_run_id ? shortId(exp.baseline_run_id) : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    );
  } catch (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">Experiments</h1>
        <ErrorState error={error} retryHref="/experiments" />
      </div>
    );
  }
}
