import { Suspense } from "react";
import { Loading, PageShell } from "@/components/ui";
import { MatterScreen } from "@/components/matters/MatterScreen";

async function Matter({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MatterScreen id={decodeURIComponent(id)} />;
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  return (
    <PageShell>
      <Suspense fallback={<Loading />}>
        <Matter params={params} />
      </Suspense>
    </PageShell>
  );
}
