// Turns the API's JSON (api/schemas.py) into the shapes the site uses.
// This is the only place that knows the wire format of normal (non-stream)
// responses, so a backend change means a change here, not in screens.
import type {
  ActSection,
  CaseRecord,
  Citation,
  CitationStatus,
  ConversationSummary,
  HistoryMessage,
  Me,
} from "./types";

type Obj = Record<string, unknown>;
const obj = (v: unknown): Obj => (typeof v === "object" && v !== null ? (v as Obj) : {});
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" ? v : null);

/** Provenance block -> the data-as-of date (null if missing). */
export const dataAsOf = (provenance: unknown): string | null => str(obj(provenance).data_as_of);

/**
 * Status from a live `citations` event. Only the exact word "verified" earns a
 * tick and only "partly" earns a warning; anything else is "unverified".
 */
export function statusFromWire(v: unknown): CitationStatus {
  return v === "verified" ? "verified" : v === "partly" ? "partly" : "unverified";
}

/** A citation as sent in the `citations` event. */
export function citationFromEvent(raw: unknown): Citation | null {
  const r = obj(raw);
  const source_id = str(r.source_id);
  const record_id = str(r.record_id);
  if (!source_id || !record_id) return null;
  return {
    source_id,
    record_id,
    title: str(r.title) ?? record_id,
    citation_string: str(r.citation),
    url: str(r.url),
    status: statusFromWire(r.status),
    status_label: str(r.status_label),
    kind: r.kind === "act" ? "act" : r.kind === "judgment" ? "judgment" : null,
    anchor: str(r.anchor),
    act_slug: str(r.act_slug),
    section: str(r.section),
    act_status: str(r.act_status),
  };
}

/** A saved source from conversation history (it carries verified + support). */
export function citationFromHistory(raw: unknown): Citation | null {
  const r = obj(raw);
  const base = citationFromEvent({ ...r, status: undefined });
  if (!base) return null;
  // Strict: a real `true` AND the exact support word, else no tick.
  const status: CitationStatus =
    r.verified === true && r.support === "supports"
      ? "verified"
      : r.verified === true && r.support === "partly"
        ? "partly"
        : "unverified";
  return { ...base, status };
}

export function meFromWire(raw: unknown): Me {
  const r = obj(raw);
  return {
    name: str(r.name),
    email: str(r.email),
    plan: str(r.plan) ?? "free",
    answers_left: num(r.answers_left),
  };
}

export function conversationFromWire(raw: unknown): ConversationSummary | null {
  const r = obj(raw);
  const id = str(r.id);
  return id ? { id, title: str(r.title) ?? "Untitled question" } : null;
}

export function historyFromWire(raw: unknown) {
  const r = obj(raw);
  const messages: HistoryMessage[] = (Array.isArray(r.messages) ? r.messages : []).flatMap((m) => {
    const o = obj(m);
    const id = str(o.id);
    if (!id) return [];
    const role = o.role === "user" ? "user" : "assistant";
    const sources = Array.isArray(o.sources)
      ? o.sources.map(citationFromHistory).filter((c): c is Citation => c !== null)
      : [];
    // A saved answer always went through the verifier, so its sources are final.
    return [{ id, role, content: str(o.content) ?? "", citations: role === "assistant" ? sources : null } as HistoryMessage];
  });
  return {
    id: str(r.id) ?? "",
    title: str(r.title) ?? "Untitled question",
    messages,
    data_as_of: dataAsOf(r.provenance),
  };
}

export function caseFromWire(raw: unknown): CaseRecord {
  const r = obj(raw);
  return {
    record_id: str(r.record_id) ?? "",
    title: str(r.title) ?? "Untitled judgment",
    court: str(r.court) ?? "",
    decision_date: str(r.decision_date),
    case_number: str(r.case_number),
    citation_string: str(r.citation),
    pdf_url: str(r.pdf_url),
    paragraphs: (Array.isArray(r.paragraphs) ? r.paragraphs : []).flatMap((p) => {
      const o = obj(p);
      const anchor = str(o.anchor);
      return anchor ? [{ anchor, text: str(o.text) ?? "" }] : [];
    }),
    data_as_of: dataAsOf(r.provenance),
  };
}

export function sectionFromWire(raw: unknown, actSlug: string): ActSection {
  const r = obj(raw);
  const status = obj(r.status);
  return {
    act_name: str(r.act_name) ?? actSlug,
    act_slug: actSlug,
    act_year: num(r.act_year),
    section_number: str(r.section_number) ?? "",
    section_title: str(r.section_title),
    text: str(r.text) ?? "",
    // Only when the dataset checked it; otherwise the page says "not checked".
    act_status: status.checked === true ? str(status.act_status) : null,
    source_url: str(r.source_url),
    data_as_of: dataAsOf(r.provenance),
  };
}
