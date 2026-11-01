// All user-facing wording that carries the trust promise or legal position lives here,
// copied from docs/UX-COPY.md. Do not improvise these strings in components.
// Strings marked NEEDS-OWNER are not quoted in UX-COPY.md; the lead must confirm them.

export const CC_BY_CREDIT = "Data: Open India Law by Vaquill AI, CC BY 4.0";

export const NOT_LEGAL_ADVICE = (productName: string) =>
  `${productName} gives information, not legal advice.`;

export const PERSONAL_ADVICE_OPENER =
  "This tool cannot advise on your own situation. Please consult an advocate."; // NEEDS-OWNER (doc gives the meaning, not the sentence)

export const VERIFICATION_LABEL = "Record found in dataset";
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
  outsideCoverage: {
    title: "Outside what this version covers",
    body: "Version 1 covers Supreme Court judgments and central and state Acts and regulations. It does not include High Courts, district courts, tribunals, or judgments after the snapshot date.",
    hint: "For those, please see the official court website.",
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
