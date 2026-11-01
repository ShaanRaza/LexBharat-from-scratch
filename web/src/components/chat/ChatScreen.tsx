"use client";
import { SearchBar, StandingNotices } from "@/components/ui";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { useChat } from "@/lib/chat/useChat";
import { AnswerView } from "./AnswerView";

export function ChatScreen() {
  const { answers, ask, busy } = useChat();
  return (
    <div className="flex flex-col gap-section">
      <DemoBanner />
      <SearchBar onSubmit={ask} disabled={busy} />
      <div className="flex flex-col gap-4">
        {answers.map((a, i) => (
          <section key={i} aria-label="Answer" className="flex flex-col gap-2">
            <h2 className="text-lead font-bold">{a.question}</h2>
            {a.status === "streaming" && !a.text && <p className="text-ink-soft">Searching courts and Acts</p>}
            {(a.text || a.failure) && <AnswerView answer={a} onRetry={() => ask(a.question)} />}
            {a.status === "streaming" && a.text && <p className="text-small text-ink-soft">Checking each source</p>}
          </section>
        ))}
      </div>
      <StandingNotices dataAsOf={answers.findLast((a) => a.citations)?.citations?.data_as_of} />
    </div>
  );
}
