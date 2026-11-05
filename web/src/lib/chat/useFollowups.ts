"use client";
import { useEffect, useState } from "react";
import { getFollowups } from "@/lib/api/client";
import { keepQuestions } from "./followups";

// Next-question suggestions for a finished answer. Asked once, only after the answer is
// done and verified; any failure just means no suggestions.
export function useFollowups(conversationId: string | null, messageId: string | null, ready: boolean) {
  const [loaded, setLoaded] = useState<{ key: string; list: string[] } | null>(null);
  const key = conversationId && ready ? `${conversationId}:${messageId}` : null;
  useEffect(() => {
    if (!key || !conversationId) return;
    let live = true;
    getFollowups(conversationId, messageId).then(
      (list) => live && setLoaded({ key, list: keepQuestions(list) }),
      () => live && setLoaded({ key, list: [] }),
    );
    return () => {
      live = false;
    };
  }, [key, conversationId, messageId]);
  return loaded && loaded.key === key ? loaded.list : [];
}
