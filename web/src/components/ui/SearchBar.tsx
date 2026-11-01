"use client";
import { useState, type ReactNode } from "react";
import { Button } from "./Button";

// Presentational only: it hands the text to onSubmit and knows nothing about search.
// Give it `value` and `onChange` to control the text from outside (so a helper can fill
// the box); without them it keeps its own text. `below` is a slot under the input row.
export function SearchBar({
  onSubmit,
  disabled = false,
  placeholder = "Ask a legal question in plain words",
  initial = "",
  value,
  onChange,
  actions,
  below,
}: {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  initial?: string;
  value?: string;
  onChange?: (text: string) => void;
  actions?: ReactNode;
  below?: ReactNode;
}) {
  const [own, setOwn] = useState(initial);
  const text = value ?? own;
  const set = (t: string) => {
    setOwn(t);
    onChange?.(t);
  };
  return (
    <div className="flex flex-col gap-2">
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const t = text.trim();
          if (t) onSubmit(t);
        }}
      >
        <input
          value={text}
          onChange={(e) => set(e.target.value)}
          placeholder={placeholder}
          aria-label="Your question"
          className="min-w-0 flex-1 rounded-pill border border-line bg-page px-5 py-3 text-body text-ink outline-none focus:border-accent"
        />
        <Button type="submit" disabled={disabled}>
          Ask
        </Button>
        {actions}
      </form>
      {below}
    </div>
  );
}
