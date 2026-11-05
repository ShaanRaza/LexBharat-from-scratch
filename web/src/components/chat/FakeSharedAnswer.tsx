"use client";
import { SharedAnswerView } from "@/components/chat/SharedAnswerView";
import { Loading } from "@/components/ui";
import { getShared } from "@/lib/api/client";
import { useLoaded } from "@/lib/matters/useLoaded";

// FAKE MODE ONLY. In fake mode the shares live in this browser's localStorage, which a
// server component cannot read, so the public page reads them here instead. With a real
// API the page uses the server fetch (cache: "no-store") and this file is not used.
export function FakeSharedAnswer({ token }: { token: string }) {
  const r = useLoaded(() => getShared(token), `shared:${token}`);
  if (r.status === "loading") return <Loading />;
  return <SharedAnswerView shared={r.status === "ready" ? (r.value ?? null) : null} />;
}
