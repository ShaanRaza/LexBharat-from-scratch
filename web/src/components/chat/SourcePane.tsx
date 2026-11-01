"use client";
import { useEffect, useRef } from "react";
import { ActSection } from "@/components/records/ActSection";
import { Judgment } from "@/components/records/Judgment";
import { Button, Card, CitationChip, Loading } from "@/components/ui";
import { FAILURES } from "@/lib/copy";
import { markFor, meaningFor } from "@/lib/citation";
import { citationHref } from "@/lib/chat/state";
import type { SourceState } from "@/lib/chat/useSource";
import type { Citation } from "@/lib/api/types";

// The record beside the answer. It reuses the judgment and Act readers, so it can show
// nothing the reader pages do not: no judge or party names, the citation string "as
// recorded", the data-as-of date, the CC BY credit and the not-legal-advice notice.
// Presentational: it is given the citation and the loaded record.
export function SourcePane({
  citation,
  state,
  dataAsOf,
  clicks,
  onClose,
}: {
  citation: Citation;
  state: SourceState;
  dataAsOf: string;
  clicks: number;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  // Jump to the cited paragraph once the record is on screen; on a narrow screen the
  // pane sits below the answer, so bring the pane itself into view first.
  useEffect(() => {
    const el = ref.current;
    if (!el || state.status === "loading") return;
    el.scrollIntoView?.({ block: "nearest" });
    el.querySelector('[data-cited="true"]')?.scrollIntoView?.({ block: "center" });
  }, [state.status, citation.anchor, clicks]);

  return (
    <aside aria-label="Source" ref={ref} className="flex flex-col gap-3 lg:sticky lg:top-20 lg:self-start">
      <Card className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-wrap items-center gap-2 text-small">
          <CitationChip label={citation.source_id} status={citation.status} dataAsOf={dataAsOf} href={citationHref(citation)} />
          <span className="text-ink-soft">{meaningFor(markFor(citation.status), dataAsOf)}</span>
        </span>
        <Button variant="secondary" onClick={onClose}>
          Close source
        </Button>
      </Card>
      {state.status === "loading" && <Loading what="Loading the source" />}
      {state.status === "error" && (
        <Card role="alert">
          <p className="font-bold text-notfound">{FAILURES.serviceError.title}</p>
          <p className="mt-1 text-ink-soft">{FAILURES.serviceError.hint}</p>
        </Card>
      )}
      {state.status === "case" && <Judgment c={state.record} highlight={citation.anchor ?? undefined} />}
      {state.status === "section" && <ActSection s={state.record} />}
    </aside>
  );
}
