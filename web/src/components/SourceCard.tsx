import { citationHref, citationState } from "@/lib/citations";
import { copy } from "@/lib/copy";
import type { Citation } from "@/lib/types";
import { Button } from "./Button";
import { Card } from "./Card";
import { CitationChip } from "./CitationChip";
import { Label, type LabelTone } from "./Label";

const TONE: Record<ReturnType<typeof citationState>, LabelTone> = {
  verified: "verified",
  partial: "notfound",
  unverified: "notfound",
};
const TEXT = {
  verified: copy.verified,
  partial: copy.partly,
  unverified: copy.notVerified,
} as const;

/** One source under an answer: chip, title, state, recorded citation, links. */
export function SourceCard({ citation }: { citation: Citation }) {
  const state = citationState(citation);
  const inSite = citationHref(citation);
  return (
    <Card tone="plain" as="article">
      <div className="flex flex-wrap items-center gap-2">
        <CitationChip sourceId={citation.source_id} state={state} />
        <Label tone={TONE[state]}>{TEXT[state]}</Label>
        {citation.kind === "act" && citation.act_status == null && (
          <Label>{copy.inForceUnchecked}</Label>
        )}
        {citation.kind === "act" && citation.act_status != null && (
          <Label>{citation.act_status}</Label>
        )}
      </div>
      <h3 className="mt-2 text-body font-heading">{citation.title}</h3>
      {citation.citation_string && (
        <p className="text-small text-muted">
          {/* Shown exactly as stored - never retyped (CLAUDE.md section 5). */}
          <span>{citation.citation_string}</span> ({copy.citationAsRecorded})
        </p>
      )}
      {citation.excerpt && (
        <blockquote className="mt-2 border-l-2 border-line pl-3 text-small text-muted">
          {citation.excerpt}
        </blockquote>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {inSite && (
          <Button href={inSite} variant="secondary">
            {citation.kind === "judgment" ? "Open judgment" : "Open section"}
          </Button>
        )}
        {citation.link && (
          <Button href={citation.link} external variant="ghost">
            Official source
          </Button>
        )}
      </div>
    </Card>
  );
}
