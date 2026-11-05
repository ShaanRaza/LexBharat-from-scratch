"use client";
import { useState } from "react";
import { Button } from "@/components/ui";
import { ACTION_COPY, ACTION_EXPORT, ACTION_REWRITE, COPIED, COPY_FAILED } from "@/lib/copy";

// Copy / Export / Rewrite under a finished answer. It is given the text to copy (already
// built from the verified citations event) and does not know how it was made. Rewrite
// hands the question back to the input box to edit: no model rewrites a verified answer.
export function AnswerActions({
  text,
  onExport,
  onRewrite,
  copy,
}: {
  text: string | null;
  onExport: (text: string) => void;
  onRewrite: () => void;
  copy: (text: string) => Promise<boolean>;
}) {
  const [note, setNote] = useState<string | null>(null);
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Answer actions">
      <Button
        variant="secondary"
        disabled={!text}
        onClick={async () => text && setNote((await copy(text)) ? COPIED : COPY_FAILED)}
      >
        {ACTION_COPY}
      </Button>
      <Button variant="secondary" disabled={!text} onClick={() => text && onExport(text)}>
        {ACTION_EXPORT}
      </Button>
      <Button variant="secondary" onClick={onRewrite}>
        {ACTION_REWRITE}
      </Button>
      {note && (
        <span role="status" className="text-small text-ink-soft">
          {note}
        </span>
      )}
    </div>
  );
}
