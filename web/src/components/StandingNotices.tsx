import { copy } from "@/lib/copy";
import { config } from "@/lib/config";
import { DataAsOfBadge } from "./DataAsOfBadge";

/** The three notices every answer, Act page and judgment page must carry. */
export function StandingNotices({ dataAsOf }: { dataAsOf?: string | null }) {
  return (
    <footer className="flex flex-col gap-2 border-t border-line pt-4 text-label text-muted">
      <div className="flex flex-wrap items-center gap-2">
        <DataAsOfBadge date={dataAsOf} snapshot={config.dataSnapshot} />
        <span>{copy.credit}</span>
      </div>
      <p>{copy.notAdvice}</p>
    </footer>
  );
}
