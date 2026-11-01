import { Card, Label, StandingNotices } from "@/components/ui";
import { COVERAGE_COVERED, COVERAGE_EXCLUDED, COVERAGE_PLACEHOLDER, FAILURES } from "@/lib/copy";
import type { CoverageOut } from "@/lib/api/types";

// What the dataset holds, exactly as the API says (one source: core/coverage.json). It
// invents no category. While the dataset has not been measured it says so.
export function CoverageView({ coverage }: { coverage: CoverageOut | null }) {
  if (!coverage) {
    return (
      <Card role="alert">
        <p className="font-bold text-notfound">{FAILURES.serviceError.title}</p>
        <p className="mt-1 text-ink-soft">{FAILURES.serviceError.hint}</p>
      </Card>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {coverage.status === "placeholder" && <Label>{COVERAGE_PLACEHOLDER}</Label>}
      <p className="leading-relaxed">{coverage.sentence}</p>
      <section aria-label={COVERAGE_COVERED}>
        <h2 className="font-sans text-label font-bold uppercase tracking-wide text-ink-soft">{COVERAGE_COVERED}</h2>
        <ul className="mt-1 list-disc pl-5">
          {[...coverage.courts, ...coverage.instruments].map((i) => (
            <li key={i.id}>{i.label}</li>
          ))}
        </ul>
      </section>
      <section aria-label={COVERAGE_EXCLUDED}>
        <h2 className="font-sans text-label font-bold uppercase tracking-wide text-ink-soft">{COVERAGE_EXCLUDED}</h2>
        <ul className="mt-1 list-disc pl-5">
          {coverage.excluded.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </section>
      <StandingNotices dataAsOf={coverage.provenance.data_as_of} />
    </div>
  );
}
