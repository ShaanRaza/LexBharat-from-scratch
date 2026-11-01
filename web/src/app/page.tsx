import { TopBar } from "@/components/ui";
import { ChatScreen } from "@/components/chat/ChatScreen";

export default function Home() {
  return (
    <>
      <TopBar />
      <main className="mx-auto w-full max-w-reading flex-1 px-gutter py-section">
        <h1 className="mb-6 text-display font-extrabold">Ask a legal question</h1>
        <ChatScreen />
      </main>
    </>
  );
}
