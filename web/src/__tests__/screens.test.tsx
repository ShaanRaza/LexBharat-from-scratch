vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { ActLookup } from "@/components/records/ActLookup";
import { StatsView } from "@/components/records/StatsView";
import { SignInForm } from "@/components/auth/SignInForm";
import { TopBar } from "@/components/ui";
import { FailureCard } from "@/components/chat/FailureCard";
import { AnswerView } from "@/components/chat/AnswerView";
import { applyEvent, newAnswer } from "@/lib/chat/state";
import { FAKE_CITATIONS, FAKE_PROVENANCE, FAKE_STATS } from "@/lib/fake/data";
import { FAILURES } from "@/lib/copy";
import { canSignIn } from "@/lib/auth/consent";
import { getMe, getStats, sampleSections } from "@/lib/api/client";

describe("stats page", () => {
  it("shows counts with date, credit and notice, labelled Sample when not live", () => {
    render(<StatsView stats={FAKE_STATS} />);
    expect(screen.getByText("Sample")).toBeInTheDocument();
    expect(screen.getByText("340")).toBeInTheDocument();
    expect(screen.getByText(/Data as of 2026-08-31/)).toBeInTheDocument();
    expect(screen.getByText(/CC BY 4.0/)).toBeInTheDocument();
    expect(screen.getByText(/do not predict/)).toBeInTheDocument();
  });
  it("never shows a percentage, chance or prediction word", () => {
    const { container } = render(<StatsView stats={FAKE_STATS} />);
    expect(container.textContent).not.toMatch(/%|chance|likely|probab|win rate/i);
  });
  it("shows the service-down card when the call failed", () => {
    render(<StatsView stats={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent(FAILURES.serviceError.title);
  });
  it("reads through the client in fake mode", async () => {
    expect((await getStats()).rows.length).toBeGreaterThan(0);
    expect((await getMe()).answers_left_this_month).toBe(3);
  });
});

describe("act lookup", () => {
  it("lists samples only when given (fake mode)", () => {
    expect(sampleSections().length).toBeGreaterThan(0);
    render(<ActLookup samples={[]} />);
    expect(screen.queryByText("Sample")).toBeNull();
  });
  it("lookup button needs both fields", () => {
    render(<ActLookup samples={[]} />);
    expect(screen.getByRole("button", { name: "Look up" })).toBeDisabled();
  });
});

describe("sign in", () => {
  it("needs a plausible email and a password", () => {
    expect(canSignIn("a@b.co", "x")).toBe(true);
    expect(canSignIn("a@b.co", "")).toBe(false);
    expect(canSignIn("nope", "x")).toBe(false);
  });
  it("signs in in fake mode", async () => {
    render(<SignInForm />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(screen.getByText("You are signed in.")).toBeInTheDocument());
  });
});

describe("navigation", () => {
  const PUBLIC = ["Acts", "Statistics", "Coverage", "Help", "Sign in", "Get early access"];
  it("the public bar has every public link, and on a phone all of them sit behind one Menu button", () => {
    render(<TopBar />);
    for (const t of PUBLIC) {
      expect(screen.getAllByRole("link", { name: t }).length).toBeGreaterThan(0); // the desktop bar
    }
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    const sheet = screen.getByRole("dialog", { name: "Menu" });
    for (const t of PUBLIC) {
      expect(within(sheet).getByRole("link", { name: t })).toBeInTheDocument(); // the same list in the sheet
    }
  });
  it("the public bar carries nothing personal: no matters, history or account", () => {
    render(<TopBar />);
    for (const t of ["Matters", "Projects", "History", "Account", "New question"]) {
      expect(screen.queryByRole("link", { name: t })).toBeNull();
    }
  });
});

describe("failure screens use the exact copy", () => {
  it.each(["notFound", "outsideCoverage", "notInDataset", "usageLimit", "serviceError"] as const)("%s", (k) => {
    render(<FailureCard kind={k} />);
    expect(screen.getByRole("alert")).toHaveTextContent(FAILURES[k].body);
  });
  it("UX-COPY sentences are verbatim", () => {
    expect(FAILURES.notFound.body).toBe("No matching judgments found in our dataset (data as of the snapshot date).");
  });
});

describe("citations: visible meaning per citation, one event", () => {
  const answered = () => {
    let s = newAnswer("q");
    s = applyEvent(s, { event: "token", data: { text: "A [S1] B [S2] C [S3]." } });
    s = applyEvent(s, {
      event: "citations",
      data: { citations: FAKE_CITATIONS, removed_count: 0, data_as_of: FAKE_PROVENANCE.data_as_of, credit: FAKE_PROVENANCE.credit, notice: FAKE_PROVENANCE.notice },
    });
    return applyEvent(s, { event: "done", data: { message_id: null, from_cache: false, refused: false } });
  };
  it("prints the meaning next to each mark, tick only on verified", () => {
    const { container } = render(<AnswerView answer={answered()} />);
    expect(screen.getAllByText(/Record found in dataset \(data as of 2026-08-31\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Support not checked").length).toBeGreaterThan(0);
    expect(container.querySelectorAll('[data-mark="tick"]').length).toBe(2); // S1 inline + S1 list
    expect(container.querySelectorAll('[data-mark="unchecked"]').length).toBe(2);
  });
});
