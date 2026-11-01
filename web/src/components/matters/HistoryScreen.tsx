"use client";
import Link from "next/link";
import { useState } from "react";
import { Card, SearchBar } from "@/components/ui";
import { listConversations, searchHistory } from "@/lib/api/client";
import { HISTORY_NONE, HISTORY_RECENT, HISTORY_SEARCH, HISTORY_SEARCH_PLACEHOLDER } from "@/lib/copy";
import { useLoaded } from "@/lib/matters/useLoaded";

// Recent conversations, and search across the user's OWN saved questions and answers.
export function HistoryScreen() {
  const [q, setQ] = useState<string | null>(null);
  const recent = useLoaded(() => listConversations(), "recent");
  const found = useLoaded(() => (q ? searchHistory(q) : Promise.resolve([])), `search:${q}`);
  return (
    <div className="flex flex-col gap-4">
      <SearchBar placeholder={HISTORY_SEARCH_PLACEHOLDER} submitLabel={HISTORY_SEARCH} onSubmit={(t) => setQ(t)} />
      {q === null ? (
        <section aria-label={HISTORY_RECENT} className="flex flex-col gap-2">
          <h2 className="text-label font-bold uppercase tracking-wide text-ink-soft">{HISTORY_RECENT}</h2>
          {recent.status === "ready" && recent.value!.length === 0 && <p className="text-ink-soft">{HISTORY_NONE}</p>}
          <ul className="flex flex-col gap-2">
            {recent.value?.map((c) => (
              <li key={c.id}>
                <Link href={`/conversations/${c.id}`}>
                  <Card>{c.title ?? "Untitled conversation"}</Card>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section aria-label="Results" className="flex flex-col gap-2">
          {found.status === "ready" && found.value!.length === 0 && <p className="text-ink-soft">{HISTORY_NONE}</p>}
          <ul className="flex flex-col gap-2">
            {found.value?.map((h) => (
              <li key={`${h.conversation_id}-${h.message_id ?? "title"}`}>
                <Link href={`/conversations/${h.conversation_id}`}>
                  <Card>
                    <span className="font-semibold">{h.title ?? "Untitled conversation"}</span>
                    <span className="mt-1 block text-small text-ink-soft">{h.snippet}</span>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
