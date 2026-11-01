import { Card, Label, StandingNotices } from "@/components/ui";
import { IN_FORCE_NOT_CHECKED } from "@/lib/copy";
import type { SectionOut } from "@/lib/api/types";

// In-force status is shown ONLY when the API says act_status was checked (filled in
// the dataset for 1,568 of 22,264 acts). Otherwise the standing label is shown.
export function ActSection({ s }: { s: SectionOut }) {
  return (
    <article>
      <p className="text-small text-ink-soft">{s.act_name}</p>
      <h1 className="text-title font-extrabold">
        Section {s.section}
        {s.section_title ? `: ${s.section_title}` : ""}
      </h1>
      <div className="mt-2 flex gap-2">
        {s.act_status_checked ? (
          <Label>{s.in_force ? "In force" : "Not in force"}</Label>
        ) : (
          <Label>{IN_FORCE_NOT_CHECKED}</Label>
        )}
      </div>
      <Card className="mt-4">
        <p className="whitespace-pre-wrap leading-relaxed">{s.text}</p>
        {s.source_url && (
          <a href={s.source_url} rel="noreferrer" className="mt-3 inline-block text-small text-accent underline">
            Source
          </a>
        )}
      </Card>
      <StandingNotices dataAsOf={s.provenance.data_as_of} />
    </article>
  );
}
