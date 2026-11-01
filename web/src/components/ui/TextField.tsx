import type { InputHTMLAttributes } from "react";

// One labelled input, used by every form so they all look the same.
export function TextField({
  label,
  className = "",
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="flex flex-col gap-1 text-small font-semibold">
      {label}
      <input
        {...rest}
        className={`rounded-chip border border-line bg-page px-3 py-2 text-body font-normal text-ink outline-none focus:border-accent ${className}`}
      />
    </label>
  );
}
