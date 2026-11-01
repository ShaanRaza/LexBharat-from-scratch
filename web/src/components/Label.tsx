import type { ReactNode } from "react";

export type LabelTone = "neutral" | "accent" | "verified" | "notfound" | "danger";

const TONES: Record<LabelTone, string> = {
  neutral: "bg-panel text-muted border-line",
  accent: "bg-tint text-accent-hover border-line",
  verified: "bg-verified-tint text-verified border-verified",
  notfound: "bg-notfound-tint text-notfound border-notfound",
  danger: "bg-danger-tint text-danger border-danger",
};

/** A small pill of text, e.g. "Sample" or "in-force status not checked". */
export function Label({ tone = "neutral", children }: { tone?: LabelTone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 text-label font-label ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
