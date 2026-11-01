import { markFor, type CitationStatus } from "@/lib/citation";
import { PARTLY_LABEL, VERIFICATION_LABEL } from "@/lib/copy";

// One chip per citation. Tick only for "verified"; warning for "partly"; no mark otherwise.
// Never one badge for a whole answer (CLAUDE.md section 5).
export function CitationChip({
  label,
  status,
  dataAsOf,
  href,
}: {
  label: string;
  status: CitationStatus;
  dataAsOf: string;
  href: string;
}) {
  const mark = markFor(status);
  const tone =
    mark === "tick"
      ? "bg-verified-bg text-verified"
      : mark === "warning"
        ? "bg-partly-bg text-partly"
        : "bg-panel text-ink-soft";
  const meaning =
    mark === "tick"
      ? `${VERIFICATION_LABEL} (data as of ${dataAsOf})`
      : mark === "warning"
        ? `${PARTLY_LABEL} (data as of ${dataAsOf})`
        : "Not verified";
  return (
    <a
      href={href}
      title={meaning}
      data-mark={mark}
      className={`inline-flex items-center gap-1 rounded-chip px-2 py-1 text-label font-semibold ${tone}`}
    >
      {mark === "tick" && <span aria-hidden>✓</span>}
      {mark === "warning" && <span aria-hidden>⚠</span>}
      <span>{label}</span>
      <span className="sr-only">{meaning}</span>
    </a>
  );
}
