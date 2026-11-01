import { DATA_AS_OF, PRODUCT_NAME } from "@/lib/config";
import { CC_BY_CREDIT, NOT_LEGAL_ADVICE } from "@/lib/copy";

// Standing footer for every answer, stats page, Act page and judgment page:
// data-as-of date + CC BY credit + not-legal-advice (docs/UX-COPY.md "Standing notices").
export function StandingNotices({ dataAsOf = DATA_AS_OF }: { dataAsOf?: string }) {
  return (
    <footer className="mt-section border-t border-line pt-4 text-small text-ink-soft">
      <p>{NOT_LEGAL_ADVICE(PRODUCT_NAME)}</p>
      <p>Data as of {dataAsOf}.</p>
      <p>{CC_BY_CREDIT}</p>
    </footer>
  );
}
