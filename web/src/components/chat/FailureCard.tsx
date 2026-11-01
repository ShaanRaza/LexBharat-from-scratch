import { Card } from "@/components/ui";
import { FAILURES } from "@/lib/copy";
import type { FailureKind } from "@/lib/chat/state";

// One screen per failure kind, wording from lib/copy.ts (docs/UX-COPY.md).
export function FailureCard({ kind, onRetry }: { kind: FailureKind; onRetry?: () => void }) {
  const c = FAILURES[kind];
  return (
    <Card role="alert" data-failure={kind} className="border-notfound">
      <h3 className="text-lead font-bold text-notfound">{c.title}</h3>
      <p className="mt-2">{c.body}</p>
      <p className="mt-1 text-ink-soft">{c.hint}</p>
      {kind === "serviceError" && onRetry && (
        <button onClick={onRetry} className="mt-3 text-small font-semibold text-accent underline">
          Try again
        </button>
      )}
    </Card>
  );
}
