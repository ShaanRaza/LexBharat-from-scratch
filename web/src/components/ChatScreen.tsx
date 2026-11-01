"use client";
import { useEffect, useRef, useState } from "react";
import { useChat } from "@/hooks/useChat";
import { config } from "@/lib/config";
import { useConversationsRefresh } from "./ChatShell";
import { ChatView } from "./ChatView";

/** Glue: connects the chat logic (useChat) to the chat layout (ChatView). */
export function ChatScreen({ conversationId }: { conversationId?: string }) {
  const refresh = useConversationsRefresh();
  const chat = useChat({ conversationId, onConversationCreated: refresh });
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  // Keep the newest words in view while the answer streams.
  const last = chat.messages[chat.messages.length - 1];
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [last?.text, last?.status, chat.messages.length]);

  const submit = (q: string) => {
    setDraft("");
    void chat.send(q);
  };

  return (
    <>
      <ChatView
        messages={chat.messages}
        draft={draft}
        onDraftChange={setDraft}
        onSubmit={() => submit(draft)}
        onExample={submit}
        onRetry={() => void chat.retry()}
        busy={chat.busy}
        loading={chat.loading}
        showSampleLabel={config.useFakeApi}
      />
      <div ref={bottom} />
    </>
  );
}
