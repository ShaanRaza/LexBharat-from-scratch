"use client";
import { useState } from "react";
import { Button, Dialog } from "@/components/ui";
import {
  MATTER_CANCEL,
  MATTER_DELETE,
  MATTER_DELETE_ALL,
  MATTER_DELETE_ALL_WARNING,
  MATTER_DELETE_FAILED,
  MATTER_DELETE_ONLY,
  MATTER_DELETE_TITLE,
} from "@/lib/copy";
import { wordsFor } from "@/lib/matters/label";
import type { MatterDeleteMode, MatterKind } from "@/lib/api/types";

// Deleting asks WHICH delete is meant. Neither choice is pre-selected and Delete stays
// off until one is picked, so a client's work is never removed or orphaned by a default.
export function DeleteMatterDialog({
  kind,
  onConfirm,
  onCancel,
}: {
  kind: MatterKind;
  onConfirm: (mode: MatterDeleteMode) => Promise<void>;
  onCancel: () => void;
}) {
  const one = wordsFor(kind).one;
  const [mode, setMode] = useState<MatterDeleteMode | null>(null);
  const [state, setState] = useState<"idle" | "working" | "failed">("idle");
  async function go() {
    if (!mode) return;
    setState("working");
    try {
      await onConfirm(mode);
    } catch {
      setState("failed");
    }
  }
  return (
    <Dialog title={MATTER_DELETE_TITLE(one)} onClose={onCancel}>
      <fieldset className="flex flex-col gap-2" disabled={state === "working"}>
        {(
          [
            ["unfile", MATTER_DELETE_ONLY(one)],
            ["everything", MATTER_DELETE_ALL(one)],
          ] as const
        ).map(([value, text]) => (
          <label key={value} className="flex items-start gap-2 text-body">
            <input type="radio" name="delete-mode" value={value} checked={mode === value} onChange={() => setMode(value)} className="mt-1" />
            <span>{text}</span>
          </label>
        ))}
      </fieldset>
      {mode === "everything" && <p className="text-small text-danger">{MATTER_DELETE_ALL_WARNING}</p>}
      {state === "failed" && (
        <p role="alert" className="text-small text-danger">
          {MATTER_DELETE_FAILED}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button disabled={!mode || state === "working"} onClick={go}>
          {MATTER_DELETE}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {MATTER_CANCEL}
        </Button>
      </div>
    </Dialog>
  );
}
