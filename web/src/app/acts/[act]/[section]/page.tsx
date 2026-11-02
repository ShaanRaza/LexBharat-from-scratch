import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loading, PageShell } from "@/components/ui";
import { ActSection } from "@/components/records/ActSection";
import { getSection } from "@/lib/api/client";

async function Section({ params }: { params: Promise<{ act: string; section: string }> }) {
  const { act, section } = await params;
  const s = await getSection(decodeURIComponent(act), decodeURIComponent(section)).catch(() => null);
  if (!s) notFound();
  return <ActSection s={s} />;
}

export default function Page({ params }: { params: Promise<{ act: string; section: string }> }) {
  return (
    <PageShell shell="auto">
      <Suspense fallback={<Loading />}>
        <Section params={params} />
      </Suspense>
    </PageShell>
  );
}
