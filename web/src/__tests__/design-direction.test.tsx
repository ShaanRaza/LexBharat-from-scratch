import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CitationChip } from "@/components/ui/CitationChip";

const tokens = readFileSync(join(__dirname, "../design/tokens.css"), "utf8");
const css = (name: string) => new RegExp(`--${name}:\\s*([^;]+);`).exec(tokens)?.[1].trim();

describe("tokens follow docs/DESIGN-DIRECTION.md (a draft the owner reacts to)", () => {
  it("has the section 3 palette", () => {
    expect(css("color-bg")).toBe("#fafaf9");
    expect(css("color-surface")).toBe("#ffffff");
    expect(css("color-text")).toBe("#1c1917");
    expect(css("color-text-muted")).toBe("#57534e");
    expect(css("color-border")).toBe("#e7e5e4");
    expect(css("color-accent")).toBe("#1e3a5f");
    expect(css("color-warn")).toBe("#92400e");
  });
  it("the verification tick is NOT green: it is the muted text colour", () => {
    expect(css("color-verified")).toBe("var(--color-text-muted)");
    expect(css("color-verified-bg")).toBe("var(--color-surface)");
  });
  it("names serif for headings, a Devanagari sibling in both stacks, a 68ch measure, 150ms motion", () => {
    expect(css("font-serif")).toMatch(/noto-serif/);
    expect(css("font-serif")).toMatch(/deva/);
    expect(css("font-sans")).toMatch(/inter/);
    expect(css("font-sans")).toMatch(/deva/);
    expect(css("container-measure")).toBe("68ch");
    expect(css("motion-step")).toBe("150ms");
    expect(css("spacing")).toBe("0.25rem"); // the 4px base
    expect(css("text-body--line-height")).toBe("1.6");
  });
  it("motion is switched off for reduced-motion users", () => {
    const g = readFileSync(join(__dirname, "../app/globals.css"), "utf8");
    expect(g).toMatch(/prefers-reduced-motion: no-preference[\s\S]*\.step-enter/);
  });
});

describe("the tick is text-led and neutral", () => {
  it("a verified chip carries an outline mark (an svg), the words, and no green", () => {
    const { container } = render(<CitationChip label="S1" status="verified" dataAsOf="2026-08-31" href="/x" />);
    const a = container.querySelector("a")!;
    expect(a.querySelector("svg")).not.toBeNull();
    expect(a.textContent).toContain("Record found in dataset (data as of 2026-08-31)");
    expect(a.className).not.toMatch(/green|emerald|verified-bg/);
    expect(a.className).toMatch(/text-text-muted/);
  });
  it("partly and unchecked differ by mark and words, and neither uses an alarm colour for unchecked", () => {
    const p = render(<CitationChip label="S2" status="partly" dataAsOf="d" href="/x" />).container;
    expect(p.textContent).toContain("Supports only partly");
    const u = render(<CitationChip label="S3" status="unchecked" dataAsOf="d" href="/x" />).container;
    expect(u.textContent).toContain("Support not checked");
    expect(u.querySelector("a")!.className).not.toMatch(/warn|danger/);
  });
  it("no unicode glyph stands in for the marks", () => {
    const { container } = render(<CitationChip label="S1" status="verified" dataAsOf="d" href="/x" />);
    expect(container.textContent).not.toMatch(/[✓⚠?]/);
  });
});
