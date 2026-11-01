import { Suspense } from "react";
import { Loading, PageShell } from "@/components/ui";
import { StatsView } from "@/components/records/StatsView";
import { getStats } from "@/lib/api/client";
import { STATS_TITLE } from "@/lib/copy";

async function Stats() {
  const stats = await getStats().catch(() => null);
  return <StatsView stats={stats} />;
}

export default function Page() {
  return (
    <PageShell>
      <h1 className="mb-4 text-title font-extrabold">{STATS_TITLE}</h1>
      <Suspense fallback={<Loading />}>
        <Stats />
      </Suspense>
    </PageShell>
  );
}
