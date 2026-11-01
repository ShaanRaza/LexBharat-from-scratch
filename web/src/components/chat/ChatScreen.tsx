"use client";
import { SearchBar, StandingNotices } from "@/components/ui";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { useChat } from "@/lib/chat/useChat";
import { useSource } from "@/lib/chat/useSource";
import { useUsage } from "@/lib/chat/useUsage";
import { SourcePane } from "./SourcePane";
import { UsageMeter } from "./UsageMeter";
import { AnswerView } from "./AnswerView";
import { FailureCard } from "./FailureCard";
import { ProgressPanel } from "./ProgressPanel";

// Chat on the left; the cited record opens on the right. Below the large breakpoint the
// two stack (answer first, source under it) instead of sitting side by side.
export function ChatScreen() {
  const { answers, ask, busy } = useChat();
  const left = useUsage();
  const source = useSource();
  const dataAsOf = answers.findLast((a) => a.citations)?.citations?.data_as_of;
  const split = source.open !== null;
  return (
    <div className={`flex flex-col gap-section ${split ? "w-full" : "mx-auto w-full max-w-reading"}`}>
      <div className="flex w-full max-w-reading flex-col gap-section">
        <DemoBanner />
        <SearchBar onSubmit={ask} disabled={busy || left === 0} />
        <UsageMeter left={left} />
        {left === 0 && <FailureCard kind="usageLimit" />}
      </div>
      <div className={split ? "grid gap-section lg:grid-cols-2" : "flex flex-col"}>
        <div className="flex min-w-0 flex-col gap-4">
          {answers.map((a, i) => (
            <section key={i} aria-label="Answer" className="flex flex-col gap-2">
              <h2 className="text-lead font-bold">{a.question}</h2>
              {a.status === "streaming" && <ProgressPanel steps={a.steps} />}
              {(a.text || a.failure) && (
                <AnswerView answer={a} onRetry={() => ask(a.question)} onOpenSource={source.openCitation} />
              )}
            </section>
          ))}
        </div>
        {source.open && (
          <SourcePane
            citation={source.open}
            state={source.state}
            dataAsOf={dataAsOf ?? ""}
            clicks={source.clicks}
            onClose={source.close}
          />
        )}
      </div>
      <StandingNotices dataAsOf={dataAsOf} />
    </div>
  );
}
