import Link from "next/link";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { listProjects } from "@/lib/api/projects";
import { formatDate, shortId } from "@/lib/format";

export default async function ProjectsPage() {
  try {
    const projects = await listProjects();
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-semibold">Projects</h1>
          <p className="mt-1 text-sm text-muted">Projects owned by the authenticated user.</p>
        </div>
        {projects.length === 0 ? (
          <EmptyState title="No projects yet." description="Create a project via the API or CLI." />
        ) : (
          <DataTable headers={["Name", "ID", "Description", "Created"]}>
            {projects.map((project) => (
              <tr key={project.id} className="hover:bg-elevated/40">
                <td className="px-3 py-2">
                  <Link
                    href={`/projects/${project.id}`}
                    className="font-medium text-accent hover:underline"
                  >
                    {project.name}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-muted">{shortId(project.id)}</td>
                <td className="px-3 py-2 text-sm text-muted">{project.description || "—"}</td>
                <td className="px-3 py-2 text-xs text-muted">{formatDate(project.created_at)}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </div>
    );
  } catch (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">Projects</h1>
        <ErrorState error={error} retryHref="/projects" />
      </div>
    );
  }
}
