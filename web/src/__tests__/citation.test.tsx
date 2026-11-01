import { render, screen } from "@testing-library/react";
import { markFor } from "@/lib/citation";
import { CitationChip } from "@/components/ui";

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
