// Shapes of the data the website gets from the HTTP API (docs/API.md).
// docs/API.md does not spell out every field yet, so the shapes below follow
// docs/DATA-MODEL.md. If the backend differs, change THIS file and api.ts only.

/** The one error format every route uses. */
export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string };
}

/** How the citation verifier rated the passage against its sentence. */
export type Support = "supports" | "partly" | "does_not_support";

/** One checked citation (S1-S8) from the single `citations` event. */
export interface Citation {
  source_id: string; // "S1" .. "S8"
  record_id: string;
  kind: "judgment" | "act";
  title: string;
  /** Citation string exactly as stored. null when the dataset has none. */
  citation_string: string | null;
  /** The record's pdf_url (judgments) or source_url (acts). */
  link: string | null;
  /** Paragraph number inside the judgment, for the #p<n> anchor. */
  paragraph: number | null;
  /** Act routing, so the site can link to /acts/{act}/{section}. */
  act_slug: string | null;
  section: string | null;
  /** Only shown when filled; otherwise "in-force status not checked". */
  act_status: string | null;
  excerpt: string | null;
  /** True only when verifier checks 1-3 passed. */
  verified: boolean;
  support: Support | null;
}

/** What `done` says about how the turn ended. */
export type Outcome = "answered" | "not_found" | "out_of_scope" | "provider_failed";

/** Events the answer stream can produce (SSE, per docs/API.md). */
export type StreamEvent =
  | { type: "text"; text: string }
  | {
      type: "citations";
      citations: Citation[];
      dataAsOf: string | null;
      removedCount: number;
    }
  | {
      type: "done";
      messageId: string | null;
      outcome: Outcome;
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
  data_as_of: string | null;
}

export interface CaseParagraph {
  n: number;
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
  data_as_of: string;
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
  data_as_of: string;
}
