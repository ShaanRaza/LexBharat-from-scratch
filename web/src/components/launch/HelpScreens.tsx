"use client";
import Link from "next/link";
import { useState } from "react";
import { Button, Card, EmptyState, Label, Loading, TextArea, TextField } from "@/components/ui";
import { listHelp, postSupport } from "@/lib/api/client";
import { HELP_NONE, SUPPORT_EMAIL_LABEL, SUPPORT_FAILED, SUPPORT_MESSAGE_LABEL, SUPPORT_SEND, SUPPORT_THANKS, SAMPLE_LABEL } from "@/lib/copy";
import { canSubmit } from "@/lib/auth/consent";
import { useLoaded } from "@/lib/matters/useLoaded";

export function HelpIndex() {
  const help = useLoaded(() => listHelp(), "help");
  if (help.status === "loading") return <Loading />;
  if ((help.value ?? []).length === 0) return <EmptyState {...HELP_NONE} />;
  return (
    <ul className="flex flex-col gap-2">
      {help.value!.map((a) => (
        <li key={a.slug}>
          <Link href={`/help/${a.slug}`}>
            <Card className="flex flex-wrap items-center gap-2 break-words">
              <span className="font-semibold">{a.title}</span>
              {a.title.startsWith("Sample") && <Label>{SAMPLE_LABEL}</Label>}
            </Card>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function HelpArticleView({ slug }: { slug: string }) {
  const help = useLoaded(() => listHelp(), "help");
  if (help.status === "loading") return <Loading />;
  const a = help.value?.find((x) => x.slug === slug);
  if (!a) return <EmptyState title="This article was not found" action={{ label: "Back to help", href: "/help" }} />;
  return (
    <article className="flex max-w-measure flex-col gap-3">
      <h2 className="break-words text-title font-bold">{a.title}</h2>
      {a.body.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
    </article>
  );
}

// The support form. The message goes to the support inbox (POST /support, needed).
export function SupportForm() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done" | "failed">("idle");
  const ok = canSubmit(email, true) && message.trim().length > 0;
  if (state === "done") return <Card role="status">{SUPPORT_THANKS}</Card>;
  return (
    <form
      className="flex max-w-measure flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!ok) return;
        setState("sending");
        try {
          await postSupport({ email: email.trim(), message: message.trim() });
          setState("done");
        } catch {
          setState("failed");
        }
      }}
    >
      <TextField label={SUPPORT_EMAIL_LABEL} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <TextArea label={SUPPORT_MESSAGE_LABEL} rows={5} value={message} onChange={(e) => setMessage(e.target.value)} />
      {state === "failed" && (
        <p role="alert" className="text-small text-warn">
          {SUPPORT_FAILED}
        </p>
      )}
      <div>
        <Button type="submit" disabled={!ok || state === "sending"}>
          {SUPPORT_SEND}
        </Button>
      </div>
    </form>
  );
}
