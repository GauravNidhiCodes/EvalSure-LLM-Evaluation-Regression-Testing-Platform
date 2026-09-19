export function DataTable({
  headers,
  children,
}: {
  headers: string[];
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-x-auto rounded border border-border">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead className="bg-elevated/80 text-[11px] uppercase tracking-wide text-muted">
          <tr>
            {headers.map((header) => (
              <th key={header} className="border-b border-border px-3 py-2 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-panel/40">{children}</tbody>
      </table>
    </div>
  );
}
