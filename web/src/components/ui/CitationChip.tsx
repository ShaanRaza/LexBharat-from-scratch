import { PartlyMark, TickMark, UncheckedMark } from "./Marks";
import { markFor, meaningFor, type CitationStatus } from "@/lib/citation";

// One chip per citation, never one badge for a whole answer (CLAUDE.md section 5).
// Text-led and neutral (docs/DESIGN-DIRECTION.md section 4): a small outline mark in muted
// text, then the label; the words "Record found in dataset (data as of ...)" are printed
// next to it in the citation list and carried here for screen readers and the tooltip.
// The mark is an outline, not a green check: the tick means the record exists, not that
// the case is good law. "partly" and "unchecked" differ by mark and by words, not by alarm.
export function CitationChip({
  label,
  status,
  dataAsOf,
  href,
  onOpen,
}: {
  label: string;
  status: CitationStatus;
  dataAsOf: string;
  href: string;
  // If given, a plain click opens the source beside the answer instead of navigating.
  // The href stays, so open-in-new-tab and no-JavaScript still work.
  onOpen?: () => void;
}) {
  const mark = markFor(status);
  const tone =
    mark === "tick"
      ? "border-border bg-surface text-text-muted"
      : mark === "warning"
        ? "border-warn bg-surface text-warn"
        : mark === "unchecked"
          ? "border-dashed border-text-muted bg-bg text-text-muted"
          : "border-border bg-surface text-text-muted";
  const meaning = meaningFor(mark, dataAsOf);
  return (
    <a
      href={href}
      onClick={(e) => {
        if (!onOpen || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
        e.preventDefault();
        onOpen();
      }}
      title={meaning}
      data-mark={mark}
      className={`inline-flex items-center gap-1 rounded-chip border px-2 py-0.5 align-baseline text-label font-semibold no-underline ${tone}`}
    >
      {mark === "tick" && <TickMark />}
      {mark === "warning" && <PartlyMark />}
      {mark === "unchecked" && <UncheckedMark />}
      <span>{label}</span>
      <span className="sr-only">{meaning}</span>
    </a>
  );
}
