import Link from "next/link";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { listDatasets } from "@/lib/api/datasets";
import { listProjects } from "@/lib/api/projects";
import type { Dataset, Project } from "@/types/api";

export default async function DatasetsIndexPage() {
  try {
    const projects = await listProjects();
    const rows: Array<{ project: Project; datasets: Dataset[] }> = [];
    for (const project of projects) {
      const datasets = await listDatasets(project.id).catch(() => [] as Dataset[]);
      if (datasets.length) rows.push({ project, datasets });
    }
    const total = rows.reduce((sum, row) => sum + row.datasets.length, 0);

    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-semibold">Datasets</h1>
          <p className="mt-1 text-sm text-muted">Datasets across projects.</p>
        </div>
        {total === 0 ? (
          <EmptyState title="No datasets yet." />
        ) : (
          <div className="space-y-4">
            {rows.map(({ project, datasets }) => (
              <section key={project.id} className="rounded border border-border bg-panel p-4">
                <Link
                  href={`/projects/${project.id}/datasets`}
                  className="text-sm font-medium text-accent hover:underline"
                >
                  {project.name}
                </Link>
                <ul className="mt-3 space-y-1">
                  {datasets.map((dataset) => (
                    <li key={dataset.id}>
                      <Link
                        href={`/datasets/${dataset.id}`}
                        className="text-sm text-ink hover:text-accent"
                      >
                        {dataset.name}
                      </Link>
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
        <h1 className="text-lg font-semibold">Datasets</h1>
        <ErrorState error={error} retryHref="/datasets" />
      </div>
    );
  }
}
