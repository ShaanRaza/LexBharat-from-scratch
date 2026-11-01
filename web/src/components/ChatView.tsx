import { copy } from "@/lib/copy";
import type { ChatMessage } from "@/hooks/chatState";
import { Label } from "./Label";
import { MessageView } from "./MessageView";
import { SearchBar } from "./SearchBar";
import { StandingNotices } from "./StandingNotices";

interface Props {
  messages: ChatMessage[];
  draft: string;
  onDraftChange: (v: string) => void;
  onSubmit: () => void;
  onExample: (q: string) => void;
  onRetry: () => void;
  busy: boolean;
  loading?: boolean;
  showSampleLabel?: boolean;
}

/** The chat screen layout. Receives data and callbacks; has no chat logic. */
export function ChatView(p: Props) {
  const latestAsOf =
    [...p.messages].reverse().find((m) => m.dataAsOf)?.dataAsOf ?? null;
  const empty = p.messages.length === 0;
  return (
    <div className="mx-auto flex w-full max-w-reading flex-1 flex-col gap-4 px-gutter py-6">
      {p.showSampleLabel && (
        <div>
          <Label tone="accent">{copy.sample} data - no backend connected</Label>
        </div>
      )}
      <div className="flex flex-1 flex-col gap-4">
        {empty && !p.loading && (
          <div className="flex flex-col gap-3 py-8">
            <h1 className="text-display font-heading">Ask a legal question</h1>
            <p className="text-lead text-muted">
              Get a short, plain answer where every source is checked against the dataset.
            </p>
            <ul className="flex flex-wrap gap-2">
              {copy.examples.map((q) => (
                <li key={q}>
                  <button
                    type="button"
                    className="rounded-pill border border-line bg-panel px-3 py-1.5 text-left text-small hover:bg-tint"
                    onClick={() => p.onExample(q)}
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {p.loading && <p className="text-small text-muted">Loading...</p>}
        {p.messages.map((m, i) => (
          <MessageView
            key={m.id}
            message={m}
            onRetry={i === p.messages.length - 1 ? p.onRetry : undefined}
          />
        ))}
      </div>
      <div className="sticky bottom-0 flex flex-col gap-3 bg-page pb-4 pt-2">
        <SearchBar
          value={p.draft}
          onChange={p.onDraftChange}
          onSubmit={p.onSubmit}
          disabled={p.busy}
          label={copy.askLabel}
          placeholder={copy.askPlaceholder}
        />
        <StandingNotices dataAsOf={latestAsOf} />
      </div>
    </div>
  );
}
