// A stand-in backend for NEXT_PUBLIC_USE_FAKE_API=1. Behaviour is chosen by
// words in the question so every screen can be seen without a backend:
//   "limit"          -> usage limit reached
//   "outage"/"error" -> service error
//   "writer"         -> sources found but the writer failed
//   "high court"     -> outside coverage
//   "unknown"        -> not found
//   anything else    -> a sample answer with 3 citations (tick, warning, none)
import { ApiError } from "../api-error";
import type { ApiClient } from "../api";
import type { HistoryMessage, Outcome, StreamEvent } from "../types";
import {
  SAMPLE_DATA_AS_OF,
  sampleAnswer,
  sampleCase,
  sampleCitations,
  sampleSection,
  sampleSectionWithStatus,
} from "./sampleData";

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export function createFakeApi(delayMs = 40): ApiClient {
  let answersLeft = 20;
  const conversations: { id: string; title: string; messages: HistoryMessage[] }[] = [
    { id: "sample-conv-1", title: "Sample: bail in economic offences", messages: [] },
    { id: "sample-conv-2", title: "Sample: section 138 cheque bounce", messages: [] },
  ];

  return {
    async getMe() {
      return { name: "Sample User", email: "sample@example.org", plan: "free", answers_left: answersLeft };
    },
    async listConversations() {
      return { items: conversations.map(({ id, title }) => ({ id, title })), next_cursor: null };
    },
    async createConversation() {
      const id = `sample-conv-${conversations.length + 1}`;
      conversations.unshift({ id, title: "New sample chat", messages: [] });
      return { id };
    },
    async getConversation(id) {
      const found = conversations.find((c) => c.id === id);
      if (!found) throw new ApiError("not_found", "Conversation not found.", 404);
      return { ...found, data_as_of: SAMPLE_DATA_AS_OF };
    },
    async getCase(id) {
      if (id !== sampleCase.record_id) throw new ApiError("not_found", "Judgment not found.", 404);
      return sampleCase;
    },
    async getSection(act, n) {
      if (act === sampleSectionWithStatus.act_slug && n === "1") return sampleSectionWithStatus;
      if (act === sampleSection.act_slug && n === "1") return sampleSection;
      throw new ApiError("not_found", "Section not found.", 404);
    },
    async recordConsent() {
      /* nothing to store in fake mode */
    },
    async *streamMessage(_conversationId, content, signal): AsyncGenerator<StreamEvent> {
      const q = content.toLowerCase();
      await wait(delayMs);
      if (signal?.aborted) return;

      if (q.includes("limit")) {
        yield { type: "error", code: "quota_exceeded", message: "", requestId: "fake-req-1" };
        return;
      }
      if (q.includes("outage") || q.includes("error")) {
        yield { type: "error", code: "internal_error", message: "", requestId: "fake-req-2" };
        return;
      }
      const cites = (outcome: Outcome, list = sampleCitations, removed = 0): StreamEvent => ({
        type: "citations",
        citations: list,
        outcome,
        dataAsOf: SAMPLE_DATA_AS_OF,
        removedCount: removed,
        note: removed ? "One authority could not be verified and was removed." : null,
      });
      const done = (): StreamEvent => ({ type: "done", messageId: "fake-msg", requestId: "fake-req", answersLeft });

      if (q.includes("unknown")) {
        yield cites("not_found", []);
        yield done();
        return;
      }
      if (q.includes("high court")) {
        yield cites("out_of_scope", []);
        yield done();
        return;
      }
      if (q.includes("writer")) {
        // Sources found, no written answer. Nothing was checked: no ticks.
        yield cites("provider_failed", sampleCitations.map((c) => ({ ...c, status: "unverified" as const, status_label: null })));
        yield done();
        return;
      }

      // Normal answer: text word by word. Real API sends no [S1] markers
      // before the citations event; the hook also strips any that slip in.
      for (const word of sampleAnswer.split(/(?<= )/)) {
        if (signal?.aborted) return;
        yield { type: "text", text: word };
        await wait(delayMs / 4);
      }
      await wait(delayMs);
      yield cites("answered", sampleCitations, 1);
      answersLeft = Math.max(0, answersLeft - 1);
      yield done();
    },
  };
}
