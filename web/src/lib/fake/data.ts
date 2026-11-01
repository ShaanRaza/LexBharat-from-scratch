// Canned data for fake mode. All of it is sample content, labelled "Sample" in the UI.
//
// HOW TO TRIGGER THE REALISTIC CASES (fake mode only). Real law is not tidy, so the layout
// is checked against these, at 1280px and 375px, not only against the three short passages.
//
//   Ask a question containing...                 you get...
//     eight       an answer with the full 8 citations (S1-S8, verified/partly/unchecked,
//                 judgments and Acts, long stored citation string, 200-character Act title)
//     removed     a verifier-removed-a-citation result (removed_count 1, with the note)
//     nothing     the empty result: not found in the dataset
//     notheld     a refusal with its own message: not in our dataset
//     highcourt   the out-of-coverage refusal
//     limit       the usage-limit screen
//     fail        the service-failure screen
//     upload      an answer the server would refuse to share (shaped by an upload)
//     (anything else)  the short 3-citation sample answer
//
//   Open a record id (the answer's chips link to these)...
//     /cases/sc-long-001                    a 48-paragraph judgment (p7 is very long, p13 holds
//                                           an unbroken 150-character address, p4 is one line)
//     /acts/long-title-act-1999/7           an Act with a 200-character title
//     /acts/subclause-act-1999/12           an Act section with nested sub-clauses (a)(i)(A)
//
//   Add ?fake=empty to /stats, /history, /matters, /shared, /coverage to see the empty state.
//   The default fake database has a matter with a very long title and 60 conversations, and a
//   matter with none. Tests use the small database (NEXT_PUBLIC_FAKE_DB=minimal).
import type { CaseOut, Citation, CoverageOut, MeOut, SectionOut, StatsOut, Provenance } from "@/lib/api/types";
import { CC_BY_CREDIT, NOT_LEGAL_ADVICE_API } from "@/lib/copy";
import { LONG_CASE, LONG_CASE_ID, longSections } from "@/lib/fake/fixtures";

import { ANSWER_EIGHT, ANSWER_REMOVED, CITATIONS_EIGHT, CITATIONS_REMOVED } from "@/lib/fake/fixtures";

export { ANSWER_EIGHT, ANSWER_REMOVED, CITATIONS_EIGHT, CITATIONS_REMOVED };

export const FAKE_PROVENANCE: Provenance = {
  data_as_of: "2026-08-31",
  snapshot_version: "v2026.08",
  credit: CC_BY_CREDIT,
  notice: NOT_LEGAL_ADVICE_API,
};

export const FAKE_ANSWER_TEXT =
  "Sample answer. Cheating and dishonestly inducing delivery of property is punished under section 420 of the Indian Penal Code [S1]. The Court discussed the ingredients of the offence in a sample judgment [S2]. A further sample point is not checked [S3].";

export const FAKE_CITATIONS: Citation[] = [
  {
    source_id: "S1", kind: "act", anchor: null, act_slug: "ipc-1860", section: "420",
    record_id: "act-ipc-1860-420", title: "Indian Penal Code, 1860",
    citation_string: null, url: "https://example.invalid/sample/ipc-420", status: "verified",
  },
  {
    source_id: "S2", kind: "judgment", anchor: "p12", act_slug: null, section: null,
    record_id: "sc-sample-001", title: "Sample v. Sample (judgment)",
    citation_string: "(2020) 1 SCC 1", url: "https://example.invalid/sample/sc-001.pdf", status: "partly",
  },
  {
    source_id: "S3", kind: "judgment", anchor: "p13", act_slug: null, section: null,
    record_id: "sc-sample-001", title: "Sample v. Sample (judgment)",
    citation_string: "(2020) 1 SCC 1", url: "https://example.invalid/sample/sc-001.pdf", status: "unchecked",
  },
];

export const FAKE_CASE: CaseOut = {
  record_id: "sc-sample-001",
  title: "Sample v. Sample (judgment)",
  court: "Supreme Court of India",
  decision_date: "2020-01-15",
  case_number: "Sample Appeal No. 1 of 2019",
  citation_string: "(2020) 1 SCC 1",
  url: "https://example.invalid/sample/sc-001.pdf",
  paragraphs: [
    { anchor: "p11", text: "Sample paragraph eleven. This text is placeholder content." },
    { anchor: "p12", text: "Sample paragraph twelve, on the ingredients of the offence." },
    { anchor: "p13", text: "Sample paragraph thirteen. This text is placeholder content." },
  ],
  provenance: FAKE_PROVENANCE,
};

export const FAKE_CASES: Record<string, CaseOut> = {
  [FAKE_CASE.record_id]: FAKE_CASE,
  [LONG_CASE_ID]: { ...LONG_CASE, provenance: FAKE_PROVENANCE },
};

export const FAKE_SECTIONS: SectionOut[] = [
  ...longSections(FAKE_PROVENANCE),
  {
    act_slug: "ipc-1860", act_name: "Indian Penal Code, 1860", act_year: 1860,
    section: "420", section_title: "Cheating and dishonestly inducing delivery of property",
    text: "Sample text of the section. Whoever cheats and thereby dishonestly induces the person deceived to deliver any property...",
    source_url: "https://example.invalid/sample/ipc-420",
    in_force: null, act_status_checked: false, provenance: FAKE_PROVENANCE,
  },
  {
    act_slug: "sample-act-2000", act_name: "Sample Act, 2000", act_year: 2000,
    section: "1", section_title: "Short title",
    text: "Sample text. This Act may be called the Sample Act, 2000.",
    source_url: "https://example.invalid/sample/act-1",
    in_force: true, act_status_checked: true, provenance: FAKE_PROVENANCE,
  },
];

export const FAKE_ME: MeOut = {
  id: "fake-user", email: null, name: null, plan: "free", answers_left_this_month: 3,
};

// Sample counts, labelled "Sample" in the UI. Counts only.
export const FAKE_STATS: StatsOut = {
  live: false,
  provenance: FAKE_PROVENANCE,
  rows: [
    { court: "Supreme Court of India", year: 2020, outcome_label: "Allowed", count: 120 },
    { court: "Supreme Court of India", year: 2020, outcome_label: "Dismissed", count: 340 },
    { court: "Supreme Court of India", year: 2021, outcome_label: "Allowed", count: 95 },
    { court: "Supreme Court of India", year: 2021, outcome_label: "Dismissed", count: 410 },
  ],
};

// Sample coverage in the shape GET /coverage returns (fake mode only; labelled Sample).
export const FAKE_COVERAGE: CoverageOut = {
  status: "placeholder",
  sentence: "Sample coverage sentence: this demo covers its sample records only.",
  sentence_approved: false,
  not_in_dataset_message: "Sample: this is not in our dataset.",
  courts: [{ id: "sample-court", label: "Sample court judgments" }],
  instruments: [{ id: "sample-acts", label: "Sample Acts" }],
  excluded: ["Sample exclusions"],
  measured_at: null,
  provenance: FAKE_PROVENANCE,
};

export const FAKE_STATS_EMPTY: StatsOut = { live: false, provenance: FAKE_PROVENANCE, rows: [] };

// The answer a question gets in fake mode, chosen by keyword (see the trigger list above).
export function fakeAnswerFor(question: string): { text: string; citations: Citation[]; removed: number } {
  const q = question.toLowerCase();
  if (q.includes("eight")) return { text: ANSWER_EIGHT, citations: CITATIONS_EIGHT, removed: 0 };
  if (q.includes("removed")) return { text: ANSWER_REMOVED, citations: CITATIONS_REMOVED, removed: 1 };
  return { text: FAKE_ANSWER_TEXT, citations: FAKE_CITATIONS, removed: 0 };
}
