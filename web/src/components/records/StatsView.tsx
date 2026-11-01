import { Card, Label, StandingNotices } from "@/components/ui";
import { FAILURES, SAMPLE_LABEL, STATS_DESCRIPTIVE_NOTE } from "@/lib/copy";
import type { StatsOut } from "@/lib/api/types";

// Counts only (CLAUDE.md section 6): no percentages, no "chances", no prediction.
// `live` false means sample data, and the page says so.
export function StatsView({ stats }: { stats: StatsOut | null }) {
  if (!stats) {
    return (
      <Card role="alert">
        <p className="font-bold text-notfound">{FAILURES.serviceError.title}</p>
        <p className="mt-1 text-ink-soft">{FAILURES.serviceError.hint}</p>
      </Card>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {!stats.live && <Label>{SAMPLE_LABEL}</Label>}
      <p className="text-ink-soft">{STATS_DESCRIPTIVE_NOTE}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-small">
          <thead>
            <tr className="border-b border-line text-ink-soft">
              <th className="py-2 pr-4 font-semibold">Court</th>
              <th className="py-2 pr-4 font-semibold">Year</th>
              <th className="py-2 pr-4 font-semibold">Outcome</th>
              <th className="py-2 text-right font-semibold">Count</th>
            </tr>
          </thead>
          <tbody>
            {stats.rows.map((r) => (
              <tr key={`${r.court}/${r.year}/${r.outcome_label}`} className="border-b border-line">
                <td className="py-2 pr-4">{r.court}</td>
                <td className="py-2 pr-4">{r.year}</td>
                <td className="py-2 pr-4">{r.outcome_label}</td>
                <td className="py-2 text-right">{r.count.toLocaleString("en-IN")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <StandingNotices dataAsOf={stats.provenance.data_as_of} />
    </div>
  );
}
