import Link from "next/link";

export type SidebarItem = { href: string; label: string };

// Generic list of links (e.g. recent conversations, or the sections of an Act).
export function Sidebar({ title, items, current }: { title: string; items: SidebarItem[]; current?: string }) {
  return (
    <aside className="w-full shrink-0 md:w-(--container-sidebar)">
      <h2 className="mb-2 font-sans text-label font-bold uppercase tracking-wide text-ink-soft">{title}</h2>
      <ul className="flex flex-col gap-1">
        {items.map((i) => (
          <li key={i.href}>
            <Link
              href={i.href}
              aria-current={current === i.href ? "page" : undefined}
              className={`block rounded-chip px-2 py-1.5 text-small text-ink hover:bg-panel ${current === i.href ? "bg-tint font-semibold" : ""}`}
            >
              {i.label}
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
