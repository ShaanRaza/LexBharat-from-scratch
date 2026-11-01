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
    { anchor: "p1", text: "Sample text. This paragraph introduces the question the court was asked to decide." },
    { anchor: "p2", text: "Sample text. The court sets out the facts in short, plain words so the screen has something to show." },
    { anchor: "p3", text: "Sample text. The court notes the arguments made on each side of the appeal." },
    { anchor: "p4", text: "Sample text. The court explains the rule it applies and why." },
    { anchor: "p5", text: "Sample text. In this sample paragraph the court says bail is the rule and refusal is the exception." },
    { anchor: "p6", text: "Sample text. The court applies the rule to the facts and gives its reasons." },
    { anchor: "p7", text: "Sample text. The appeal is disposed of in the terms above." },
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
    title: "Sample Case One (illustrative judgment)",
    citation_string: "[2019] Sample SCR 100",
    url: "https://example.org/sample-case-1.pdf",
    status: "verified",
    status_label: "Record found in dataset",
    kind: "judgment",
    anchor: "p5",
    act_slug: null,
    section: null,
    act_status: null,
  },
  {
    source_id: "S2",
    record_id: "sample-act-section",
    title: "Sample Act, section 1",
    citation_string: null,
    url: "https://example.org/sample-act/1",
    status: "partly",
    status_label: "Supports this only in part",
    kind: "act",
    anchor: null,
    act_slug: "sample-act",
    section: "1",
    act_status: null,
  },
  {
    source_id: "S3",
    record_id: "sample-case-2",
    title: "Sample Case Two (illustrative judgment)",
    citation_string: null,
    url: null,
    status: "unverified",
    status_label: null,
    kind: "judgment",
    anchor: null,
    act_slug: null,
    section: null,
    act_status: null,
  },
];

export const sampleAnswer =
  "Sample answer. In the sample judgment the court treats bail as the general rule. The sample Act section covers part of this question. A third source was found but could not be fully checked.";
