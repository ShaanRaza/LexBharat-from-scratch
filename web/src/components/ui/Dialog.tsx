"use client";
import { useEffect, useRef, type ReactNode } from "react";

// A modal box: a backdrop, a titled panel, Escape to close, focus moved inside. Styled
// only from tokens; it knows nothing about what it asks.
export function Dialog({
  title,
  onClose,
  children,
  placement = "center",
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  placement?: "center" | "sheet"; // "sheet" rises from the bottom on a phone
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className={`fixed inset-0 z-20 flex justify-center bg-backdrop ${placement === "sheet" ? "items-end" : "items-center p-gutter"}`}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`flex w-full max-w-reading flex-col gap-4 border border-line bg-page p-card outline-none ${placement === "sheet" ? "rounded-t-card" : "rounded-card"}`}
      >
        <h2 className="text-lead font-bold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
