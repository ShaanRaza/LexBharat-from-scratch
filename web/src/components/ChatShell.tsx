"use client";
import { usePathname } from "next/navigation";
import { createContext, Suspense, useContext, type ReactNode } from "react";
import { useConversations } from "@/hooks/useConversations";
import { Sidebar } from "./Sidebar";

const RefreshContext = createContext<() => void>(() => undefined);

/** Lets the chat tell the sidebar "a new conversation exists, reload". */
export const useConversationsRefresh = () => useContext(RefreshContext);

/** The sidebar, with the open conversation highlighted. */
function ConversationSidebar({ items, loading, highlight }: SidebarData & { highlight: boolean }) {
  // /c/<id> -> highlight that conversation. usePathname needs <Suspense> (below).
  const pathname = usePathname();
  const match = highlight ? /^\/c\/([^/]+)/.exec(pathname ?? "") : null;
  const activeId = match ? decodeURIComponent(match[1]) : null;
  return <Sidebar items={items} activeId={activeId} loading={loading} />;
}

interface SidebarData {
  items: { id: string; title: string }[];
  loading: boolean;
}

/** Sidebar + the chat page, for every page in the (chat) route group. */
export function ChatShell({ children }: { children: ReactNode }) {
  const { items, loading, refresh } = useConversations();
  const data = { items: items.map((c) => ({ id: c.id, title: c.title })), loading };
  return (
    <RefreshContext.Provider value={refresh}>
      <div className="flex flex-1">
        <Suspense fallback={<Sidebar {...data} />}>
          <ConversationSidebar {...data} highlight />
        </Suspense>
        <div className="flex min-w-0 flex-1 flex-col">{children}</div>
      </div>
    </RefreshContext.Provider>
  );
}
