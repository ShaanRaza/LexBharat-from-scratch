"use client";
import { Button, Card, PageShell } from "@/components/ui";
import { FAILURES } from "@/lib/copy";

// Last-resort screen if a page throws. Same wording as the chat service-error card.
export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <PageShell shell="public">
      <Card role="alert">
        <h1 className="text-lead font-bold text-notfound">Something went wrong</h1>
        <p className="mt-2 text-ink-soft">{FAILURES.serviceError.hint}</p>
        <Button className="mt-3" onClick={reset}>
          Try again
        </Button>
      </Card>
    </PageShell>
  );
}
