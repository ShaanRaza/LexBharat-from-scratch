import { AnswerView } from "@/components/chat/AnswerView";
import { Card, StandingNotices } from "@/components/ui";
import { SHARED_UNAVAILABLE } from "@/lib/copy";
import type { AnswerState } from "@/lib/chat/state";
import type { SharedAnswerOut } from "@/lib/api/types";

// One shared answer, read-only. It shows the per-citation ticks (with their words), the
// data-as-of date, the CC BY credit and the not-legal-advice notice, and nothing about
// who shared it. No Copy, Share or follow-up controls.
export function SharedAnswerView({ shared }: { shared: SharedAnswerOut | null }) {
  if (!shared) {
    return (
      <Card role="alert">
        <p className="font-bold text-notfound">{SHARED_UNAVAILABLE}</p>
      </Card>
    );
  }
  const p = shared.provenance;
  const answer: AnswerState = {
    question: shared.question,
    text: shared.text,
    steps: [],
    citations: { citations: shared.citations, removed_count: 0, data_as_of: p.data_as_of, credit: p.credit, notice: p.notice },
    status: "done",
    failure: null,
    refused: false,
    messageId: null,
  };
  return (
    <article className="flex flex-col gap-3">
      <h2 className="text-lead font-bold">{shared.question}</h2>
      <AnswerView answer={answer} />
      <StandingNotices dataAsOf={p.data_as_of} />
    </article>
  );
}
