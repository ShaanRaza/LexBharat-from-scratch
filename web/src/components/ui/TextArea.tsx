import type { TextareaHTMLAttributes } from "react";

// One labelled multi-line input, styled like TextField.
export function TextArea({ label, className = "", ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  return (
    <label className="flex flex-col gap-1 text-small font-semibold">
      {label}
      <textarea
        {...rest}
        className={`rounded-chip border border-line bg-page px-3 py-2 text-body font-normal text-ink outline-none focus:border-accent ${className}`}
      />
    </label>
  );
}
