"use client";
import { Button, Card, TextArea } from "@/components/ui";
import type { ImproveState } from "@/lib/chat/useImprove";
import {
  IMPROVE_DISMISS,
  IMPROVE_EDIT_LABEL,
  IMPROVE_FAILED,
  IMPROVE_LABEL,
  IMPROVE_NO_CHANGE,
  IMPROVE_USE,
  IMPROVE_WORKING,
} from "@/lib/copy";

// The button that sits beside the input box, and the panel under it that shows the
// suggestion as EDITABLE text. Nothing is sent until the user accepts it into the box
// and presses Ask. Presentational: state and actions come from useImprove.
export function ImproveButton({ state, canImprove, onImprove }: { state: ImproveState; canImprove: boolean; onImprove: () => void }) {
  return (
    <Button type="button" variant="secondary" disabled={!canImprove || state.status === "working"} onClick={onImprove}>
      {state.status === "working" ? IMPROVE_WORKING : IMPROVE_LABEL}
    </Button>
  );
}

export function ImprovePanel({
  state,
  onEdit,
  onUse,
  onDismiss,
}: {
  state: ImproveState;
  onEdit: (text: string) => void;
  onUse: (text: string) => void;
  onDismiss: () => void;
}) {
  if (state.status === "idle" || state.status === "working") return null;
  if (state.status === "unchanged" || state.status === "failed") {
    return (
      <Card role="status" className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-small">{state.status === "failed" ? IMPROVE_FAILED : IMPROVE_NO_CHANGE}</span>
        <Button variant="secondary" onClick={onDismiss}>
          {IMPROVE_DISMISS}
        </Button>
      </Card>
    );
  }
  return (
    <Card className="flex flex-col gap-3">
      <TextArea label={IMPROVE_EDIT_LABEL} value={state.text} rows={3} onChange={(e) => onEdit(e.target.value)} />
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={!state.text.trim()} onClick={() => onUse(state.text.trim())}>
          {IMPROVE_USE}
        </Button>
        <Button type="button" variant="secondary" onClick={onDismiss}>
          {IMPROVE_DISMISS}
        </Button>
      </div>
    </Card>
  );
}
