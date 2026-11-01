"use client";
import { useState } from "react";
import { SearchBar, StandingNotices } from "@/components/ui";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { PRODUCT_NAME } from "@/lib/config";
import { answerToText } from "@/lib/chat/answerText";
import { copyText, downloadText } from "@/lib/chat/download";
import type { AnswerState } from "@/lib/chat/state";
import { MatterPicker } from "@/components/matters/MatterPicker";
import { listMatters, shareMessage } from "@/lib/api/client";
import { MATTER_FILE_UNDER } from "@/lib/copy";
import { useLoaded } from "@/lib/matters/useLoaded";
import { useChat } from "@/lib/chat/useChat";
import { useFollowups } from "@/lib/chat/useFollowups";
import { useImprove } from "@/lib/chat/useImprove";
import { useSource } from "@/lib/chat/useSource";
import { useUsage } from "@/lib/chat/useUsage";
import { AnswerActions } from "./AnswerActions";
import { AnswerView } from "./AnswerView";
import { FailureCard } from "./FailureCard";
import { FollowUps } from "./FollowUps";
import { ImproveButton, ImprovePanel } from "./ImproveHelper";
import { Onboarding } from "./Onboarding";
import { ProgressPanel } from "./ProgressPanel";
import { ReportAnswer } from "./ReportAnswer";
import { ShareControl } from "./ShareControl";
import { SourcePane } from "./SourcePane";
import { UsageMeter } from "./UsageMeter";

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "answer";

// Under a finished, verified answer: Copy / Export / Rewrite, then next questions.
function AfterAnswer({
  answer,
  conversationId,
  ask,
  onRewrite,
  busy,
}: {
  answer: AnswerState;
  conversationId: string | null;
  ask: (q: string) => void;
  onRewrite: (q: string) => void;
  busy: boolean;
}) {
  const ready = answer.status === "done" && !answer.failure && answer.citations !== null;
  const suggestions = useFollowups(conversationId, answer.messageId, ready);
  if (!ready) return null;
  const text = answerToText(answer);
  return (
    <div className="flex flex-col gap-3">
      <AnswerActions
        text={text}
        copy={copyText}
        onExport={(t) => downloadText(`${slug(PRODUCT_NAME)}-answer.txt`, t)}
        onRewrite={() => onRewrite(answer.question)}
      />
      {answer.messageId && (
        <ShareControl
          create={() => shareMessage(answer.messageId!)}
          copy={copyText}
          origin={typeof window === "undefined" ? "" : window.location.origin}
        />
      )}
      {answer.messageId && <ReportAnswer messageId={answer.messageId} />}
      <FollowUps suggestions={suggestions} onAsk={ask} disabled={busy} />
    </div>
  );
}

// Chat on the left; the cited record opens on the right. Below the large breakpoint the
// two stack (answer first, source under it) instead of sitting side by side.
export function ChatScreen() {
  const [matterId, setMatterId] = useState<string | null>(null);
  const matters = useLoaded(() => listMatters("active"), "chat-matters");
  const { answers, ask, busy, conversationId } = useChat(matterId);
  const left = useUsage();
  const source = useSource();
  const improve = useImprove();
  const [question, setQuestion] = useState("");
  const dataAsOf = answers.findLast((a) => a.citations)?.citations?.data_as_of;
  const split = source.open !== null;
  // Whatever way a question is sent (typed, a follow-up, a rewrite), it is an ordinary
  // new question through the whole pipeline.
  const send = (q: string) => {
    improve.dismiss();
    setQuestion("");
    ask(q);
  };
  return (
    <div className={`flex flex-col gap-section ${split ? "w-full" : "w-full max-w-reading"}`}>
      <div className="flex w-full max-w-reading flex-col gap-section">
        <DemoBanner />
        <SearchBar
          value={question}
          onChange={setQuestion}
          onSubmit={send}
          disabled={busy || left === 0}
          actions={
            <ImproveButton state={improve.state} canImprove={question.trim() !== ""} onImprove={() => improve.improve(question)} />
          }
          below={
            <ImprovePanel
              state={improve.state}
              onEdit={improve.edit}
              onUse={(t) => {
                setQuestion(t);
                improve.dismiss();
              }}
              onDismiss={improve.dismiss}
            />
          }
        />
        {(matters.value?.length ?? 0) > 0 && (
          <MatterPicker label={MATTER_FILE_UNDER} matters={matters.value ?? []} value={matterId} onChange={setMatterId} />
        )}
        <UsageMeter left={left} />
        {left === 0 && <FailureCard kind="usageLimit" />}
      </div>
      <div className={split ? "grid gap-section lg:grid-cols-2" : "flex flex-col"}>
        <div className="flex min-w-0 flex-col gap-4">
          {answers.length === 0 && <Onboarding />}
          {answers.map((a, i) => (
            <section key={i} aria-label="Answer" className="flex flex-col gap-2">
              <h2 className="text-lead font-bold">{a.question}</h2>
              {a.status === "streaming" && <ProgressPanel steps={a.steps} />}
              {(a.text || a.failure) && (
                <AnswerView answer={a} onRetry={() => ask(a.question)} onOpenSource={source.openCitation} />
              )}
              <AfterAnswer answer={a} conversationId={conversationId} ask={send} onRewrite={setQuestion} busy={busy || left === 0} />
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
