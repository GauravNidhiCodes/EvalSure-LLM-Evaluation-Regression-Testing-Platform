import Link from "next/link";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { listExperiments } from "@/lib/api/experiments";
import { getProject } from "@/lib/api/projects";
import { formatDate, shortId } from "@/lib/format";

export default async function ProjectExperimentsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  try {
    const [project, experiments] = await Promise.all([
      getProject(projectId),
      listExperiments(projectId),
    ]);
    return (
      <div className="space-y-4">
        <PageHeaderLinks
          items={[
            { href: "/projects", label: "Projects" },
            { href: `/projects/${projectId}`, label: project.name },
            { href: `/projects/${projectId}/experiments`, label: "Experiments" },
          ]}
        />
        <h1 className="text-lg font-semibold">Experiments</h1>
        {experiments.length === 0 ? (
          <EmptyState title="No experiments yet." />
        ) : (
          <DataTable headers={["Name", "Baseline", "Description", "Created"]}>
            {experiments.map((exp) => (
              <tr key={exp.id} className="hover:bg-elevated/40">
                <td className="px-3 py-2">
                  <Link
                    href={`/experiments/${exp.id}`}
                    className="font-medium text-accent hover:underline"
                  >
                    {exp.name}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted">
                  {exp.baseline_run_id ? (
                    <Link href={`/runs/${exp.baseline_run_id}`} className="text-accent hover:underline">
                      {shortId(exp.baseline_run_id)}
                    </Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-3 py-2 text-sm text-muted">{exp.description || "—"}</td>
                <td className="px-3 py-2 text-xs text-muted">{formatDate(exp.created_at)}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/projects/${projectId}/experiments`} />;
  }
}
