import { Suspense } from "react";
import { Loading, PageShell } from "@/components/ui";
import { ConversationScreen } from "@/components/matters/ConversationScreen";

async function Conversation({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ConversationScreen id={decodeURIComponent(id)} />;
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  return (
    <PageShell shell="app">
      <Suspense fallback={<Loading />}>
        <Conversation params={params} />
      </Suspense>
    </PageShell>
  );
}
