import type { ReactNode } from "react";

// Small uppercase tag, e.g. "Sample" or "keyword results only".
export function Label({ children }: { children: ReactNode }) {
  return (
    <span className="inline-block rounded-chip bg-tint px-2 py-0.5 text-label font-bold uppercase tracking-wide text-ink">
      {children}
    </span>
  );
}
