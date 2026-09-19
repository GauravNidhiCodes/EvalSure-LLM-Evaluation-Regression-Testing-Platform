import Link from "next/link";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { listDatasets } from "@/lib/api/datasets";
import { getProject } from "@/lib/api/projects";
import { formatDate, shortId } from "@/lib/format";

export default async function ProjectDatasetsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  try {
    const [project, datasets] = await Promise.all([
      getProject(projectId),
      listDatasets(projectId),
    ]);
    return (
      <div className="space-y-4">
        <PageHeaderLinks
          items={[
            { href: "/projects", label: "Projects" },
            { href: `/projects/${projectId}`, label: project.name },
            { href: `/projects/${projectId}/datasets`, label: "Datasets" },
          ]}
        />
        <h1 className="text-lg font-semibold">Datasets</h1>
        {datasets.length === 0 ? (
          <EmptyState title="No datasets yet." />
        ) : (
          <DataTable headers={["Name", "ID", "Description", "Created"]}>
            {datasets.map((dataset) => (
              <tr key={dataset.id} className="hover:bg-elevated/40">
                <td className="px-3 py-2">
                  <Link
                    href={`/datasets/${dataset.id}`}
                    className="font-medium text-accent hover:underline"
                  >
                    {dataset.name}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted">{shortId(dataset.id)}</td>
                <td className="px-3 py-2 text-sm text-muted">{dataset.description || "—"}</td>
                <td className="px-3 py-2 text-xs text-muted">{formatDate(dataset.created_at)}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/projects/${projectId}/datasets`} />;
  }
}
