"use client";
import Link from "next/link";
import { Card, StandingNotices } from "@/components/ui";
import { AnswerView } from "@/components/chat/AnswerView";
import { getConversation, listMatters, moveConversation } from "@/lib/api/client";
import { MATTER_FILE_UNDER } from "@/lib/copy";
import type { AnswerState } from "@/lib/chat/state";
import { useLoaded } from "@/lib/matters/useLoaded";
import type { StoredMessage } from "@/lib/api/types";
import { MatterPicker } from "./MatterPicker";

// A saved conversation, read-only: each stored answer is shown with its stored ticks
// (the same chips as in the chat). The "file under" picker moves it between matters.
export function ConversationScreen({ id }: { id: string }) {
  const conv = useLoaded(() => getConversation(id), `conv:${id}`);
  const matters = useLoaded(() => listMatters("active"), "matters:active");
  if (conv.status === "loading") return <p className="text-ink-soft">Loading</p>;
  if (conv.status === "error" || !conv.value) {
    return (
      <Card role="alert">
        <p className="font-bold text-notfound">This was not found</p>
        <Link href="/history" className="mt-2 inline-block text-small font-semibold text-accent underline">
          Back to history
        </Link>
      </Card>
    );
  }
  const c = conv.value;
  const prov = c.provenance;
  const answers = pairUp(c.messages).map(([q, a]): AnswerState => ({
    question: q,
    text: a.content,
    steps: [],
    citations: prov
      ? { citations: a.citations, removed_count: 0, data_as_of: prov.data_as_of, credit: prov.credit, notice: prov.notice }
      : null,
    status: "done",
    failure: null,
    refused: false,
    messageId: a.id,
  }));
  return (
    <div className="flex flex-col gap-4">
      <h1 className="break-words text-title font-bold">{c.title ?? "Untitled conversation"}</h1>
      <MatterPicker
        label={MATTER_FILE_UNDER}
        matters={matters.value ?? []}
        value={c.matter_id}
        onChange={async (matterId) => {
          await moveConversation(id, matterId);
          conv.reload();
        }}
      />
      {answers.map((a) => (
        <section key={a.messageId} aria-label="Answer" className="flex flex-col gap-2">
          <h2 className="text-lead font-bold">{a.question}</h2>
          <AnswerView answer={a} />
        </section>
      ))}
      <StandingNotices dataAsOf={prov?.data_as_of} />
    </div>
  );
}

// Pair each question with the answer that follows it.
function pairUp(messages: StoredMessage[]): [string, StoredMessage][] {
  const out: [string, StoredMessage][] = [];
  let q = "";
  for (const m of messages) {
    if (m.role === "user") q = m.content;
    else out.push([q, m]);
  }
  return out;
}
