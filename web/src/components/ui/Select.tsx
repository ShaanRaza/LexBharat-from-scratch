import type { SelectHTMLAttributes } from "react";

// One labelled drop-down, styled like TextField so every form looks the same.
export function Select({ label, className = "", children, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return (
    <label className="flex flex-col gap-1 text-small font-semibold">
      {label}
      <select
        {...rest}
        className={`rounded-chip border border-line bg-page px-3 py-2 text-body font-normal text-ink outline-none focus:border-accent ${className}`}
      >
        {children}
      </select>
    </label>
  );
}
