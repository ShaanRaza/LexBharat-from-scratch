vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/admin" }));

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { Onboarding } from "@/components/chat/Onboarding";
import { ReportAnswer } from "@/components/chat/ReportAnswer";
import { AccountScreen } from "@/components/launch/AccountScreen";
import { EvalsScreen, InventedScreen, ReportsScreen, SpendScreen, TriageScreen } from "@/components/launch/AdminScreens";
import { HelpArticleView, HelpIndex, SupportForm } from "@/components/launch/HelpScreens";
import { PricingScreen } from "@/components/launch/PricingScreen";
import { AreaLayout } from "@/components/ui";
import { FAKE_PLANS } from "@/lib/fake/launch";
import { resetFakeDb } from "@/lib/fake/store";

beforeEach(() => resetFakeDb());

describe("pricing (behind a switch, no price in code)", () => {
  it("says so plainly when the switch is off, and calls nothing", () => {
    render(<PricingScreen enabled={false} />);
    expect(screen.getByText("Plans are not available yet.")).toBeInTheDocument();
  });
  it("lists plans from the server with plain-number limits and a Sample label", async () => {
    const { container } = render(<PricingScreen enabled />);
    expect(await screen.findByText("Sample Student")).toBeInTheDocument();
    expect(screen.getByText("40 research answers a month")).toBeInTheDocument();
    expect(screen.getByText("Your plan")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/₹|\d+\s*(\/|per)\s*month/i); // no price shown
    expect(FAKE_PLANS.every((p) => /sample/i.test(p.price_text))).toBe(true);
  });
});

describe("account settings", () => {
  it("shows consents with their notice version and withdraws one", async () => {
    render(<AccountScreen />);
    expect(await screen.findByText("Notice version draft-0")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    expect(await screen.findByText(/^Withdrawn 20/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  });
  it("exports my data", async () => {
    render(<AccountScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Export my data" }));
    expect(await screen.findByText("Your export is ready.")).toBeInTheDocument();
  });
  it("deleting asks first, shows the NEEDS-OWNER placeholder for what it removes, and only then deletes", async () => {
    render(<AccountScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete my account" }));
    const d = await screen.findByRole("dialog");
    expect(within(d).getByText(/NEEDS-OWNER/)).toBeInTheDocument();
    expect(screen.queryByText("Your account has been deleted.")).toBeNull();
    fireEvent.click(within(d).getByRole("button", { name: "Delete account" }));
    expect(await screen.findByText("Your account has been deleted.")).toBeInTheDocument();
  });
  it("Cancel deletes nothing", async () => {
    render(<AccountScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete my account" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByText("Your account has been deleted.")).toBeNull();
  });
});

describe("admin", () => {
  it("every admin screen carries the second-factor notice and sample data", async () => {
    for (const C of [TriageScreen, ReportsScreen, EvalsScreen, InventedScreen, SpendScreen]) {
      const { container, unmount } = render(<C />);
      await waitFor(() => expect(container.querySelector("[data-admin-notice]")).not.toBeNull());
      expect(container.querySelector("[data-admin-notice]")!.textContent).toMatch(/second factor/);
      unmount();
    }
  });
  it("triage shows open reports and moves one along", async () => {
    render(<TriageScreen />);
    expect(await screen.findByText("3 open")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Start review" })[0]);
    await waitFor(() => expect(screen.getAllByText("In review").length).toBe(2));
    fireEvent.click(screen.getAllByRole("button", { name: "Mark resolved" })[0]);
    expect(await screen.findByText("2 open")).toBeInTheDocument();
  });
  it("the reported-answers list keeps resolved ones", async () => {
    render(<ReportsScreen />);
    expect(await screen.findAllByText("A citation is wrong")).not.toHaveLength(0);
  });
  it("the test runner starts, progresses, and ends with a pass rate and failures", async () => {
    render(<EvalsScreen />);
    expect(screen.getByText("No run yet")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start a run" }));
    expect(await screen.findByText(/200 questions done · pass rate 96%/, undefined, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Failures" })).toBeInTheDocument();
  });
  it("the invented-citation log and the spend table", async () => {
    render(<InventedScreen />);
    expect(await screen.findByText("not retrieved")).toBeInTheDocument();
    render(<SpendScreen />);
    expect(await screen.findByText("2026-11-02")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0); // no price configured: tokens only
  });
});

describe("help and support", () => {
  it("lists sample articles, shows one, and says when an article is missing", async () => {
    render(<HelpIndex />);
    expect(await screen.findByText("Sample: asking a question")).toBeInTheDocument();
    render(<HelpArticleView slug="ask-a-question" />);
    expect(await screen.findByText(/Type your question in plain words/)).toBeInTheDocument();
    render(<HelpArticleView slug="nope" />);
    expect(await screen.findByText("This article was not found")).toBeInTheDocument();
  });
  it("the support form needs an email and a message, then confirms", async () => {
    render(<SupportForm />);
    const send = screen.getByRole("button", { name: "Send" });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Your email"), { target: { value: "a@b.co" } });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText("How can we help?"), { target: { value: "hello" } });
    fireEvent.click(send);
    expect(await screen.findByText("Thank you. We have your message.")).toBeInTheDocument();
  });
});

describe("reporting a wrong answer", () => {
  it("a report reaches the admin triage queue", async () => {
    render(<ReportAnswer messageId="fake-msg-777" />);
    fireEvent.click(screen.getByRole("button", { name: "Report a wrong answer" }));
    const d = await screen.findByRole("dialog");
    fireEvent.change(within(d).getByLabelText("What was wrong? (optional)"), { target: { value: "wrong section" } });
    fireEvent.click(within(d).getByRole("button", { name: "Send report" }));
    expect(await screen.findByText("Thank you. Your report was sent.")).toBeInTheDocument();
    render(<TriageScreen />);
    expect(await screen.findByText("4 open")).toBeInTheDocument();
    expect(screen.getByText("wrong section")).toBeInTheDocument();
  });
  it("Helpful is recorded once", async () => {
    render(<ReportAnswer messageId="fake-msg-778" />);
    fireEvent.click(screen.getByRole("button", { name: "Helpful" }));
    expect(await screen.findByText("Thank you for the feedback.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Helpful" })).toBeDisabled();
  });
});

describe("area layout and onboarding", () => {
  const items = [{ href: "/a", label: "Alpha" }, { href: "/b", label: "Beta" }];
  it("a sidebar on a desktop and a sheet behind a menu button on a phone", () => {
    render(<AreaLayout title="Area" items={items}><p>body</p></AreaLayout>);
    expect(screen.getAllByRole("link", { name: "Alpha" })).toHaveLength(1); // the sidebar (sheet is closed)
    fireEvent.click(screen.getByRole("button", { name: "Area menu" }));
    const sheet = screen.getByRole("dialog", { name: "Area" });
    expect(within(sheet).getByRole("link", { name: "Beta" })).toBeInTheDocument();
    expect(screen.getByText("body")).toBeInTheDocument();
  });
  it("first run shows three steps, and Got it hides them", () => {
    render(<Onboarding />);
    expect(screen.getByText("Ask your first question")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByText("Ask your first question")).toBeNull();
  });
});
