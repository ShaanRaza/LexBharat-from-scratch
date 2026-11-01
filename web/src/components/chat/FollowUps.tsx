import { Button } from "@/components/ui";
import { FOLLOWUPS_TITLE } from "@/lib/copy";

// Suggested next questions. Each is just a question: clicking one asks it like any other.
export function FollowUps({ suggestions, onAsk, disabled }: { suggestions: string[]; onAsk: (q: string) => void; disabled?: boolean }) {
  if (suggestions.length === 0) return null;
  return (
    <section aria-label={FOLLOWUPS_TITLE} className="flex flex-col gap-2">
      <h3 className="font-sans text-label font-bold uppercase tracking-wide text-ink-soft">{FOLLOWUPS_TITLE}</h3>
      <ul className="flex flex-col items-start gap-2">
        {suggestions.map((q) => (
          <li key={q}>
            <Button variant="secondary" disabled={disabled} onClick={() => onAsk(q)} className="text-left">
              {q}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
