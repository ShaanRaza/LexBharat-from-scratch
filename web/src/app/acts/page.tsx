import { PageShell, StandingNotices } from "@/components/ui";
import { ActLookup } from "@/components/records/ActLookup";
import { sampleSections } from "@/lib/api/client";

export default function Acts() {
  return (
    <PageShell>
      <h1 className="mb-4 text-title font-extrabold">Look up an Act section</h1>
      <ActLookup samples={sampleSections()} />
      <StandingNotices />
    </PageShell>
  );
}
