export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="rounded border border-dashed border-border bg-panel/40 px-4 py-10 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {description ? <p className="mt-2 text-sm text-muted">{description}</p> : null}
    </div>
  );
}
