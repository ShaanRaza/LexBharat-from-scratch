import Link from "next/link";
import { Button } from "./Button";

export interface SidebarItem {
  id: string;
  title: string;
}

/** Conversation list. Hidden on phones to keep one column (design doc). */
export function Sidebar({
  items,
  activeId,
  loading,
}: {
  items: SidebarItem[];
  activeId?: string | null;
  loading?: boolean;
}) {
  return (
    <aside className="hidden w-sidebar shrink-0 flex-col gap-3 border-r border-line bg-panel p-4 md:flex">
      <Button href="/" variant="secondary">
        New question
      </Button>
      <h2 className="mt-2 text-label font-label uppercase text-muted">Your questions</h2>
      {loading && <p className="text-small text-muted">Loading...</p>}
      {!loading && items.length === 0 && (
        <p className="text-small text-muted">Nothing yet. Ask your first question.</p>
      )}
      <ul className="flex flex-col gap-1">
        {items.map((c) => (
          <li key={c.id}>
            <Link
              href={`/c/${encodeURIComponent(c.id)}`}
              aria-current={c.id === activeId ? "page" : undefined}
              className={`block truncate rounded-control px-3 py-2 text-small hover:bg-tint ${
                c.id === activeId ? "bg-tint font-label text-text" : "text-muted"
              }`}
            >
              {c.title}
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
