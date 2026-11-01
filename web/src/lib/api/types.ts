// Hand-written from api/schemas.py (commit 7cc0e14). No shared imports with api/
// (CLAUDE.md section 2 rule 3). When OpenAPI is live, regenerate and compare.
// Deliberately NO judge or party-name fields anywhere.

export type ErrorCode =
  | "unauthenticated" | "forbidden" | "not_found" | "validation_error"
  | "quota_exceeded" | "rate_limited" | "out_of_scope" | "not_found_in_dataset"
  | "feature_disabled" | "service_unavailable" | "internal_error";

export type ApiErrorBody = { code: ErrorCode; message: string; request_id: string };

export type CitationKind = "judgment" | "act";
export type CitationStatus = "verified" | "partly" | "unchecked";

export type Citation = {
  source_id: string; // S1..S8
  kind: CitationKind;
  anchor: string | null;
  act_slug: string | null;
  section: string | null;
  record_id: string;
  title: string | null;
  citation_string: string | null; // exactly as recorded
  url: string | null;
  status: CitationStatus;
};

export type CitationsEvent = {
  citations: Citation[];
  removed_count: number;
  data_as_of: string;
  credit: string;
  notice: string;
};

// Live progress: a step name and counts only. Never a case name, citation, quote or id.
export type StepName = "understanding" | "searching" | "checking" | "writing" | "verifying";
export type StepEventData = { step: StepName; found: number | null; kept: number | null };

export type StreamEvent =
  | { event: "step"; data: StepEventData }
  | { event: "token"; data: { text: string } }
  | { event: "citations"; data: CitationsEvent }
  | { event: "done"; data: { message_id: string | null; from_cache: boolean; refused: boolean; reason?: "out_of_scope" | "not_found" | null; message_key?: string | null } }
  | { event: "error"; data: ApiErrorBody };

export type Provenance = {
  data_as_of: string;
  snapshot_version: string;
  credit: string;
  notice: string;
};

export type CaseParagraph = { anchor: string; text: string };

export type CaseOut = {
  record_id: string;
  title: string | null;
  court: string | null;
  decision_date: string | null;
  case_number: string | null;
  citation_string: string | null;
  url: string | null;
  paragraphs: CaseParagraph[];
  provenance: Provenance;
};

export type SectionOut = {
  act_slug: string;
  act_name: string;
  act_year: number | null;
  section: string;
  section_title: string | null;
  text: string;
  source_url: string | null;
  in_force: boolean | null;
  act_status_checked: boolean;
  provenance: Provenance;
};

export type ConsentIn = { notice_version: string; purpose: string };

export type Plan = "free" | "student" | "pro" | "chambers";

export type MeOut = {
  id: string;
  email: string | null;
  name: string | null;
  role?: "advocate" | "student" | "in-house" | "other" | null;
  plan: Plan;
  answers_left_this_month: number | null; // null = limit not configured yet
};

// Descriptive counts only. Never a prediction or a win chance.
export type StatsRow = { court: string; year: number; outcome_label: string; count: number };
export type StatsOut = { rows: StatsRow[]; live: boolean; provenance: Provenance };

// Next-question suggestions and the "Improve my question" helper (question text only).
export type FollowupsOut = { suggestions: string[] };
export type ImproveOut = { text: string; changed: boolean };

// What the dataset covers: read from GET /coverage, never typed in the web app.
export type CoverageItem = { id: string; label: string };
export type CoverageOut = {
  status: "placeholder" | "measured";
  sentence: string;
  sentence_approved: boolean;
  not_in_dataset_message: string;
  courts: CoverageItem[];
  instruments: CoverageItem[];
  excluded: string[];
  measured_at: string | null;
  provenance: Provenance;
};

// Matters (PRD-v2 O11). "Matter" or "Project" is only the `kind` label.
export type MatterKind = "matter" | "project";
export type MatterStatus = "active" | "archived";
export type MatterOut = {
  id: string;
  title: string;
  kind: MatterKind;
  status: MatterStatus;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  conversation_count: number;
  document_count: number;
};
export type ConversationOut = {
  id: string;
  module: "research" | "document";
  title: string | null;
  message_count: number;
  matter_id: string | null;
  created_at: string;
  updated_at: string;
};
export type MatterDetail = MatterOut & { conversations: ConversationOut[] };
export type MatterDeleteMode = "unfile" | "everything";
export type MatterDeleted = { mode: MatterDeleteMode; documents_deleted: number; conversations_deleted: number };

export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  from_cache: boolean;
  citations: Citation[];
  created_at: string;
};
export type ConversationDetail = ConversationOut & { messages: StoredMessage[]; provenance: Provenance | null };

// A match in the user's own saved work (never anyone else's).
export type HistoryHit = {
  kind: "conversation" | "message";
  conversation_id: string;
  message_id: string | null;
  matter_id: string | null;
  title: string | null;
  snippet: string;
  created_at: string;
};
