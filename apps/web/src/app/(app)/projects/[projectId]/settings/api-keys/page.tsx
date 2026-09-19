import Link from "next/link";
import { ApiKeysManager } from "@/components/settings/ApiKeysManager";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { listProjectApiKeys } from "@/lib/api/api-keys";
import { getProject } from "@/lib/api/projects";

export const dynamic = "force-dynamic";

export default async function ProjectApiKeysPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  try {
    const [project, keys] = await Promise.all([
      getProject(projectId),
      listProjectApiKeys(projectId),
    ]);
    return (
      <div className="space-y-5">
        <PageHeaderLinks
          items={[
            { href: "/projects", label: "Projects" },
            { href: `/projects/${project.id}`, label: project.name },
            { href: `/projects/${project.id}/settings/api-keys`, label: "API keys" },
          ]}
        />
        <div>
          <h1 className="text-lg font-semibold">API keys</h1>
          <p className="mt-1 text-sm text-muted">
            Project keys for SDK / CLI / CI. Plaintext is shown once at creation; only hashes are
            stored.
          </p>
        </div>
        <ApiKeysManager projectId={project.id} initialKeys={keys} />
        <p className="text-sm text-muted">
          <Link href={`/projects/${project.id}`} className="text-accent hover:underline">
            Back to project
          </Link>
        </p>
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/projects/${projectId}/settings/api-keys`} />;
  }
}
