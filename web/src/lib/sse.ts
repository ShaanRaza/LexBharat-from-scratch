// Reads a server-sent-events stream (docs/API.md "Streaming contract").
// An SSE message looks like:   event: text\n data: {"text":"Hello "}\n\n
import type { Citation, Outcome, StreamEvent, Support } from "./types";

export interface RawSseMessage {
  event: string;
  data: string;
}

/** Splits a byte stream into SSE messages (handles chunks cut mid-line). */
export async function* readSse(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<RawSseMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const msg = parseBlock(block);
        if (msg) yield msg;
      }
    }
    const tail = parseBlock(buffer);
    if (tail) yield tail;
  } finally {
    reader.releaseLock();
  }
}

function parseBlock(block: string): RawSseMessage | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue; // blank or comment
    const i = line.indexOf(":");
    const field = i === -1 ? line : line.slice(0, i);
    const val = i === -1 ? "" : line.slice(i + 1).replace(/^ /, "");
    if (field === "event") event = val;
    else if (field === "data") data.push(val);
  }
  return data.length ? { event, data: data.join("\n") } : null;
}

const OUTCOMES: Outcome[] = ["answered", "not_found", "out_of_scope", "provider_failed"];
const SUPPORTS: Support[] = ["supports", "partly", "does_not_support"];

const str = (v: unknown): string | null => (typeof v === "string" ? v : null);

/** Cleans one citation from the wire. `verified` is true ONLY for real `true`. */
export function normalizeCitation(raw: unknown): Citation | null {
  if (typeof raw !== "object" || raw === null) return null;
  const r = raw as Record<string, unknown>;
  const sourceId = str(r.source_id);
  const recordId = str(r.record_id);
  if (!sourceId || !recordId) return null;
  return {
    source_id: sourceId,
    record_id: recordId,
    kind: r.kind === "act" ? "act" : "judgment",
    title: str(r.title) ?? recordId,
    citation_string: str(r.citation_string),
    link: str(r.link),
    paragraph: typeof r.paragraph === "number" ? r.paragraph : null,
    act_slug: str(r.act_slug),
    section: str(r.section),
    act_status: str(r.act_status),
    excerpt: str(r.excerpt),
    verified: r.verified === true,
    support: SUPPORTS.includes(r.support as Support) ? (r.support as Support) : null,
  };
}

/** Turns one raw SSE message into a typed event (null = ignore it). */
export function toStreamEvent(msg: RawSseMessage): StreamEvent | null {
  let d: Record<string, unknown>;
  try {
    const parsed: unknown = JSON.parse(msg.data);
    d = typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return null;
  }
  switch (msg.event) {
    case "text":
      return typeof d.text === "string" ? { type: "text", text: d.text } : null;
    case "citations": {
      const list = Array.isArray(d.citations) ? d.citations : [];
      return {
        type: "citations",
        citations: list.map(normalizeCitation).filter((c): c is Citation => c !== null),
        dataAsOf: str(d.data_as_of),
        removedCount: typeof d.removed_count === "number" ? d.removed_count : 0,
      };
    }
    case "done":
      return {
        type: "done",
        messageId: str(d.message_id),
        outcome: OUTCOMES.includes(d.outcome as Outcome) ? (d.outcome as Outcome) : "answered",
        answersLeft: typeof d.answers_left === "number" ? d.answers_left : null,
      };
    case "error": {
      const e = (typeof d.error === "object" && d.error !== null ? d.error : d) as Record<string, unknown>;
      return {
        type: "error",
        code: str(e.code) ?? "internal_error",
        message: str(e.message) ?? "",
        requestId: str(e.request_id),
      };
    }
    default:
      return null;
  }
}
