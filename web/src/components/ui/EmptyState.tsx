import Link from "next/link";
import type { ReactNode } from "react";

// What a screen shows when there is nothing to show yet: a plain title, one line on what
// will appear here or what to do, and at most one action. Never a blank table or a bare
// header. Interface words only: nothing about the law goes in an empty state.
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: { label: string; href: string } | ReactNode;
}) {
  const act =
    action && typeof action === "object" && "href" in (action as object) ? (
      <Link href={(action as { href: string }).href} className="font-semibold text-accent underline">
        {(action as { label: string }).label}
      </Link>
    ) : (
      (action as ReactNode)
    );
  return (
    <section data-empty className="flex max-w-measure flex-col gap-1 rounded-card border border-dashed border-line p-card-sm sm:p-card">
      <h2 className="text-lead font-bold">{title}</h2>
      {hint && <p className="text-ink-soft">{hint}</p>}
      {act && <div className="mt-2 text-small">{act}</div>}
    </section>
  );
}
