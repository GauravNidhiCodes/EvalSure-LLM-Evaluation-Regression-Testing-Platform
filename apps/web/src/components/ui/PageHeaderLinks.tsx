import Link from "next/link";

export function PageHeaderLinks({
  items,
}: {
  items: Array<{ href: string; label: string }>;
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-2 text-xs text-muted">
      {items.map((item, index) => (
        <span key={item.href} className="inline-flex items-center gap-2">
          {index > 0 ? <span className="text-border">/</span> : null}
          <Link href={item.href} className="hover:text-accent">
            {item.label}
          </Link>
        </span>
      ))}
    </div>
  );
}
