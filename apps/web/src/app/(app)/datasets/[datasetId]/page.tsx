import Link from "next/link";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { JsonPreview } from "@/components/ui/JsonPreview";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { getDataset, listDatasetVersions } from "@/lib/api/datasets";
import { formatDate, shortId } from "@/lib/format";

export default async function DatasetDetailPage({
  params,
}: {
  params: Promise<{ datasetId: string }>;
}) {
  const { datasetId } = await params;
  try {
    const [dataset, versions] = await Promise.all([
      getDataset(datasetId),
      listDatasetVersions(datasetId),
    ]);
    return (
      <div className="space-y-5">
        <PageHeaderLinks
          items={[
            { href: `/projects/${dataset.project_id}`, label: "Project" },
            { href: `/projects/${dataset.project_id}/datasets`, label: "Datasets" },
            { href: `/datasets/${dataset.id}`, label: dataset.name },
          ]}
        />
        <div>
          <h1 className="text-lg font-semibold">{dataset.name}</h1>
          <p className="mt-1 text-sm text-muted">{dataset.description || "No description"}</p>
        </div>
        <dl className="grid gap-3 rounded border border-border bg-panel p-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Dataset ID</dt>
            <dd className="mt-1 break-all font-mono text-xs">{dataset.id}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Created</dt>
            <dd className="mt-1">{formatDate(dataset.created_at)}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-muted">Metadata</dt>
            <dd className="mt-2">
              <JsonPreview value={dataset.metadata} label="metadata" />
            </dd>
          </div>
        </dl>
        <section className="space-y-3">
          <h2 className="text-sm font-medium">Versions</h2>
          {versions.length === 0 ? (
            <EmptyState title="No dataset versions." />
          ) : (
            <DataTable headers={["Version", "ID", "Content hash", "Cases", "Created"]}>
              {versions.map((version) => (
                <tr key={version.id} className="hover:bg-elevated/40">
                  <td className="px-3 py-2">
                    <Link
                      href={`/datasets/${dataset.id}/versions/${version.id}`}
                      className="font-mono text-accent hover:underline"
                    >
                      v{version.version}
                    </Link>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted">{shortId(version.id)}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted">
                    {shortId(version.content_hash, 12)}
                  </td>
                  <td className="px-3 py-2 text-sm">{version.test_case_count ?? "—"}</td>
                  <td className="px-3 py-2 text-xs text-muted">{formatDate(version.created_at)}</td>
                </tr>
              ))}
            </DataTable>
          )}
        </section>
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/datasets/${datasetId}`} />;
  }
}
