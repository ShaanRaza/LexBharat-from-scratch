// User-facing wording in ONE place. The strings come from docs/UX-COPY.md and
// carry the trust promise and legal position - change them deliberately,
// never improvise them inside a component.
import { config } from "./config";

export const copy = {
  /** Standing notices (UX-COPY.md "Standing notices"). */
  notAdvice: `${config.productName} gives information, not legal advice.`,
  credit: "Data: Open India Law by Vaquill AI, CC BY 4.0",
  inForceUnchecked: "in-force status not checked",

  /** The verification badge (UX-COPY.md). */
  verified: "Record found in dataset",
  partly: "Partly supported",
  notVerified: "Not verified",
  citationAsRecorded: "as recorded in the dataset",
  removedNote:
    "One authority could not be verified and was removed from this answer.",

  /** Failure states (UX-COPY.md "Failure and edge states"). */
  notFound: {
    title: "No matching judgments found",
    body: "No matching judgments found in our dataset (data as of the snapshot date). No answer was written, so nothing has been invented.",
    tips: [
      "Try rephrasing your question in plainer words.",
      "Use Act and section lookup if you know the section.",
    ],
  },
  outOfScope: {
    title: "Outside what this version covers",
    body: "Version 1 covers Supreme Court judgments and central and state Acts and regulations. It does not include High Courts, district courts, tribunals, or judgments after the snapshot date.",
    tips: ["For those, please check the official court website."],
  },
  serviceError: {
    title: "Something went wrong on our side",
    body: "We could not complete this request. Nothing was guessed. Please try again.",
  },
  // Draft wording for "the LLM provider fails": UX-COPY only describes the
  // behaviour (sources with links, no written answer, retry). Confirm wording.
  providerFailed: {
    title: "We could not write an answer",
    body: "The sources we found are listed below with links, but no written answer is available right now. You can try again.",
  },
  usageLimit: {
    title: "You have reached your monthly limit",
    body: "You have used all your research answers for this month. Act and section lookup stays free.",
  },
  retry: "Try again",

  /** Chat screen. */
  searching: "Searching courts and Acts",
  checking: "Checking each source",
  askPlaceholder: "Ask a legal question in plain words",
  askLabel: "Your question",
  examples: [
    "What is the punishment for cheating under the Bharatiya Nyaya Sanhita?",
    "Can bail be granted in economic offences?",
    "What does section 138 of the Negotiable Instruments Act cover?",
  ],
  sample: "Sample",
} as const;

/** Consent shown at sign-up. The real, counsel-reviewed text does not exist
 *  yet (legal/consent-notice-v1.md is "Not written"). This is a labelled
 *  placeholder - do not ship it. */
export const consent = {
  noticeVersion: "v1-pending",
  purpose: "research_account",
  title: "Consent notice",
  placeholder:
    "Placeholder: the consent notice (purpose, data collected, retention, how to withdraw) is still being written and reviewed by counsel. This text must be replaced before launch.",
  checkbox: "I have read the consent notice and agree.",
} as const;
