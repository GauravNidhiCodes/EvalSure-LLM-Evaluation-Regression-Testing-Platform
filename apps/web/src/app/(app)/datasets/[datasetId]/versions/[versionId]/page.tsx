import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { JsonPreview } from "@/components/ui/JsonPreview";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { getDataset, getDatasetVersion, listTestCases } from "@/lib/api/datasets";
import { formatDate, previewJson } from "@/lib/format";

export default async function DatasetVersionPage({
  params,
}: {
  params: Promise<{ datasetId: string; versionId: string }>;
}) {
  const { datasetId, versionId } = await params;
  try {
    const [dataset, version, cases] = await Promise.all([
      getDataset(datasetId),
      getDatasetVersion(versionId),
      listTestCases(versionId),
    ]);
    return (
      <div className="space-y-5">
        <PageHeaderLinks
          items={[
            { href: `/datasets/${datasetId}`, label: dataset.name },
            { href: `/datasets/${datasetId}/versions/${versionId}`, label: `v${version.version}` },
          ]}
        />
        <div>
          <h1 className="text-lg font-semibold">
            {dataset.name} · v{version.version}
          </h1>
          <p className="mt-1 font-mono text-xs text-muted">
            hash {version.content_hash} · {formatDate(version.created_at)}
          </p>
        </div>
        {cases.length === 0 ? (
          <EmptyState title="No test cases in this version." />
        ) : (
          <DataTable headers={["External ID", "Input", "Expected", "Tags", "Metadata"]}>
            {cases.map((testCase) => (
              <tr key={testCase.id} className="align-top hover:bg-elevated/40">
                <td className="px-3 py-2 font-mono text-xs">{testCase.external_id}</td>
                <td className="px-3 py-2 text-xs text-muted">
                  <JsonPreview value={testCase.input} label="input" />
                </td>
                <td className="px-3 py-2 text-xs text-muted">
                  <JsonPreview value={testCase.expected} label="expected" />
                </td>
                <td className="px-3 py-2 text-xs text-muted">
                  {testCase.tags.length ? testCase.tags.join(", ") : "—"}
                </td>
                <td className="px-3 py-2 text-xs text-muted">
                  {Object.keys(testCase.metadata || {}).length ? (
                    <JsonPreview value={testCase.metadata} label="metadata" />
                  ) : (
                    previewJson(testCase.metadata, 20)
                  )}
                </td>
              </tr>
            ))}
          </DataTable>
        )}
      </div>
    );
  } catch (error) {
    return (
      <ErrorState error={error} retryHref={`/datasets/${datasetId}/versions/${versionId}`} />
    );
  }
}
