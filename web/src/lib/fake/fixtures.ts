// Realistic sample fixtures for fake mode. Real law is not tidy: these exist so a layout is
// judged against long judgments, eight citations, a 200-character Act title and long stored
// citation strings, not against three short sentences. All of it is SAMPLE content. It names
// no judge, party or advocate and carries no price. See the trigger list in data.ts.
import type { CaseOut, Citation, Provenance, SectionOut } from "@/lib/api/types";

const POOL = [
  "The statutory test is applied to the facts as they appear on the record, not as they are later described.",
  "It is settled that the burden lies on the party who asserts the existence of the fact in issue.",
  "The provision must be read as a whole, and no word in it can be treated as surplus without reason.",
  "Where two constructions are open, the one that avoids an absurd result is to be preferred.",
  "The order under challenge does not disclose the reasons that led to the conclusion reached.",
  "A finding of fact recorded after appreciating the evidence is not lightly interfered with.",
  "The question that arises for decision is narrow, and it is answered by the text of the section itself.",
  "Delay, by itself, does not defeat a claim unless it has caused real prejudice to the other side.",
  "The material placed before the court must be considered together and not in isolated fragments.",
  "For these reasons the earlier view cannot be sustained and the matter must be considered afresh.",
  "Nothing in this discussion should be taken to express an opinion on any matter not before the court.",
  "The record shows that the notice was issued, served and acknowledged within the time allowed.",
];

const LONG_URL =
  "https://example.invalid/sample/records/very/long/path/with/many/segments/and/no/spaces/at/all/to/test/wrapping/0123456789/abcdefghijklmnopqrstuvwxyz";

function sentences(n: number, seed: number): string {
  return Array.from({ length: n }, (_, i) => POOL[(seed + i * 5) % POOL.length]).join(" ");
}

const SIZES = [2, 5, 3, 1, 8, 4, 40, 2, 6, 3, 1, 9, 3, 5, 2, 7, 4, 1, 3, 6];

/** A 48-paragraph judgment: varied lengths, one very long paragraph (p7), one with an
 *  unbroken 150-character address (p13), one very short (p4). */
export const LONG_CASE_ID = "sc-long-001";
export const LONG_CITATION_STRING =
  "(2020) 14 SCC 1 : 2020 SCC OnLine SC 1234 : AIR 2020 SC 4321 : [2020] 9 S.C.R. 1 (long stored citation string, as in the sample record)";

export const LONG_CASE: CaseOut = {
  record_id: LONG_CASE_ID,
  title: "Sample long judgment",
  court: "Supreme Court of India",
  decision_date: "2020-03-09",
  case_number: "Sample Civil Appeal Nos. 1234-1240 of 2018 with Sample Special Leave Petition (Civil) Nos. 5678 of 2018 and connected matters",
  citation_string: LONG_CITATION_STRING,
  url: LONG_URL + ".pdf",
  paragraphs: Array.from({ length: 48 }, (_, i) => {
    const n = i + 1;
    let text = sentences(SIZES[i % SIZES.length], i);
    if (n === 13) text = `See ${LONG_URL} and the records listed there. ${text}`;
    return { anchor: `p${n}`, text };
  }),
  provenance: undefined as unknown as Provenance, // filled in by data.ts
};

const ACT_TITLE_200 =
  "The Sample Statute for the Regulation, Administration, Supervision, Inspection, Registration and Periodic Review of Illustrative Institutions and Connected Matters, Together with Transitional Provisions, 1999";

export const LONG_ACT = { slug: "long-title-act-1999", title: ACT_TITLE_200 };
export const SUBCLAUSE_ACT = { slug: "subclause-act-1999", title: "The Sample Provisions Act, 1999" };

export function longSections(provenance: Provenance): SectionOut[] {
  return [
    {
      act_slug: LONG_ACT.slug, act_name: ACT_TITLE_200, act_year: 1999, section: "7",
      section_title: "Registration of institutions, renewal of registration, and the conditions on which registration may be refused, suspended or cancelled",
      text: sentences(14, 3),
      source_url: LONG_URL, in_force: null, act_status_checked: false, provenance,
    },
    {
      act_slug: SUBCLAUSE_ACT.slug, act_name: SUBCLAUSE_ACT.title, act_year: 1999, section: "12",
      section_title: "Powers and conditions",
      text: [
        "(1) Subject to the provisions of this section, the competent authority may, by order in writing:",
        "    (a) require any person to furnish such information as it considers necessary, being information relating to:",
        "        (i) the constitution of the institution, including:",
        "            (A) its governing document and every amendment to it;",
        "            (B) the names of its office holders and the date of each appointment; and",
        "        (ii) the accounts of the institution for the preceding three years;",
        "    (b) inspect any record, register or document kept by the institution; and",
        "    (c) give such directions as it thinks fit for securing compliance with this Act.",
        "(2) No order under sub-section (1) shall be made unless the person concerned has been given a reasonable opportunity of being heard.",
        "(3) Nothing in sub-section (1) affects any other power conferred by this Act.",
      ].join("\n"),
      source_url: LONG_URL, in_force: true, act_status_checked: true, provenance,
    },
  ];
}

export const ANSWER_EIGHT =
  "Sample answer with eight sources. The first point concerns the offence of cheating under the Indian Penal Code [S1]. " +
  "The Court set out the ingredients in a long judgment [S2], and later dealt with the effect of a notice [S3].\n\n" +
  "A second line of reasoning concerns the earlier sample view [S4]. The statute with the very long title applies to institutions of the kind described [S5], " +
  "and its sub-clauses set conditions in turn [S6].\n\n" +
  "Two further passages deal with delay [S7] and with how a stored citation is shown [S8]. Each point above carries its own source, and each source carries its own mark.";

function cite(c: Partial<Citation> & Pick<Citation, "source_id" | "status">): Citation {
  return {
    kind: "judgment", anchor: null, act_slug: null, section: null,
    record_id: LONG_CASE_ID, title: null, citation_string: LONG_CITATION_STRING,
    url: LONG_URL + ".pdf", ...c,
  };
}

/** Eight citations: mixed verified / partly / unchecked, mixed judgments and Acts. */
export const CITATIONS_EIGHT: Citation[] = [
  cite({ source_id: "S1", kind: "act", act_slug: "ipc-1860", section: "420", record_id: "act-ipc-1860-420", title: "Indian Penal Code, 1860", citation_string: null, url: "https://example.invalid/sample/ipc-420", status: "verified" }),
  cite({ source_id: "S2", anchor: "p7", status: "verified" }),
  cite({ source_id: "S3", anchor: "p13", status: "partly" }),
  cite({ source_id: "S4", record_id: "sc-sample-001", anchor: "p12", citation_string: "(2020) 1 SCC 1", url: "https://example.invalid/sample/sc-001.pdf", status: "verified" }),
  cite({ source_id: "S5", kind: "act", act_slug: LONG_ACT.slug, section: "7", record_id: "act-long-7", title: ACT_TITLE_200, citation_string: null, url: LONG_URL, status: "unchecked" }),
  cite({ source_id: "S6", kind: "act", act_slug: SUBCLAUSE_ACT.slug, section: "12", record_id: "act-sub-12", title: SUBCLAUSE_ACT.title, citation_string: null, url: LONG_URL, status: "verified" }),
  cite({ source_id: "S7", anchor: "p41", status: "partly" }),
  cite({ source_id: "S8", anchor: "p48", status: "unchecked" }),
];

export const ANSWER_REMOVED =
  "Sample answer where one authority failed its check. The first point stands on a record that exists [S1]. A second point relied on a source that could not be verified [S2]. A third point is supported [S3].";

/** The verifier removed S2: only S1 and S3 reach the client, and removed_count says so. */
export const CITATIONS_REMOVED: Citation[] = [CITATIONS_EIGHT[1], CITATIONS_EIGHT[3]].map((c, i) => ({
  ...c,
  source_id: i === 0 ? "S1" : "S3",
}));

// ---- the matter / conversation fixtures (used by store.ts) ---------------------------
export const LONG_MATTER_TITLE =
  "Sample very long matter title that runs on well past any sensible width, with an unbroken token " +
  "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 and then more words after it to see what happens";

export const CONVERSATION_TITLES = Array.from({ length: 60 }, (_, i) => {
  const base = [
    "What is the position on delay in filing?",
    "Ingredients of the offence of cheating",
    "How is a stored citation shown?",
    "Whether a notice served by post is good service",
    "Limitation for a cheque notice",
  ];
  const t = base[i % base.length];
  return i % 7 === 0 ? `${t} (and a very long follow-on question about related provisions, their sub-clauses and how they interact in practice)` : `${t} #${i + 1}`;
});
