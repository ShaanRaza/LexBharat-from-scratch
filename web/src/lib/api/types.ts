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

export type ForceStatus = "in_force" | "repealed" | "not_checked";
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
  force_status: ForceStatus;
  in_force: boolean | null; // derived from force_status, kept for older clients
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
  not_found_message: string;
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

// Share a saved answer by link (O14). The token is shown once; only a hash is stored.
export type ShareCreated = { id: string; token: string; path: string; expires_at: string };
export type ShareLink = { id: string; message_id: string; created_at: string; expires_at: string; revoked_at: string | null };
export type SharedAnswerOut = {
  question: string;
  text: string;
  citations: Citation[];
  expires_at: string;
  provenance: Provenance;
};

// ---- Launch pages (pricing, account, admin, help). Several routes do not exist yet: each
// call in lib/api/client.ts says which one is needed. -----------------------------------
export type PlanOut = {
  id: string;
  name: string;
  // Text from the server's plans table (e.g. "Sample", or whatever the owner configures).
  // The web app never contains a price: pricing is the owner's, in config (O10).
  price_text: string;
  limits: { label: string; value: number | null }[]; // plain numbers, never credits
  current: boolean;
};
export type ConsentRow = { id: string; notice_version: string; purpose: string; given_at: string; withdrawn_at: string | null };

export type ReportReason = "citation" | "answer" | "missing" | "other";
export type ReportRow = {
  id: string;
  message_id: string;
  reason: ReportReason;
  comment: string | null;
  status: "new" | "in_review" | "resolved";
  created_at: string;
};
export type EvalRun = {
  id: string;
  status: "running" | "done";
  total: number;
  done: number;
  passed: number;
  failures: { id: string; kind: string; detail: string }[];
};
export type InventedRow = {
  id: string;
  at: string;
  reason: "not retrieved" | "record missing" | "quote not found" | "claim not supported";
  cited_text: string; // what the model wrote; shown to admins only, never to users
};
export type SpendRow = {
  day: string;
  answers: number;
  helper_calls: number;
  tokens_in: number;
  tokens_out: number;
  estimated_cost: number | null;
  cost_per_answer: number | null;
};
export type HelpArticle = { slug: string; title: string; body: string[] };
export type SupportIn = { email: string; message: string };
