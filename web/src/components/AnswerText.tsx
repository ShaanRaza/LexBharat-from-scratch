import { citationHref, citationState, segmentAnswer } from "@/lib/citations";
import type { Citation } from "@/lib/types";
import { CitationChip } from "./CitationChip";

/**
 * The written answer. [S1]-style markers become chips only once the checked
 * citations have arrived (`citations` not null); before that they are hidden,
 * so nothing citation-shaped shows early and then vanishes.
 */
export function AnswerText({
  text,
  citations,
}: {
  text: string;
  citations: Citation[] | null;
}) {
  const byId = citations ? new Map(citations.map((c) => [c.source_id, c])) : null;
  const known = byId ? new Set(byId.keys()) : null;
  return (
    <p className="whitespace-pre-wrap text-body">
      {segmentAnswer(text, known).map((seg, i) => {
        if (seg.type === "text") return <span key={i}>{seg.text}</span>;
        const c = byId?.get(seg.sourceId);
        if (!c) return null;
        return (
          <span key={i} className="mx-0.5">
            <CitationChip sourceId={c.source_id} state={citationState(c)} href={citationHref(c)} />
          </span>
        );
      })}
    </p>
  );
}
