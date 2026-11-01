import { Suspense } from "react";
import { ChatScreen } from "@/components/ChatScreen";

// Next.js 16: params is a Promise, and reading it must sit inside <Suspense>.
async function Conversation({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ChatScreen key={id} conversationId={id} />;
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<p className="p-6 text-small text-muted">Loading...</p>}>
      <Conversation params={params} />
    </Suspense>
  );
}
