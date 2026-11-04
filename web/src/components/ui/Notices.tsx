import { PRODUCT_NAME } from "@/lib/config";
import { CC_BY_CREDIT, DATA_DATE_WITH_RESULTS, NOT_LEGAL_ADVICE } from "@/lib/copy";

// Standing footer for every answer, stats page, Act page and judgment page:
// data-as-of date + CC BY credit + not-legal-advice (docs/UX-COPY.md "Standing notices").
// The date describes the content the page shows and comes from the API (core/coverage.json);
// the web app holds no date of its own, and never the release name.
export function StandingNotices({ dataAsOf }: { dataAsOf?: string }) {
  return (
    <footer className="mt-section border-t border-line pt-4 text-small text-ink-soft">
      <p>{NOT_LEGAL_ADVICE(PRODUCT_NAME)}</p>
      <p>{dataAsOf ? `Data as of ${dataAsOf}.` : DATA_DATE_WITH_RESULTS}</p>
      <p>{CC_BY_CREDIT}</p>
    </footer>
  );
}
