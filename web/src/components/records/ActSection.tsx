import { Card, Label, StandingNotices } from "@/components/ui";
import { IN_FORCE_LABEL, IN_FORCE_NOT_CHECKED, REPEALED_LABEL } from "@/lib/copy";
import { headingSize } from "@/lib/heading";
import type { SectionOut } from "@/lib/api/types";

// The API decides (core/act_status.py, decision A180): "Repealed" where act_status, the
// IND_REP_ id or a clean repeal marker in the title says so; "In force" only where act_status
// says so; otherwise the standing "not checked" label. This component only shows the answer.
export function ActSection({ s }: { s: SectionOut }) {
  return (
    <article>
      <p className="break-words text-small text-ink-soft">{s.act_name}</p>
      <h1 className={`${headingSize(`Section ${s.section}${s.section_title ? `: ${s.section_title}` : ""}`)} mt-1 break-words font-bold`}>
        Section {s.section}
        {s.section_title ? `: ${s.section_title}` : ""}
      </h1>
      <div className="mt-2 flex gap-2">
        {s.force_status === "in_force" && <Label>{IN_FORCE_LABEL}</Label>}
        {s.force_status === "repealed" && <Label>{REPEALED_LABEL}</Label>}
        {s.force_status === "not_checked" && <Label plain>{IN_FORCE_NOT_CHECKED}</Label>}
      </div>
      <Card className="mt-4">
        <p className="whitespace-pre-wrap break-words">{s.text}</p>
        {s.source_url && (
          <a href={s.source_url} rel="noreferrer" className="mt-3 inline-block break-all text-small text-accent underline">
            Source
          </a>
        )}
      </Card>
      <StandingNotices dataAsOf={s.provenance.data_as_of} />
    </article>
  );
}
