// The chat's state and rules, as a plain reducer (no React, no styling).
// Key trust rule: citations are stored only from the single `citations` event,
// so the screen can never show a citation before verification finished.
import { failureFromError, failureFromOutcome, type Failure } from "@/lib/failure";
import type { Citation, HistoryMessage, Outcome, StreamEvent } from "@/lib/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  status: "streaming" | "done" | "failed";
  /** null until the citations event arrives. */
  citations: Citation[] | null;
  dataAsOf: string | null;
  removedCount: number;
  /** The API's own "one authority was removed" sentence, when it sent one. */
  note: string | null;
  /** How the turn ended, as reported with the citations. null until then. */
  outcome: Outcome | null;
  failure: Failure | null;
}

export interface ChatState {
  messages: ChatMessage[];
  answersLeft: number | null;
}

export type ChatAction =
  | { type: "ask"; userId: string; assistantId: string; question: string }
  | { type: "event"; id: string; event: StreamEvent }
  | { type: "interrupted"; id: string }
  | { type: "dropLastTurn" }
  | { type: "load"; messages: ChatMessage[] };

export const initialChatState: ChatState = { messages: [], answersLeft: null };

const blank = (id: string): ChatMessage => ({
  id,
  role: "assistant",
  text: "",
  status: "streaming",
  citations: null,
  dataAsOf: null,
  removedCount: 0,
  note: null,
  outcome: null,
  failure: null,
});

export function fromHistory(m: HistoryMessage, dataAsOf: string | null): ChatMessage {
  return {
    id: m.id,
    role: m.role,
    text: m.content,
    status: "done",
    citations: m.citations,
    dataAsOf,
    removedCount: 0,
    note: null,
    outcome: m.role === "assistant" ? "answered" : null,
    failure: null,
  };
}

function patch(state: ChatState, id: string, fn: (m: ChatMessage) => ChatMessage): ChatState {
  return { ...state, messages: state.messages.map((m) => (m.id === id ? fn(m) : m)) };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "ask":
      return {
        ...state,
        messages: [
          ...state.messages,
          { ...blank(action.userId), role: "user", text: action.question, status: "done" },
          blank(action.assistantId),
        ],
      };

    case "event": {
      const ev = action.event;
      return patch(state, action.id, (m) => {
        if (m.status !== "streaming") return m; // late events are ignored
        switch (ev.type) {
          case "text":
            return { ...m, text: m.text + ev.text };
          case "citations":
            return {
              ...m,
              citations: ev.citations,
              dataAsOf: ev.dataAsOf,
              removedCount: ev.removedCount,
              note: ev.note,
              outcome: ev.outcome,
            };
          case "done": {
            // `done` without a citations event means the answer was never
            // verified, so it must not be shown as if it were.
            const failure =
              m.outcome === null ? failureFromError("missing_citations", null) : failureFromOutcome(m.outcome);
            if (m.outcome === null) return { ...m, status: "failed", text: "", citations: null, failure };
            // A non-answer (not found, out of scope...) shows its own screen, not the text.
            return { ...m, status: "done", failure, text: failure ? "" : m.text };
          }
          case "error":
            // Drop partial text and any citations: an unfinished answer was
            // never verified and must not be shown as if it were.
            return {
              ...m,
              status: "failed",
              text: "",
              citations: null,
              failure: failureFromError(ev.code, ev.requestId),
            };
        }
      });
    }

    case "interrupted":
      return patch(state, action.id, (m) =>
        m.status === "streaming"
          ? { ...m, status: "failed", text: "", citations: null, failure: failureFromError("stream_interrupted", null) }
          : m,
      );

    case "dropLastTurn":
      return { ...state, messages: state.messages.slice(0, -2) };

    case "load":
      return { ...state, messages: action.messages };
  }
}

/** answers_left changes only via `done`; kept out of the message list. */
export function answersLeftFrom(event: StreamEvent): number | null {
  return event.type === "done" ? event.answersLeft : null;
}
