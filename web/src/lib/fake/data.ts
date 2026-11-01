// Canned data for fake mode. All of it is sample content, labelled "Sample" in the UI.
import type { CaseOut, Citation, MeOut, SectionOut, StatsOut, Provenance } from "@/lib/api/types";
import { CC_BY_CREDIT, NOT_LEGAL_ADVICE_API } from "@/lib/copy";

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

export const FAKE_SECTIONS: SectionOut[] = [
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
