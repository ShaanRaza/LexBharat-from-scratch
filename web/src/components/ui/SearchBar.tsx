"use client";
import { useState } from "react";
import { Button } from "./Button";

// Presentational only: it hands the text to onSubmit and knows nothing about search.
export function SearchBar({
  onSubmit,
  disabled = false,
  placeholder = "Ask a legal question in plain words",
  initial = "",
}: {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  initial?: string;
}) {
  const [text, setText] = useState(initial);
  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const t = text.trim();
        if (t) onSubmit(t);
      }}
    >
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        aria-label="Your question"
        className="min-w-0 flex-1 rounded-pill border border-line bg-page px-5 py-3 text-body text-ink outline-none focus:border-accent"
      />
      <Button type="submit" disabled={disabled}>
        Ask
      </Button>
    </form>
  );
}
