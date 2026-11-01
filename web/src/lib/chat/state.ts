// Chat logic with no styling in it. A reducer folds stream events into one answer.
import type { ApiErrorBody, Citation, CitationsEvent, StepEventData, StreamEvent } from "@/lib/api/types";

export type FailureKind = "notFound" | "outsideCoverage" | "notInDataset" | "usageLimit" | "serviceError";

export type AnswerState = {
  question: string;
  text: string;
  // Progress so far, in the order received. Names and counts only (never a citation).
  steps: StepEventData[];
  // null until the single citations event arrives. While null no citation is shown.
  citations: CitationsEvent | null;
  status: "streaming" | "done" | "failed";
  failure: FailureKind | null;
  refused: boolean;
  // The saved answer's id, from the done event (null in fake mode or if refused).
  messageId: string | null;
};

export function newAnswer(question: string): AnswerState {
  return { question, text: "", steps: [], citations: null, status: "streaming", failure: null, refused: false, messageId: null };
}

export function failureFor(e: ApiErrorBody): FailureKind {
  switch (e.code) {
    case "not_found_in_dataset": return "notFound";
    case "out_of_scope": return "outsideCoverage";
    case "quota_exceeded": return "usageLimit";
    default: return "serviceError";
  }
}

// A refusal's screen: "not in our dataset" has its own message key and is NOT the
// out-of-coverage screen (O7). Anything else refused out of scope is the coverage screen.
function refusalFailure(reason?: string | null, messageKey?: string | null): FailureKind {
  if (messageKey === "out_of_scope:not_in_dataset") return "notInDataset";
  return reason === "out_of_scope" ? "outsideCoverage" : "notFound";
}

export function applyEvent(s: AnswerState, ev: StreamEvent): AnswerState {
  switch (ev.event) {
    case "step":
      return { ...s, steps: [...s.steps, ev.data] };
    case "token":
      return { ...s, text: s.text + ev.data.text };
    case "citations":
      // Exactly one is expected; a second is ignored so nothing can change after the fact.
      return s.citations ? s : { ...s, citations: ev.data };
    case "done":
      return {
        ...s,
        status: "done",
        refused: ev.data.refused,
        messageId: ev.data.message_id,
        // A refusal with no explicit reason is treated as "nothing found": nothing is written.
        failure: ev.data.refused && !s.failure ? refusalFailure(ev.data.reason, ev.data.message_key) : s.failure,
      };
    case "error":
      return { ...s, status: "failed", failure: failureFor(ev.data), text: "", steps: [] };
  }
}

// The stream ended. If no done/error arrived (dropped connection) the answer is a
// service error and the partial text is cleared, same as an error event.
export function endOfStream(s: AnswerState): AnswerState {
  return s.status === "streaming" ? { ...s, status: "failed", failure: "serviceError", text: "", steps: [] } : s;
}

// Only verified/partly citations are ever shown; anything else is treated as removed.
export function isShown(c: Citation): boolean {
  return c.status === "verified" || c.status === "partly" || c.status === "unchecked";
}

export type Segment =
  | { type: "text"; text: string }
  | { type: "cite"; citation: Citation };

// Splits answer text at [S1]..[S8] markers. Before the citations event arrives the
// markers are hidden, so a citation can never appear and then vanish. After it, a
// marker with a checked citation becomes a chip; a marker without one (removed) is dropped.
export function toSegments(text: string, ce: CitationsEvent | null): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(/\[(S[1-8])\]/g)) {
    const i = m.index ?? 0;
    if (i > last) out.push({ type: "text", text: text.slice(last, i) });
    const c = ce?.citations.filter(isShown).find((x) => x.source_id === m[1]);
    if (c) out.push({ type: "cite", citation: c });
    last = i + m[0].length;
  }
  if (last < text.length) out.push({ type: "text", text: text.slice(last) });
  return out;
}

// Link target inside the app for a citation.
export function citationHref(c: Citation): string {
  if (c.kind === "act" && c.act_slug && c.section) return `/acts/${c.act_slug}/${c.section}`;
  return `/cases/${encodeURIComponent(c.record_id)}${c.anchor ? `#${c.anchor}` : ""}`;
}

// How a citation is named on screen. The title field is NOT used anywhere: for a
// judgment it is party names (CLAUDE.md section 6). To switch titles back on, change
// only this function (owner decision pending).
export function citationName(c: Citation): string {
  if (c.kind === "act") return `Act section ${c.section ?? ""} (${c.act_slug ?? c.record_id})`.replace("  ", " ");
  return c.citation_string ?? "Judgment";
}
