import { Suspense } from "react";
import { Loading, PageShell } from "@/components/ui";
import { StatsView } from "@/components/records/StatsView";
import { getStats } from "@/lib/api/client";
import { STATS_TITLE } from "@/lib/copy";

async function Stats({ searchParams }: { searchParams: Promise<{ fake?: string }> }) {
  const { fake } = await searchParams; // fake mode only: ?fake=empty shows the empty state
  const stats = await getStats(fake).catch(() => null);
  return <StatsView stats={stats} />;
}

export default function Page({ searchParams }: { searchParams: Promise<{ fake?: string }> }) {
  return (
    <PageShell shell="public">
      <h1 className="mb-4 text-title font-bold">{STATS_TITLE}</h1>
      <Suspense fallback={<Loading />}>
        <Stats searchParams={searchParams} />
      </Suspense>
    </PageShell>
  );
}
