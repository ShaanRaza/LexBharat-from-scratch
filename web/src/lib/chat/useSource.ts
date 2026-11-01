"use client";
import { useCallback, useEffect, useState } from "react";
import { getCase, getSection } from "@/lib/api/client";
import type { CaseOut, Citation, SectionOut } from "@/lib/api/types";

export type SourceState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "case"; record: CaseOut }
  | { status: "section"; record: SectionOut };

// Which citation is open beside the answer, and its record. No styling here.
// It loads through the same client calls the judgment and Act pages use, so there is
// one reader and one source of truth for a record.
export function useSource() {
  const [open, setOpen] = useState<{ citation: Citation; n: number } | null>(null);
  // The loaded record, tagged with the key it was loaded for. A result for a record
  // that is no longer open is ignored, so "loading" is derived rather than set.
  const [loaded, setLoaded] = useState<{ key: string; state: SourceState } | null>(null);

  // n changes on every click, so re-clicking the same citation jumps to it again.
  const openCitation = useCallback((citation: Citation) => setOpen((o) => ({ citation, n: (o?.n ?? 0) + 1 })), []);
  const close = useCallback(() => setOpen(null), []);

  const citation = open?.citation ?? null;
  const key = citation ? `${citation.kind}:${citation.record_id}:${citation.act_slug}:${citation.section}` : null;
  useEffect(() => {
    if (!citation) return;
    let live = true;
    const load =
      citation.kind === "act" && citation.act_slug && citation.section
        ? getSection(citation.act_slug, citation.section).then((record) => ({ status: "section", record }) as const)
        : getCase(citation.record_id).then((record) => ({ status: "case", record }) as const);
    load.then(
      (state) => live && setLoaded({ key: key!, state }),
      () => live && setLoaded({ key: key!, state: { status: "error" } }),
    );
    return () => {
      live = false;
    };
    // The record is re-fetched only when a different record is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const state: SourceState = loaded && loaded.key === key ? loaded.state : { status: "loading" };
  return { open: open?.citation ?? null, clicks: open?.n ?? 0, state, openCitation, close };
}
