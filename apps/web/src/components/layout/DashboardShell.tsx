import { Sidebar } from "@/components/layout/Sidebar";

export function DashboardShell({
  children,
  title,
  description,
  actions,
}: {
  children: React.ReactNode;
  title?: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-canvas text-ink lg:flex">
      <Sidebar />
      <div className="min-w-0 flex-1">
        {(title || actions) && (
          <header className="border-b border-border bg-panel/60 px-4 py-4 sm:px-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                {title ? <h1 className="text-lg font-semibold tracking-tight">{title}</h1> : null}
                {description ? (
                  <p className="mt-1 text-sm text-muted">{description}</p>
                ) : null}
              </div>
              {actions}
            </div>
          </header>
        )}
        <main className="px-4 py-5 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
