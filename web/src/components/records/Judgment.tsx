import { Card, StandingNotices } from "@/components/ui";
import { CITATION_AS_RECORDED } from "@/lib/copy";
import type { CaseOut } from "@/lib/api/types";

// A judgment with paragraph anchors: /cases/<id>#p12 scrolls to and highlights p12.
// The case title is a party-name string, so it is not shown (owner to decide). Judge and party names are never shown (CLAUDE.md section 6): CaseOut has no such field.
// Identify a judgment without its title (party names): stored citation string, else case
// number, else court and year. Owner may later allow c.title here.
export function judgmentHeading(c: CaseOut): string {
  if (c.citation_string) return `${c.citation_string} (${CITATION_AS_RECORDED})`;
  if (c.case_number) return c.case_number;
  const year = c.decision_date?.slice(0, 4);
  return `Supreme Court judgment${year ? `, ${year}` : ""}`;
}

export function Judgment({ c }: { c: CaseOut }) {
  return (
    <article>
      <h1 className="text-title font-extrabold">{judgmentHeading(c)}</h1>
      <dl className="mt-2 text-small text-ink-soft">
        {c.court && <div>{c.court}</div>}
        {c.decision_date && <div>Decided {c.decision_date}</div>}
        {c.case_number && <div>{c.case_number}</div>}
        {c.citation_string && (
          <div>
            {c.citation_string} ({CITATION_AS_RECORDED})
          </div>
        )}
      </dl>
      {c.url && (
        <a href={c.url} rel="noreferrer" className="mt-2 inline-block text-small text-accent underline">
          Open the original PDF
        </a>
      )}
      <Card className="mt-4 flex flex-col gap-3">
        {c.paragraphs.map((p) => (
          <p key={p.anchor} id={p.anchor} className="scroll-mt-20 rounded-chip p-2 leading-relaxed target:bg-tint">
            <span className="mr-2 text-label font-bold text-ink-soft">{p.anchor}</span>
            {p.text}
          </p>
        ))}
      </Card>
      <StandingNotices dataAsOf={c.provenance.data_as_of} />
    </article>
  );
}
