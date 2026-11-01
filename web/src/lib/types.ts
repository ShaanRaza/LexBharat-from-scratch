// Shapes of the data the website gets from the HTTP API (docs/API.md).
// docs/API.md does not spell out every field yet, so the shapes below follow
// docs/DATA-MODEL.md. If the backend differs, change THIS file and api.ts only.

/** The one error format every route uses. */
export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string };
}

/**
 * What the verifier decided about one citation (docs/API.md, api/schemas.py).
 * Only "verified" earns a tick. "partly" earns a warning mark.
 * "unverified" never gets a tick (the API normally removes failed citations,
 * so this is the safe default for anything unrecognised).
 */
export type CitationStatus = "verified" | "partly" | "unverified";

/** One checked citation (S1-S8) from the single `citations` event. */
export interface Citation {
  source_id: string; // "S1" .. "S8"
  record_id: string;
  title: string;
  /** Citation string exactly as stored. null when the dataset has none. */
  citation_string: string | null;
  /** The record's pdf_url (judgments) or source_url (acts). */
  url: string | null;
  status: CitationStatus;
  /** Label from the API ("Record found in dataset"); null = use our copy. */
  status_label: string | null;
  // The fields below are NOT in the API yet (see the web report). Without
  // `kind` the site cannot tell a judgment from an Act, so it shows no in-site
  // link rather than a wrong one.
  kind: "judgment" | "act" | null;
  /** Paragraph anchor in the judgment, e.g. "p12". */
  anchor: string | null;
  act_slug: string | null;
  section: string | null;
  act_status: string | null;
}

/** How the turn ended. "provider_failed" is not in the API yet (UX-COPY needs it). */
export type Outcome = "answered" | "not_found" | "out_of_scope" | "provider_failed";

/** Events the answer stream can produce (SSE, per docs/API.md). */
export type StreamEvent =
  | { type: "text"; text: string }
  | {
      type: "citations";
      citations: Citation[];
      outcome: Outcome;
      dataAsOf: string | null;
      removedCount: number;
      note: string | null;
    }
  | {
      type: "done";
      messageId: string | null;
      requestId: string | null;
      answersLeft: number | null;
    }
  | { type: "error"; code: string; message: string; requestId: string | null };

export interface Me {
  name: string | null;
  email: string | null;
  plan: string;
  answers_left: number | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
}

export interface CaseParagraph {
  /** Element id and URL fragment, e.g. "p12" (from the API). */
  anchor: string;
  text: string;
}

/** A judgment. Judges and party names are deliberately NOT part of this type. */
export interface CaseRecord {
  record_id: string;
  title: string;
  court: string;
  decision_date: string | null;
  case_number: string | null;
  citation_string: string | null;
  pdf_url: string | null;
  paragraphs: CaseParagraph[];
  data_as_of: string | null;
}

export interface ActSection {
  act_name: string;
  act_slug: string;
  act_year: number | null;
  section_number: string;
  section_title: string | null;
  text: string;
  /** null = "in-force status not checked" (only 1,568 of 22,264 acts have it). */
  act_status: string | null;
  source_url: string | null;
  data_as_of: string | null;
}
