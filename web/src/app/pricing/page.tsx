import { PageShell } from "@/components/ui";
import { PricingScreen } from "@/components/launch/PricingScreen";
import { PRICING_TITLE } from "@/lib/copy";

export default function Page() {
  return (
    <PageShell>
      <h1 className="mb-4 text-title font-bold">{PRICING_TITLE}</h1>
      <PricingScreen />
    </PageShell>
  );
}
