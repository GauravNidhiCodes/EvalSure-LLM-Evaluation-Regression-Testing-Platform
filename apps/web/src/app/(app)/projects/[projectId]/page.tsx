import Link from "next/link";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { getProject } from "@/lib/api/projects";
import { formatDate } from "@/lib/format";

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  try {
    const project = await getProject(projectId);
    return (
      <div className="space-y-5">
        <PageHeaderLinks
          items={[
            { href: "/projects", label: "Projects" },
            { href: `/projects/${project.id}`, label: project.name },
          ]}
        />
        <div>
          <h1 className="text-lg font-semibold">{project.name}</h1>
          <p className="mt-1 text-sm text-muted">{project.description || "No description"}</p>
        </div>
        <dl className="grid gap-3 rounded border border-border bg-panel p-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Project ID</dt>
            <dd className="mt-1 break-all font-mono text-xs">{project.id}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Created</dt>
            <dd className="mt-1">{formatDate(project.created_at)}</dd>
          </div>
        </dl>
        <div className="flex flex-wrap gap-2">
          <NavChip href={`/projects/${project.id}/datasets`} label="Datasets" />
          <NavChip href={`/projects/${project.id}/experiments`} label="Experiments" />
          <NavChip href={`/projects/${project.id}/runs`} label="Runs" />
        </div>
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/projects/${projectId}`} />;
  }
}

function NavChip({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="rounded border border-border bg-elevated px-3 py-2 text-sm text-ink hover:border-accent/50 hover:text-accent"
    >
      {label}
    </Link>
  );
}
