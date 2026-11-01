import type { HTMLAttributes } from "react";

export function Card({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={`rounded-card border border-line bg-panel p-card ${className}`}
    />
  );
}
