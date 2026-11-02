import { render, screen } from "@testing-library/react";
import { markFor } from "@/lib/citation";
import { CitationChip } from "@/components/ui";
import { AnswerView } from "@/components/chat/AnswerView";
import { applyEvent, newAnswer } from "@/lib/chat/state";
import { FAKE_PROVENANCE } from "@/lib/fake/data";
import type { Citation } from "@/lib/api/types";

describe("markFor", () => {
  it("ticks only exactly 'verified'", () => {
    expect(markFor("verified")).toBe("tick");
    expect(markFor("partly")).toBe("warning");
    expect(markFor("unchecked")).toBe("unchecked");
    for (const s of ["", "Verified", "supported", "failed", "unverified"]) {
      expect(markFor(s)).toBe("none");
    }
  });
});

describe("CitationChip", () => {
  const base = { label: "S1", dataAsOf: "2026-08-31", href: "https://x.invalid" };
  it("verified shows tick and the dataset wording", () => {
    render(<CitationChip {...base} status="verified" />);
    expect(screen.getByRole("link")).toHaveAttribute("data-mark", "tick");
    expect(screen.getByText(/Record found in dataset/)).toBeInTheDocument();
  });
  it("unchecked shows its label, no tick and no warning", () => {
    render(<CitationChip {...base} status="unchecked" />);
    expect(screen.getByRole("link")).toHaveAttribute("data-mark", "unchecked");
    expect(screen.getByText("Support not checked")).toBeInTheDocument();
    expect(screen.queryByText("✓")).toBeNull();
    expect(screen.queryByText("⚠")).toBeNull();
  });
  it("partly shows a warning, not a tick", () => {
    render(<CitationChip {...base} status="partly" />);
    expect(screen.getByRole("link")).toHaveAttribute("data-mark", "warning");
    expect(screen.queryByText("✓")).toBeNull();
  });
});

describe("a citation whose record has no source link", () => {
  // Some records have no link in the dataset (Supreme Court rows, regulator records).
  // The answer must show the citation string and the tick, and NO external link: never a dead one.
  const citation = (url: string | null): Citation => ({
    source_id: "S1", kind: "judgment", anchor: null, act_slug: null, section: null,
    record_id: "2019_INSC_1235_000", title: null, citation_string: "[2019] 6 S.C.R. 1", url, status: "verified",
  });
  const answer = (url: string | null) => {
    let s = newAnswer("What is bail?");
    s = applyEvent(s, { event: "token", data: { text: "Bail is the rule [S1]." } });
    s = applyEvent(s, { event: "citations", data: { citations: [citation(url)], removed_count: 0, data_as_of: FAKE_PROVENANCE.data_as_of, credit: FAKE_PROVENANCE.credit, notice: FAKE_PROVENANCE.notice } });
    return applyEvent(s, { event: "done", data: { message_id: "m1", from_cache: false, refused: false } });
  };

  it("shows the citation string and the tick, and no Source link", () => {
    render(<AnswerView answer={answer(null)} />);
    expect(screen.getByText(/\[2019\] 6 S\.C\.R\. 1/)).toBeInTheDocument();
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("data-mark", "tick");
    expect(screen.queryByText("Source")).toBeNull();
    for (const a of screen.getAllByRole("link")) expect(a.getAttribute("href")).toMatch(/^\//); // in-app only
  });

  it("an empty url counts as no link", () => {
    render(<AnswerView answer={answer("")} />);
    expect(screen.queryByText("Source")).toBeNull();
  });

  it("with a url the Source link is shown", () => {
    render(<AnswerView answer={answer("https://example.invalid/x.pdf")} />);
    expect(screen.getByText("Source")).toHaveAttribute("href", "https://example.invalid/x.pdf");
  });
});
