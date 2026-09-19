export function LoadingSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-9 animate-pulse rounded border border-border bg-elevated/60"
        />
      ))}
    </div>
  );
}

export function PageLoading() {
  return (
    <div className="space-y-4">
      <div className="h-6 w-48 animate-pulse rounded bg-elevated" />
      <LoadingSkeleton rows={6} />
    </div>
  );
}
