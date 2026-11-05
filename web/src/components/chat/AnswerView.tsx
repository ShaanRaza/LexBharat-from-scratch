import { Card, CitationChip } from "@/components/ui";
import { RemovedMark } from "@/components/ui/Marks";
import { markFor, meaningFor } from "@/lib/citation";
import { CITATION_AS_RECORDED, UNVERIFIED_NOTE } from "@/lib/copy";
import type { Citation } from "@/lib/api/types";
import { citationHref, citationName, isShown, toSegments, type AnswerState } from "@/lib/chat/state";
import { CoverageFailureCard } from "./CoverageFailureCard";
import { FailureCard } from "./FailureCard";

export function AnswerView({
  answer,
  onRetry,
  onOpenSource,
  linkFor = citationHref,
}: {
  answer: AnswerState;
  onRetry?: () => void;
  onOpenSource?: (c: Citation) => void;
  // Where a citation chip links. The chat links to the in-app record; a shared page
  // (read by people who may not be signed in) links to the record's own source.
  linkFor?: (c: Citation) => string;
}) {
  if (answer.failure === "outsideCoverage" || answer.failure === "notInDataset" || answer.failure === "notFound") {
    return <CoverageFailureCard kind={answer.failure} />;
  }
  if (answer.failure) return <FailureCard kind={answer.failure} onRetry={onRetry} />;
  const ce = answer.citations;
  return (
    <Card>
      <p className="max-w-measure whitespace-pre-wrap break-words">
        {toSegments(answer.text, ce).map((seg, i) =>
          seg.type === "text" ? (
            <span key={i}>{seg.text}</span>
          ) : (
            <CitationChip
              key={i}
              label={seg.citation.source_id}
              status={seg.citation.status}
              dataAsOf={ce!.data_as_of}
              href={linkFor(seg.citation)}
              onOpen={onOpenSource && (() => onOpenSource(seg.citation))}
            />
          ),
        )}
      </p>
      {ce && ce.removed_count > 0 && (
        <p className="mt-3 flex items-center gap-2 text-small text-warn" data-removed>
          <RemovedMark />
          {UNVERIFIED_NOTE}
        </p>
      )}
      {ce && ce.citations.some(isShown) && (
        <ul className="mt-4 flex flex-col gap-3 text-small">
          {ce.citations.filter(isShown).map((c) => (
            <li key={c.source_id} className="flex min-w-0 flex-col gap-1 break-words">
              <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                <CitationChip
                  label={c.source_id}
                  status={c.status}
                  dataAsOf={ce.data_as_of}
                  href={linkFor(c)}
                  onOpen={onOpenSource && (() => onOpenSource(c))}
                />
                {/* A judgment is named by its stored citation string, shown once and exactly
                    as recorded; an Act by its section. */}
                <span className="min-w-0 break-words font-semibold">
                  {c.kind === "judgment" && c.citation_string
                    ? `${c.citation_string} (${CITATION_AS_RECORDED})`
                    : citationName(c)}
                </span>
              </span>
              <span className="text-ink-soft">{meaningFor(markFor(c.status), ce.data_as_of)}</span>
              {c.url && (
                <a href={c.url} className="w-fit break-all text-accent underline" rel="noreferrer">
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
