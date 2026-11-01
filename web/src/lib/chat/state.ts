// Chat logic with no styling in it. A reducer folds stream events into one answer.
import type { ApiErrorBody, Citation, CitationsEvent, StreamEvent } from "@/lib/api/types";

export type FailureKind = "notFound" | "outsideCoverage" | "usageLimit" | "serviceError";

export type AnswerState = {
  question: string;
  text: string;
  // null until the single citations event arrives. While null no citation is shown.
  citations: CitationsEvent | null;
  status: "streaming" | "done" | "failed";
  failure: FailureKind | null;
  refused: boolean;
};

export function newAnswer(question: string): AnswerState {
  return { question, text: "", citations: null, status: "streaming", failure: null, refused: false };
}

export function failureFor(e: ApiErrorBody): FailureKind {
  switch (e.code) {
    case "not_found_in_dataset": return "notFound";
    case "out_of_scope": return "outsideCoverage";
    case "quota_exceeded": return "usageLimit";
    default: return "serviceError";
  }
}

export function applyEvent(s: AnswerState, ev: StreamEvent): AnswerState {
  switch (ev.event) {
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
        // A refusal with no explicit reason is treated as "nothing found": nothing is written.
        failure: ev.data.refused && !s.failure ? "notFound" : s.failure,
      };
    case "error":
      return { ...s, status: "failed", failure: failureFor(ev.data), text: "" };
  }
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
    const c = ce?.citations.find((x) => x.source_id === m[1]);
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
