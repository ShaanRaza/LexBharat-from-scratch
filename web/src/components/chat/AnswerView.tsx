import { Card, CitationChip } from "@/components/ui";
import { CITATION_AS_RECORDED, UNVERIFIED_NOTE } from "@/lib/copy";
import { citationHref, isShown, toSegments, type AnswerState } from "@/lib/chat/state";
import { FailureCard } from "./FailureCard";

export function AnswerView({ answer, onRetry }: { answer: AnswerState; onRetry?: () => void }) {
  if (answer.failure) return <FailureCard kind={answer.failure} onRetry={onRetry} />;
  const ce = answer.citations;
  return (
    <Card>
      <p className="whitespace-pre-wrap leading-relaxed">
        {toSegments(answer.text, ce).map((seg, i) =>
          seg.type === "text" ? (
            <span key={i}>{seg.text}</span>
          ) : (
            <CitationChip
              key={i}
              label={seg.citation.source_id}
              status={seg.citation.status}
              dataAsOf={ce!.data_as_of}
              href={citationHref(seg.citation)}
            />
          ),
        )}
      </p>
      {ce && ce.removed_count > 0 && <p className="mt-3 text-small text-partly">{UNVERIFIED_NOTE}</p>}
      {ce && ce.citations.some(isShown) && (
        <ul className="mt-4 flex flex-col gap-2 text-small">
          {ce.citations.filter(isShown).map((c) => (
            <li key={c.source_id} className="flex flex-wrap items-center gap-2">
              <CitationChip label={c.source_id} status={c.status} dataAsOf={ce.data_as_of} href={citationHref(c)} />
              <span>{c.title ?? c.record_id}</span>
              {c.citation_string && (
                <span className="text-ink-soft">
                  {c.citation_string} ({CITATION_AS_RECORDED})
                </span>
              )}
              {c.url && (
                <a href={c.url} className="text-accent underline" rel="noreferrer">
                  Source
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
      {ce && (
        <>
          <p className="mt-3 text-small text-ink-soft">{ce.notice}</p>
          <p className="text-small text-ink-soft">Data as of {ce.data_as_of}. {ce.credit}</p>
        </>
      )}
    </Card>
  );
}
