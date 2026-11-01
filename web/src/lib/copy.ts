// All user-facing wording that carries the trust promise or legal position lives here,
// copied from docs/UX-COPY.md. Do not improvise these strings in components.
// Strings marked NEEDS-OWNER are not quoted in UX-COPY.md; the lead must confirm them.

export const CC_BY_CREDIT = "Data: Open India Law by Vaquill AI, CC BY 4.0";

export const NOT_LEGAL_ADVICE = (productName: string) =>
  `${productName} gives information, not legal advice.`;

// The notice string the API puts in the citations event (api/schemas.py). Used by fake
// mode so it matches the real wire value. See the open question about two wordings.
export const NOT_LEGAL_ADVICE_API = "This is legal research, not legal advice.";

export const PERSONAL_ADVICE_OPENER =
  "This tool cannot advise on your own situation. Please consult an advocate."; // NEEDS-OWNER (doc gives the meaning, not the sentence)

export const VERIFICATION_LABEL = "Record found in dataset";
export const UNCHECKED_LABEL = "Support not checked";
export const PARTLY_LABEL = "Supports only partly";
export const UNVERIFIED_NOTE = "One authority could not be verified and was removed.";
export const CITATION_AS_RECORDED = "as recorded in the dataset";
export const IN_FORCE_NOT_CHECKED = "in-force status not checked";

export const FAILURES = {
  notFound: {
    title: "No matching judgments found",
    body: "No matching judgments found in our dataset (data as of the snapshot date).",
    hint: "Try rephrasing your question, or use Act lookup.",
  },
  // What the product covers is NOT typed here: the sentence comes from GET /coverage
  // (one source, core/coverage.json). The body below is only the fallback shown if that
  // call fails, and it names no category. NEEDS-OWNER: wording not approved.
  outsideCoverage: {
    title: "Outside what this version covers",
    body: "This is outside what this version covers. See the coverage page for what it does cover.",
    hint: "For those, please see the official court website.",
  },
  // A source the dataset does not hold (O7). NEEDS-OWNER: the message itself is
  // not_in_dataset_message from GET /coverage; this is the fallback.
  notInDataset: {
    title: "Not in our dataset",
    body: "This is not in our dataset.",
    hint: "See the coverage page for what the dataset holds.",
  },
  serviceError: {
    title: "We could not write an answer",
    body: "The sources we found are shown below with links, but no written answer.",
    hint: "You can try again.",
  }, // NEEDS-OWNER: UX-COPY describes this state, does not quote it
  usageLimit: {
    title: "You have used this month's research answers",
    body: "Your plan includes a fixed number of research answers a month.",
    hint: "Your limit resets next month.",
  }, // NEEDS-OWNER: no wording in UX-COPY, only "plain numbers, never credits"
  unreadableScan: {
    title: "We could not read this file",
    body: "We could not read this file. Try a clearer scan or paste the text.",
    hint: "You were not charged for this.",
  },
} as const;

// Sign-up consent. The real notice is a versioned document in legal/ and does not exist
// yet (legal/README.md). NEEDS-OWNER: wording and version below are placeholders.
export const CONSENT_NOTICE_VERSION = process.env.NEXT_PUBLIC_CONSENT_NOTICE_VERSION ?? "draft-0";
export const CONSENT_PURPOSE = "service";
export const CONSENT_TEXT =
  "I have read the consent notice and privacy policy and agree to my data being used to provide this service."; // NEEDS-OWNER

// Stats page. NEEDS-OWNER: UX-COPY gives the rule ("descriptive, never a prediction")
// but not the sentences below.
export const STATS_TITLE = "Outcome counts";
export const STATS_DESCRIPTIVE_NOTE =
  "These are counts of recorded outcomes. They describe past decisions and do not predict any case."; // NEEDS-OWNER

// Plain numbers, never credits (UX-COPY "Copy rules").
export const ANSWERS_LEFT = (n: number) => `${n} research ${n === 1 ? "answer" : "answers"} left this month`;
export const SAMPLE_LABEL = "Sample";

// Live progress panel (PRD-v2 section 4.2). Plain status words, not legal wording.
export const PROGRESS_LABELS = {
  understanding: "Understanding your question",
  searching: "Searching",
  checking: "Checking sources",
  writing: "Writing",
  verifying: "Verifying citations",
} as const;
export const PROGRESS_COUNTS = (found: number | null, kept: number | null) =>
  found === null ? "" : kept === null ? `${found} passages found` : `${found} passages found, ${kept} kept`;

// Answer actions, follow-ups and the improve helper. Plain interface words, not legal
// wording.
export const ACTION_COPY = "Copy";
export const ACTION_EXPORT = "Export";
export const ACTION_REWRITE = "Rewrite";
export const COPIED = "Copied";
export const COPY_FAILED = "Could not copy. Select the text and copy it yourself.";
export const SOURCES_HEADING = "Sources";
export const FOLLOWUPS_TITLE = "Ask next";
export const IMPROVE_LABEL = "Improve my question";
export const IMPROVE_WORKING = "Improving";
export const IMPROVE_USE = "Use this";
export const IMPROVE_DISMISS = "Dismiss";
export const IMPROVE_NO_CHANGE = "No improvement suggested. Your question is unchanged.";
export const IMPROVE_FAILED = "Could not improve the question. Your question is unchanged.";
export const IMPROVE_EDIT_LABEL = "Suggested question (you can edit it)";

// Coverage page. NEEDS-OWNER: interface words only; the sentence is the API's.
export const COVERAGE_TITLE = "What the dataset covers";
export const COVERAGE_PLACEHOLDER = "Placeholder: the dataset has not been measured yet";
export const COVERAGE_COVERED = "Covered";
export const COVERAGE_EXCLUDED = "Not covered";

// Matters (PRD-v2 O11): the word is the kind label, "Matter" for advocates and "Project"
// for students; it is not a second feature. NEEDS-OWNER: interface words, not legal text.
export const MATTER_WORDS = {
  matter: { one: "Matter", many: "Matters" },
  project: { one: "Project", many: "Projects" },
} as const;
export const MATTERS_NONE = (many: string) => `You have no ${many.toLowerCase()} yet.`;
export const MATTER_UNFILED = "Unfiled";
export const MATTER_NEW_LABEL = (one: string) => `New ${one.toLowerCase()} name`;
export const MATTER_CREATE = "Create";
export const MATTER_RENAME = "Rename";
export const MATTER_SAVE = "Save";
export const MATTER_CANCEL = "Cancel";
export const MATTER_ARCHIVE = "Archive";
export const MATTER_RESTORE = "Restore";
export const MATTER_DELETE = "Delete";
export const MATTER_SHOW_ARCHIVED = "Show archived";
export const MATTER_FILE_UNDER = "File this conversation under";
export const MATTER_CONVERSATIONS = "Conversations";
export const MATTER_CONVERSATIONS_NONE = "No conversations yet.";
// The two things "delete" can mean. The user must pick one: there is no default.
export const MATTER_DELETE_ONLY = (one: string) => `Delete the ${one.toLowerCase()} only, and move its work to unfiled`;
export const MATTER_DELETE_ALL = (one: string) => `Delete the ${one.toLowerCase()} and everything in it`;
export const MATTER_DELETE_ALL_WARNING = "This also permanently deletes its conversations and uploaded files. It cannot be undone."; // NEEDS-OWNER
export const MATTER_DELETE_TITLE = (one: string) => `Delete this ${one.toLowerCase()}?`;
export const MATTER_DELETE_FAILED = "We could not finish deleting. Nothing else was removed and it was kept. Please try again."; // NEEDS-OWNER
export const HISTORY_TITLE = "History and search";
export const HISTORY_SEARCH_PLACEHOLDER = "Search your own saved questions and answers";
export const HISTORY_SEARCH = "Search";
export const HISTORY_RECENT = "Recent conversations";
export const HISTORY_NONE = "Nothing found in your saved work.";
export const NAV_HISTORY = "History";
