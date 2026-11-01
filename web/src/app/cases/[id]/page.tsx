import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loading, PageShell } from "@/components/ui";
import { Judgment } from "@/components/records/Judgment";
import { getCase } from "@/lib/api/client";

async function Case({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const c = await getCase(decodeURIComponent(id)).catch(() => null);
  if (!c) notFound();
  return <Judgment c={c} />;
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  return (
    <PageShell>
      <Suspense fallback={<Loading />}>
        <Case params={params} />
      </Suspense>
    </PageShell>
  );
}
