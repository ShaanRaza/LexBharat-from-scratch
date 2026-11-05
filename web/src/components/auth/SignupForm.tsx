"use client";
import { useState } from "react";
import { Button, Card, TextField } from "@/components/ui";
import { postConsent } from "@/lib/api/client";
import { CONSENT_NOTICE_VERSION, CONSENT_PURPOSE, CONSENT_TEXT } from "@/lib/copy";
import { canSubmit } from "@/lib/auth/consent";

// Account creation itself is Firebase's job in the browser (docs/API.md); wired later.
// This form records the consent against the notice version.
export function SignupForm() {
  const [email, setEmail] = useState("");
  const [consented, setConsented] = useState(false);
  const [state, setState] = useState<"idle" | "saving" | "done" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit(email, consented)) return;
    setState("saving");
    try {
      await postConsent({ notice_version: CONSENT_NOTICE_VERSION, purpose: CONSENT_PURPOSE });
      setState("done");
    } catch {
      setState("error");
    }
  }

  if (state === "done") return <Card>Thank you. We have recorded your consent.</Card>;
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <TextField label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <label className="flex items-start gap-2 text-small">
        <input type="checkbox" checked={consented} onChange={(e) => setConsented(e.target.checked)} className="mt-1" />
        <span>{CONSENT_TEXT}</span>
      </label>
      <p className="text-label text-ink-soft">Consent notice version: {CONSENT_NOTICE_VERSION}</p>
      {state === "error" && <p role="alert" className="text-small text-danger">Something went wrong. Please try again.</p>}
      <Button type="submit" disabled={!canSubmit(email, consented) || state === "saving"}>
        Create account
      </Button>
    </form>
  );
}
