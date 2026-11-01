import { Suspense } from "react";
import { CaseScreen } from "@/components/CaseScreen";

async function Case({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CaseScreen id={decodeURIComponent(id)} />;
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<p className="p-6 text-small text-muted">Loading...</p>}>
      <Case params={params} />
    </Suspense>
  );
}
