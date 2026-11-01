import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { ChatScreen } from "@/components/chat/ChatScreen";
import { SourcePane } from "@/components/chat/SourcePane";
import { FAKE_CASE, FAKE_CITATIONS, FAKE_SECTIONS } from "@/lib/fake/data";
import type { Citation } from "@/lib/api/types";

const verifiedJudgment: Citation = { ...FAKE_CITATIONS[1], status: "verified" };

describe("source pane (presentational)", () => {
  it("keeps the tick wording, date, credit and notice, and marks the cited paragraph", () => {
    const { container } = render(
      <SourcePane
        citation={verifiedJudgment}
        state={{ status: "case", record: FAKE_CASE }}
        dataAsOf="2026-08-31"
        clicks={1}
        onClose={() => {}}
      />,
    );
    expect(container.querySelector('[data-mark="tick"]')).not.toBeNull();
    expect(screen.getAllByText(/Record found in dataset \(data as of 2026-08-31\)/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Data as of 2026-08-31/)).toBeInTheDocument();
    expect(screen.getByText(/CC BY 4.0/)).toBeInTheDocument();
    expect(screen.getByText(/not legal advice/)).toBeInTheDocument();
    const cited = container.querySelector('[data-cited="true"]');
    expect(cited?.id).toBe("p12");
    expect(container.querySelectorAll('[data-cited="true"]')).toHaveLength(1);
  });

  it("reuses the judgment reader, so it shows no judge or party names", () => {
    const { container } = render(
      <SourcePane citation={verifiedJudgment} state={{ status: "case", record: FAKE_CASE }} dataAsOf="d" clicks={1} onClose={() => {}} />,
    );
    // The reader shows the citation string as recorded, never the party-name title.
    expect(container.textContent).toContain("as recorded in the dataset");
    expect(container.textContent).not.toContain("Sample v. Sample");
  });

  it("shows an Act section with the in-force label when status is unchecked", () => {
    render(
      <SourcePane citation={FAKE_CITATIONS[0]} state={{ status: "section", record: FAKE_SECTIONS[0] }} dataAsOf="d" clicks={1} onClose={() => {}} />,
    );
    expect(screen.getByText("in-force status not checked")).toBeInTheDocument();
  });

  it("stacks on narrow widths: no side-by-side classes below the large breakpoint", () => {
    const { container } = render(
      <SourcePane citation={verifiedJudgment} state={{ status: "loading" }} dataAsOf="d" clicks={1} onClose={() => {}} />,
    );
    // The only column rules are behind the lg: prefix; the pane itself is a plain block.
    expect(container.innerHTML).not.toMatch(/(^|\s)(flex-row|grid-cols-2)\b/);
  });
});

describe("answer with the source beside it", () => {
  async function ask() {
    render(<ChatScreen />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "bail" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(screen.getAllByText("S2").length).toBeGreaterThan(0), { timeout: 3000 });
  }

  it("clicking a judgment citation opens that record and marks the cited paragraph", async () => {
    await ask();
    const chip = screen.getAllByRole("link", { name: /S2/ })[0];
    fireEvent.click(chip);
    const pane = await screen.findByRole("complementary", { name: "Source" });
    await waitFor(() => expect(within(pane).getByText(/Sample paragraph twelve/)).toBeInTheDocument());
    expect(pane.querySelector('[data-cited="true"]')?.id).toBe("p12");
    // The answer is still on screen next to it.
    expect(screen.getByRole("region", { name: "Answer" })).toBeInTheDocument();
  });

  it("clicking an Act citation opens the section and keeps the link as a fallback", async () => {
    await ask();
    const chip = screen.getAllByRole("link", { name: /S1/ })[0];
    expect(chip).toHaveAttribute("href", "/acts/ipc-1860/420");
    fireEvent.click(chip);
    const pane = await screen.findByRole("complementary", { name: "Source" });
    await waitFor(() => expect(within(pane).getByText("in-force status not checked")).toBeInTheDocument());
  });

  it("a modified click is left to the browser (new tab), and Close removes the pane", async () => {
    await ask();
    fireEvent.click(screen.getAllByRole("link", { name: /S2/ })[0], { ctrlKey: true });
    expect(screen.queryByRole("complementary", { name: "Source" })).toBeNull();
    fireEvent.click(screen.getAllByRole("link", { name: /S2/ })[0]);
    await screen.findByRole("complementary", { name: "Source" });
    fireEvent.click(screen.getByRole("button", { name: "Close source" }));
    expect(screen.queryByRole("complementary", { name: "Source" })).toBeNull();
  });
});
