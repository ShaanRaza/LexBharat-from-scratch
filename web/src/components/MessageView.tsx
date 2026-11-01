import { copy } from "@/lib/copy";
import type { ChatMessage } from "@/hooks/chatState";
import { AnswerText } from "./AnswerText";
import { Card } from "./Card";
import { FailureNotice } from "./FailureNotice";
import { SourceCard } from "./SourceCard";

/** One chat turn: the user's question, or the assistant's answer with sources. */
export function MessageView({
  message,
  onRetry,
}: {
  message: ChatMessage;
  onRetry?: () => void;
}) {
  if (message.role === "user") {
    return (
      <div className="self-end rounded-card bg-tint px-4 py-3 text-body max-w-reading">
        {message.text}
      </div>
    );
  }

  const streaming = message.status === "streaming";
  const sources = message.citations ?? [];
  // Waiting text: first "Searching", then "Checking" once words have arrived.
  const progress = streaming ? (message.text ? copy.checking : copy.searching) : null;

  return (
    <div className="flex flex-col gap-3" aria-live="polite">
      {message.text && (
        <Card tone="panel">
          <AnswerText text={message.text} citations={message.citations} />
          {message.removedCount > 0 && (
            <p className="mt-3 text-small text-notfound">{copy.removedNote}</p>
          )}
        </Card>
      )}
      {progress && <p className="text-small text-muted">{progress}...</p>}
      {message.failure && (
        <FailureNotice
          kind={message.failure.kind}
          requestId={message.failure.requestId}
          onRetry={onRetry}
        />
      )}
      {sources.length > 0 && (
        <section aria-label="Sources" className="flex flex-col gap-2">
          <h2 className="text-label font-label uppercase text-muted">Sources</h2>
          {sources.map((c) => (
            <SourceCard key={c.source_id} citation={c} />
          ))}
        </section>
      )}
    </div>
  );
}
