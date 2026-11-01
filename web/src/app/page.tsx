import { PageShell } from "@/components/ui";
import { ChatScreen } from "@/components/chat/ChatScreen";

export default function Home() {
  return (
    <PageShell width="content">
      <h1 className="mb-6 text-display font-bold">Ask a legal question</h1>
      <ChatScreen />
    </PageShell>
  );
}
