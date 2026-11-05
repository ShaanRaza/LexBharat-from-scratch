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
// NEEDS-OWNER (draft, DESIGN-DIRECTION section 6, not approved). CLAUDE.md section 6 and
// UX-COPY name the label "in-force status not checked"; this draft is the same words as a
// sentence. The owner settles which.
export const IN_FORCE_NOT_CHECKED = "In-force status not checked for this Act.";
export const IN_FORCE_LABEL = "In force";
export const REPEALED_LABEL = "Repealed";

// Shown under an answer-less screen before any result has told us the date of the data.
// Owner-approved 4 Nov 2026 (A148).
export const DATA_DATE_WITH_RESULTS = "The date of the data is shown with every result.";

export const FAILURES = {
  // The search ran and the gate kept nothing. Owner-approved 4 Nov 2026. The live text is
  // not_found_message from GET /coverage (core/coverage.json); this is the fallback if that
  // call fails, and a test keeps the two identical.
  notFound: {
    title: "No matching authority found",
    body: "We could not find an authority in our dataset that answers this. That does not mean none exists \u2014 it means our snapshot does not hold one. Try narrowing to a specific Act or section.",
    hint: "If you know the Act and section, try looking it up directly.",
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
    // NEEDS-OWNER (draft, DESIGN-DIRECTION section 6, not approved). Fallback only: the
    // live text is not_in_dataset_message from GET /coverage. The draft contains "does
    // not exist" inside a negation; O7 said never to say an item does not exist.
    body: "Not in our dataset. That does not mean it does not exist \u2014 it means our snapshot does not hold it.",
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
// NEEDS-OWNER (draft, DESIGN-DIRECTION section 6, not approved). Accuracy flag: files
// deleted before the one that failed stay deleted, so "nothing was removed" is not always
// true. The owner should settle the words.
export const MATTER_DELETE_FAILED = "The matter was kept. One or more files could not be deleted, so nothing was removed.";
export const HISTORY_TITLE = "History and search";
export const HISTORY_SEARCH_PLACEHOLDER = "Search your saved work";
export const HISTORY_SEARCH = "Search";
export const HISTORY_RECENT = "Recent conversations";
export const HISTORY_NONE = "Nothing found in your saved work.";
export const NAV_HISTORY = "History";

// Share a saved answer by link (PRD-v2 O14). NEEDS-OWNER: this is wording about what a
// user is told about their own material and who can read a link.
export const SHARE_LABEL = "Share";
export const SHARE_WORKING = "Creating link";
export const SHARE_LINK_LABEL = "Link to this answer";
export const SHARE_COPY_LINK = "Copy link";
// NEEDS-OWNER (draft, DESIGN-DIRECTION section 6, not approved). The expiry is a separate
// interface line (SHARE_EXPIRES) so the draft sentence stays exactly as written.
export const SHARE_NOTE = "Anyone with this link can read this answer. It does not show your name.";
export const SHARE_EXPIRES = (date: string) => `Expires ${date}`;
export const SHARE_MANAGE_HINT = "You can switch it off under Shared links.";
export const SHARE_FAILED = "We could not create a link. Please try again.";
export const SHARED_TITLE = "Shared answer";
// NEEDS-OWNER (draft, DESIGN-DIRECTION section 6, not approved).
export const SHARED_UNAVAILABLE = "This link is not available. It may have been switched off or expired.";
export const SHARED_LINKS_TITLE = "Shared links";
export const SHARED_LINKS_NONE = "You have not shared any answers.";
export const SHARED_REVOKE = "Switch off";
export const SHARED_REVOKED = "Switched off";
export const SHARED_EXPIRES = (date: string) => `Expires ${date}`;
export const SHARED_MANAGE = "Manage shared links";

// Empty states (interface words only; nothing about the law goes here).
export const EMPTY = {
  stats: { title: "No outcome counts to show yet", hint: "Counts appear here when outcome statistics are switched on." },
  history: { title: "No saved conversations yet", hint: "Ask a question and it is saved here, where you can find it again.", action: { label: "Ask a question", href: "/" } },
  search: { title: "Nothing found in your saved work.", hint: "Try fewer or different words." },
  matters: { title: "", hint: "Create one above to keep related questions together." },
  matterConversations: { title: "No conversations in this yet", hint: "Ask a question and file it here, or move an existing conversation in.", action: { label: "Ask a question", href: "/" } },
  shared: { title: "You have not shared any answers.", hint: "Use Share under a saved answer to make a link. Links you make are listed here, where you can switch them off." },
  coverage: { title: "Coverage has not been listed yet", hint: "This page lists what the dataset holds once it has been measured." },
  chat: { title: "Ask your first question", hint: "Write it the way you would say it. Each source in the answer is checked against the dataset." },
} as const;

// ---- Launch pages (pricing, account, admin, help). Interface words only. Anything about
// the law, advice, consent text, retention, deletion consequences, refunds or tax is the
// owner's and appears below only as a marked NEEDS-OWNER placeholder. ----------------------
export const PRICING_TITLE = "Plans";
export const PRICING_OFF = "Plans are not available yet.";
export const PRICING_CURRENT = "Your plan";
export const ACCOUNT_TITLE = "Account";
export const ACCOUNT_SECTIONS = { plan: "Plan and usage", consents: "Consents", data: "Your data", delete: "Delete account" } as const;
export const CONSENT_VERSION_LABEL = (v: string) => `Notice version ${v}`;
export const CONSENT_GIVEN = (d: string) => `Given ${d}`;
export const CONSENT_WITHDRAW = "Withdraw";
export const CONSENT_WITHDRAWN = (d: string) => `Withdrawn ${d}`;
export const CONSENTS_NONE = { title: "No consents recorded", hint: "A consent is recorded when you sign up." };
export const EXPORT_BUTTON = "Export my data";
export const EXPORT_READY = "Your export is ready.";
export const EXPORT_FAILED = "Export is not available yet.";
export const DELETE_BUTTON = "Delete my account";
export const DELETE_CONFIRM_TITLE = "Delete your account?";
export const DELETE_CONFIRM_BUTTON = "Delete account";
export const DELETE_DONE = "Your account has been deleted.";
export const DELETE_FAILED = "Account deletion is not available yet.";
// NEEDS-OWNER: what deleting an account removes, and what is kept, is a legal statement
// (retention is undecided, docs/RETENTION.md). Shown as a placeholder until the owner writes it.
export const DELETE_CONSEQUENCES = "NEEDS-OWNER: what deleting your account removes and what is kept.";
export const ADMIN_TITLE = "Admin";
export const ADMIN_NOTICE = "Admin pages need a second factor. This screen shows sample data.";
export const ADMIN_SECTIONS = { triage: "Triage", reports: "Reported answers", evals: "Test runner", citations: "Invented citations", spend: "AI spend" } as const;
export const REPORT_REASONS = { citation: "A citation is wrong", answer: "The answer is wrong", missing: "Something is missing", other: "Other" } as const;
export const REPORT_BUTTON = "Report a wrong answer";
export const REPORT_SEND = "Send report";
export const REPORT_THANKS = "Thank you. Your report was sent.";
export const REPORT_FAILED = "We could not send the report. Please try again.";
export const REPORT_EDIT_LABEL = "What was wrong? (optional)";
export const REPORT_REASON_LABEL = "Reason";
export const RATE_UP = "Helpful";
export const RATE_THANKS = "Thank you for the feedback.";
export const HELP_TITLE = "Help";
export const HELP_CONTACT = "Contact support";
export const HELP_NONE = { title: "No help articles yet", hint: "Articles appear here when they are published.", action: { label: "Contact support", href: "/help/contact" } };
export const SUPPORT_EMAIL_LABEL = "Your email";
export const SUPPORT_MESSAGE_LABEL = "How can we help?";
export const SUPPORT_SEND = "Send";
export const SUPPORT_THANKS = "Thank you. We have your message.";
export const SUPPORT_FAILED = "We could not send your message. Please try again.";
export const ONBOARDING_TITLE = "Ask your first question";
export const ONBOARDING_STEPS = [
  "Ask in plain words, the way you would say it.",
  "Read the answer. Each source in it has its own mark.",
  "Click a source to open it beside the answer.",
] as const;
export const ONBOARDING_DISMISS = "Got it";

// ---- Navigation labels: the app sidebar and the public top bar read these ----
export const NAV = {
  newQuestion: "New question",
  history: "History",
  acts: "Acts",
  statistics: "Statistics",
  coverage: "Coverage",
  plans: "Plans",
  help: "Help",
  account: "Account",
  signIn: "Sign in",
  signOut: "Sign out",
  earlyAccess: "Get early access",
  reference: "Reference",
  allMatters: "All",
  menu: "Menu",
  appNav: "App",
  mattersNone: "None yet",
  mattersFailed: "Could not load",
} as const;
