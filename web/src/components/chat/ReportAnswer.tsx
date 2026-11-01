"use client";
import { useState } from "react";
import { Button, Dialog, Select, TextArea } from "@/components/ui";
import { postFeedback } from "@/lib/api/client";
import {
  MATTER_CANCEL,
  RATE_THANKS,
  RATE_UP,
  REPORT_BUTTON,
  REPORT_EDIT_LABEL,
  REPORT_FAILED,
  REPORT_REASONS,
  REPORT_REASON_LABEL,
  REPORT_SEND,
  REPORT_THANKS,
} from "@/lib/copy";
import type { ReportReason } from "@/lib/api/types";

// "Helpful" and "Report a wrong answer" under a saved answer (POST /feedback exists). A
// report changes nothing about the answer: it goes to the admin queue to be looked at.
export function ReportAnswer({ messageId }: { messageId: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason>("citation");
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed" | "rated">("idle");

  async function send() {
    setState("sending");
    try {
      await postFeedback(messageId, { rating: "down", reason, comment: comment.trim() || undefined });
      setState("sent");
      setOpen(false);
    } catch {
      setState("failed");
    }
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="secondary"
        disabled={state === "rated" || state === "sent"}
        onClick={async () => {
          await postFeedback(messageId, { rating: "up" }).catch(() => {});
          setState("rated");
        }}
      >
        {RATE_UP}
      </Button>
      <Button variant="secondary" disabled={state === "sent"} onClick={() => setOpen(true)}>
        {REPORT_BUTTON}
      </Button>
      {state === "rated" && <span role="status" className="text-small text-ink-soft">{RATE_THANKS}</span>}
      {state === "sent" && <span role="status" className="text-small text-ink-soft">{REPORT_THANKS}</span>}
      {open && (
        <Dialog title={REPORT_BUTTON} onClose={() => setOpen(false)}>
          <Select label={REPORT_REASON_LABEL} value={reason} onChange={(e) => setReason(e.target.value as ReportReason)}>
            {(Object.keys(REPORT_REASONS) as ReportReason[]).map((r) => (
              <option key={r} value={r}>
                {REPORT_REASONS[r]}
              </option>
            ))}
          </Select>
          <TextArea label={REPORT_EDIT_LABEL} rows={3} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} />
          {state === "failed" && (
            <p role="alert" className="text-small text-warn">
              {REPORT_FAILED}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button disabled={state === "sending"} onClick={send}>
              {REPORT_SEND}
            </Button>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              {MATTER_CANCEL}
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
