import { copy } from "@/lib/copy";
import type { ActSection } from "@/lib/types";
import { Button } from "./Button";
import { Card } from "./Card";
import { Label } from "./Label";
import { StandingNotices } from "./StandingNotices";

/** One Act section. In-force status shows ONLY when the dataset has it. */
export function ActSectionView({ section, isSample }: { section: ActSection; isSample?: boolean }) {
  return (
    <article className="mx-auto flex w-full max-w-reading flex-col gap-4 px-gutter py-8">
      <div className="flex flex-wrap items-center gap-2">
        {isSample && <Label tone="accent">{copy.sample}</Label>}
        {section.act_status != null ? (
          <Label tone="verified">{section.act_status}</Label>
        ) : (
          <Label>{copy.inForceUnchecked}</Label>
        )}
      </div>
      <header>
        <p className="text-small text-muted">
          {section.act_name}
          {section.act_year ? `, ${section.act_year}` : ""}
        </p>
        <h1 className="text-title font-heading">
          Section {section.section_number}
          {section.section_title ? `: ${section.section_title}` : ""}
        </h1>
      </header>
      <Card tone="panel">
        <p className="whitespace-pre-wrap text-body">{section.text}</p>
      </Card>
      {section.source_url && (
        <div>
          <Button href={section.source_url} external variant="secondary">
            Official source
          </Button>
        </div>
      )}
      <StandingNotices dataAsOf={section.data_as_of} />
    </article>
  );
}
