import { Suspense } from "react";
import { notFound } from "next/navigation";
import { TopBar } from "@/components/ui";
import { ActSection } from "@/components/records/ActSection";
import { getSection } from "@/lib/api/client";

async function Section({ params }: { params: Promise<{ act: string; section: string }> }) {
  const { act, section } = await params;
  const s = await getSection(act, section).catch(() => null);
  if (!s) notFound();
  return <ActSection s={s} />;
}

export default function Page({ params }: { params: Promise<{ act: string; section: string }> }) {
  return (
    <>
      <TopBar />
      <main className="mx-auto w-full max-w-reading flex-1 px-gutter py-section">
        <Suspense fallback={<p>Loading</p>}>
          <Section params={params} />
        </Suspense>
      </main>
    </>
  );
}
