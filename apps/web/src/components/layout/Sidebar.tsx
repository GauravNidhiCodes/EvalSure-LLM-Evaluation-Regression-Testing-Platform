"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects", label: "Projects" },
  { href: "/datasets", label: "Datasets" },
  { href: "/experiments", label: "Experiments" },
  { href: "/runs", label: "Runs" },
  { href: "/traces", label: "Traces" },
  { href: "/settings", label: "Settings" },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard" || pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  async function onLogout() {
    setLoggingOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      router.replace("/login");
      router.refresh();
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <>
      <div className="flex items-center justify-between border-b border-border bg-panel px-4 py-3 lg:hidden">
        <Link href="/dashboard" className="font-mono text-sm font-semibold tracking-wide text-ink">
          EVALSURE
        </Link>
        <button
          type="button"
          className="rounded border border-border px-2 py-1 text-xs text-muted hover:text-ink"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          Menu
        </button>
      </div>

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-56 border-r border-border bg-panel transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="hidden border-b border-border px-4 py-4 lg:block">
            <Link href="/dashboard" className="font-mono text-sm font-semibold tracking-wide text-ink">
              EVALSURE
            </Link>
            <p className="mt-1 text-[11px] text-muted">Evaluation dashboard</p>
          </div>
          <nav className="flex-1 space-y-0.5 p-3">
            {NAV.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={`block rounded px-3 py-2 text-sm ${
                    active
                      ? "bg-accent/15 font-medium text-accent"
                      : "text-muted hover:bg-elevated hover:text-ink"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="border-t border-border p-3">
            <button
              type="button"
              onClick={onLogout}
              disabled={loggingOut}
              className="w-full rounded border border-border px-3 py-2 text-left text-sm text-muted hover:bg-elevated hover:text-ink disabled:opacity-60"
            >
              {loggingOut ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </div>
      </aside>
      {open ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}
