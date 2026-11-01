import { Suspense } from "react";
import { notFound } from "next/navigation";
import { TopBar } from "@/components/ui";
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
    <>
      <TopBar />
      <main className="mx-auto w-full max-w-reading flex-1 px-gutter py-section">
        <Suspense fallback={<p>Loading</p>}>
          <Case params={params} />
        </Suspense>
      </main>
    </>
  );
}
