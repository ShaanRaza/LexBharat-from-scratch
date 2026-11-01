import type { ReactNode } from "react";

// Small uppercase tag, e.g. "Sample" or "keyword results only".
export function Label({ children, plain = false }: { children: ReactNode; plain?: boolean }) {
  return (
    <span className={`inline-block w-fit max-w-full break-words rounded-chip bg-tint px-2 py-0.5 text-label font-bold text-ink ${plain ? "" : "uppercase tracking-wide"}`}>
      {children}
    </span>
  );
}
