import { notFound } from "next/navigation";
import { Suspense } from "react";
import { ActSectionView } from "@/components/ActSectionView";
import { getApi } from "@/lib/api";
import { ApiError } from "@/lib/api-error";
import { config } from "@/lib/config";

// Public page: no login. Rendered on the server, so Google can read it.
async function loadSection(act: string, section: string) {
  try {
    return await getApi().getSection(decodeURIComponent(act), decodeURIComponent(section));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

async function Section({ params }: { params: Promise<{ act: string; section: string }> }) {
  const { act, section } = await params;
  const data = await loadSection(act, section);
  if (!data) notFound();
  return <ActSectionView section={data} isSample={config.useFakeApi} />;
}

export default function Page({ params }: { params: Promise<{ act: string; section: string }> }) {
  return (
    <Suspense fallback={<p className="p-6 text-small text-muted">Loading...</p>}>
      <Section params={params} />
    </Suspense>
  );
}
