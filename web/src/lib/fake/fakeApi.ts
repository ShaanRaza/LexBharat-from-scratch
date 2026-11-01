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
import type { HistoryMessage, StreamEvent } from "../types";
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
      return found;
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
      if (q.includes("unknown")) {
        yield { type: "citations", citations: [], dataAsOf: SAMPLE_DATA_AS_OF, removedCount: 0 };
        yield { type: "done", messageId: "fake-msg", outcome: "not_found", answersLeft };
        return;
      }
      if (q.includes("high court")) {
        yield { type: "done", messageId: "fake-msg", outcome: "out_of_scope", answersLeft };
        return;
      }
      if (q.includes("writer")) {
        yield { type: "citations", citations: sampleCitations.map((c) => ({ ...c, verified: false, support: null })), dataAsOf: SAMPLE_DATA_AS_OF, removedCount: 0 };
        yield { type: "done", messageId: "fake-msg", outcome: "provider_failed", answersLeft };
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
      yield { type: "citations", citations: sampleCitations, dataAsOf: SAMPLE_DATA_AS_OF, removedCount: 1 };
      answersLeft = Math.max(0, answersLeft - 1);
      yield { type: "done", messageId: "fake-msg", outcome: "answered", answersLeft };
    },
  };
}
