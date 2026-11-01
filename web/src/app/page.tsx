import { PageShell } from "@/components/ui";
import { ChatScreen } from "@/components/chat/ChatScreen";

export default function Home() {
  return (
    <PageShell>
      <h1 className="mb-6 text-display font-extrabold">Ask a legal question</h1>
      <ChatScreen />
    </PageShell>
  );
}
