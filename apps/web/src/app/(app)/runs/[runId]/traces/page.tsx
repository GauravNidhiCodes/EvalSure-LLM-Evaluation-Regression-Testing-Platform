import Link from "next/link";
import { TraceTimeline } from "@/components/traces/TraceTimeline";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeaderLinks } from "@/components/ui/PageHeaderLinks";
import { getRun } from "@/lib/api/runs";
import { getRunTraces } from "@/lib/api/traces";
import { shortId } from "@/lib/format";

export default async function RunTracesPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  try {
    const [run, traces] = await Promise.all([getRun(runId), getRunTraces(runId)]);
    return (
      <div className="space-y-5">
        <PageHeaderLinks
          items={[
            { href: `/runs/${runId}`, label: `Run ${shortId(runId)}` },
            { href: `/runs/${runId}/traces`, label: "Traces" },
          ]}
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold">Run traces</h1>
            <p className="mt-1 text-sm text-muted">
              Chronological evaluation lifecycle events for this run.
            </p>
          </div>
          <Link
            href={`/runs/${run.id}`}
            className="rounded border border-border px-2 py-1 text-xs text-accent hover:bg-elevated"
          >
            Back to run
          </Link>
        </div>
        {traces.events.length === 0 ? (
          <EmptyState title="No traces for this run." />
        ) : (
          <TraceTimeline events={traces.events} />
        )}
      </div>
    );
  } catch (error) {
    return <ErrorState error={error} retryHref={`/runs/${runId}/traces`} />;
  }
}
