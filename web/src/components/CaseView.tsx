import { copy } from "@/lib/copy";
import type { CaseRecord } from "@/lib/types";
import { Button } from "./Button";
import { Label } from "./Label";
import { StandingNotices } from "./StandingNotices";

/**
 * A judgment with a paragraph anchor on each paragraph: /cases/<id>#p5 jumps
 * to paragraph 5. Judges and party names are never shown (CLAUDE.md section 6).
 */
export function CaseView({
  record,
  highlight,
  isSample,
}: {
  record: CaseRecord;
  /** Element id to highlight, e.g. "p5". */
  highlight?: string | null;
  isSample?: boolean;
}) {
  return (
    <article className="mx-auto flex w-full max-w-reading flex-col gap-4 px-gutter py-8">
      <div className="flex flex-wrap items-center gap-2">
        {isSample && <Label tone="accent">{copy.sample}</Label>}
        <Label>{record.court}</Label>
        {record.decision_date && <Label>Decided {record.decision_date}</Label>}
      </div>
      <header>
        <h1 className="text-title font-heading">{record.title}</h1>
        {record.case_number && <p className="text-small text-muted">{record.case_number}</p>}
        {record.citation_string && (
          <p className="text-small text-muted">
            {record.citation_string} ({copy.citationAsRecorded})
          </p>
        )}
      </header>
      {record.pdf_url && (
        <div>
          <Button href={record.pdf_url} external variant="secondary">
            Open the original PDF
          </Button>
        </div>
      )}
      <ol className="flex flex-col gap-3">
        {record.paragraphs.map((p) => (
          <li
            key={p.n}
            id={`p${p.n}`}
            className={`flex gap-3 rounded-control p-2 ${highlight === `p${p.n}` ? "bg-tint" : ""}`}
          >
            <a href={`#p${p.n}`} className="w-8 shrink-0 text-small font-label text-accent" aria-label={`Link to paragraph ${p.n}`}>
              {p.n}
            </a>
            <p className="text-body">{p.text}</p>
          </li>
        ))}
      </ol>
      <StandingNotices dataAsOf={record.data_as_of} />
    </article>
  );
}
