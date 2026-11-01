import { Suspense } from "react";
import { Loading, PageShell } from "@/components/ui";
import { CoverageView } from "@/components/records/CoverageView";
import { getCoverage } from "@/lib/api/client";
import { COVERAGE_TITLE } from "@/lib/copy";

async function Coverage() {
  const coverage = await getCoverage().catch(() => null);
  return <CoverageView coverage={coverage} />;
}

export default function Page() {
  return (
    <PageShell>
      <h1 className="mb-4 text-title font-extrabold">{COVERAGE_TITLE}</h1>
      <Suspense fallback={<Loading />}>
        <Coverage />
      </Suspense>
    </PageShell>
  );
}
