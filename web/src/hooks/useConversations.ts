"use client";
import { useCallback, useEffect, useState } from "react";
import { getApi } from "@/lib/api";
import type { ConversationSummary } from "@/lib/types";

/** The sidebar list. `refresh()` reloads it (e.g. after a chat is created). */
export function useConversations() {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let cancelled = false;
    getApi()
      .listConversations()
      .then((p) => !cancelled && setItems(p.items))
      .catch(() => undefined) // the list is a convenience; the chat still works
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [tick]);
  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { items, loading, refresh };
}
