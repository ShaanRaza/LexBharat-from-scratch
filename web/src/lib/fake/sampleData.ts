// Sample data for fake mode. EVERYTHING here is invented for screens and tests
// and is labelled "Sample" in the UI. None of it is real law or a real case.
// No judge or party names (CLAUDE.md section 6).
import type { ActSection, CaseRecord, Citation } from "../types";

export const SAMPLE_DATA_AS_OF = "2026-08-31"; // placeholder, not the real snapshot date

export const sampleCase: CaseRecord = {
  record_id: "sample-case-1",
  title: "Sample Case One (illustrative judgment)",
  court: "Supreme Court of India (sample)",
  decision_date: "2019-03-14",
  case_number: "Sample Appeal No. 1 of 2019",
  citation_string: "[2019] Sample SCR 100",
  pdf_url: "https://example.org/sample-case-1.pdf",
  data_as_of: SAMPLE_DATA_AS_OF,
  paragraphs: [
    { n: 1, text: "Sample text. This paragraph introduces the question the court was asked to decide." },
    { n: 2, text: "Sample text. The court sets out the facts in short, plain words so the screen has something to show." },
    { n: 3, text: "Sample text. The court notes the arguments made on each side of the appeal." },
    { n: 4, text: "Sample text. The court explains the rule it applies and why." },
    { n: 5, text: "Sample text. In this sample paragraph the court says bail is the rule and refusal is the exception." },
    { n: 6, text: "Sample text. The court applies the rule to the facts and gives its reasons." },
    { n: 7, text: "Sample text. The appeal is disposed of in the terms above." },
  ],
};

export const sampleSection: ActSection = {
  act_name: "Sample Act",
  act_slug: "sample-act",
  act_year: 2023,
  section_number: "1",
  section_title: "Sample section title",
  text: "Sample text. This is placeholder wording and is not the official text of any Act. In a real result this box holds the section text exactly as stored in the dataset.",
  act_status: null,
  source_url: "https://example.org/sample-act/1",
  data_as_of: SAMPLE_DATA_AS_OF,
};

// A second section that HAS an in-force status, to show the other label.
export const sampleSectionWithStatus: ActSection = {
  ...sampleSection,
  act_slug: "sample-act-with-status",
  act_name: "Sample Act With Status",
  act_status: "In force (sample)",
};

/** Three citations in three states: ticked, warning, and NOT verified. */
export const sampleCitations: Citation[] = [
  {
    source_id: "S1",
    record_id: "sample-case-1",
    kind: "judgment",
    title: "Sample Case One (illustrative judgment)",
    citation_string: "[2019] Sample SCR 100",
    link: "https://example.org/sample-case-1.pdf",
    paragraph: 5,
    act_slug: null,
    section: null,
    act_status: null,
    excerpt: "Sample text. In this sample paragraph the court says bail is the rule and refusal is the exception.",
    verified: true,
    support: "supports",
  },
  {
    source_id: "S2",
    record_id: "sample-act-section",
    kind: "act",
    title: "Sample Act, section 1",
    citation_string: null,
    link: "https://example.org/sample-act/1",
    paragraph: null,
    act_slug: "sample-act",
    section: "1",
    act_status: null,
    excerpt: "Sample text. This is placeholder wording and is not the official text of any Act.",
    verified: true,
    support: "partly",
  },
  {
    source_id: "S3",
    record_id: "sample-case-2",
    kind: "judgment",
    title: "Sample Case Two (illustrative judgment)",
    citation_string: null,
    link: null,
    paragraph: null,
    act_slug: null,
    section: null,
    act_status: null,
    excerpt: null,
    verified: false,
    support: null,
  },
];

export const sampleAnswer =
  "Sample answer. In the sample judgment the court treats bail as the general rule [S1]. The sample Act section covers part of this question [S2]. A third source was found but could not be fully checked [S3].";
