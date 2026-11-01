import type { ReactNode } from "react";

export type CardTone = "plain" | "panel" | "verified" | "notfound" | "danger";

const TONES: Record<CardTone, string> = {
  plain: "bg-page border-line",
  panel: "bg-panel border-line",
  verified: "bg-verified-tint border-verified",
  notfound: "bg-notfound-tint border-notfound",
  danger: "bg-danger-tint border-danger",
};

/** A rounded box with a thin border. Every box on the site uses this. */
export function Card({
  tone = "plain",
  as: Tag = "div",
  children,
}: {
  tone?: CardTone;
  as?: "div" | "section" | "article" | "aside";
  children: ReactNode;
}) {
  return (
    <Tag className={`rounded-card border p-5 shadow-card ${TONES[tone]}`}>{children}</Tag>
  );
}
