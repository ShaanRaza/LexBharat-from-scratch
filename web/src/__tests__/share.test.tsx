import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { metadata } from "@/app/s/[token]/page";
import { ChatScreen } from "@/components/chat/ChatScreen";
import { ShareControl } from "@/components/chat/ShareControl";
import { SharedAnswerView } from "@/components/chat/SharedAnswerView";
import { SharedLinksScreen } from "@/components/matters/SharedLinksScreen";
import { ApiError, getShared, shareMessage } from "@/lib/api/client";
import { FAKE_ANSWER_TEXT, FAKE_CITATIONS, FAKE_PROVENANCE } from "@/lib/fake/data";
import { resetFakeDb } from "@/lib/fake/store";
import type { SharedAnswerOut } from "@/lib/api/types";

beforeEach(() => resetFakeDb());

const made = { id: "l1", token: "tok-abc-123", path: "/s/tok-abc-123", expires_at: "2026-12-02T00:00:00Z" };
const forbidden = new ApiError({ code: "forbidden", message: "This answer used your uploaded document, so it cannot be shared.", request_id: "r" }, 403);

describe("the Share control", () => {
  it("shows the link once it exists, with its end date and a way to copy it", async () => {
    const copy = vi.fn().mockResolvedValue(true);
    render(<ShareControl create={async () => made} copy={copy} origin="https://app.example" />);
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    const box = (await screen.findByLabelText("Link to this answer")) as HTMLInputElement;
    expect(box.value).toBe("https://app.example/s/tok-abc-123");
    expect(box).toHaveAttribute("readonly");
    expect(screen.getByText(/Expires 2026-12-02/)).toBeInTheDocument();
    expect(screen.getByText("Anyone with this link can read this answer. It does not show your name.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    expect(await screen.findByText("Copied")).toBeInTheDocument();
    expect(copy).toHaveBeenCalledWith("https://app.example/s/tok-abc-123");
  });

  it("when the server refuses, says why and shows NO link", async () => {
    render(<ShareControl create={async () => Promise.reject(forbidden)} copy={vi.fn()} origin="https://app.example" />);
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("used your uploaded document");
    expect(screen.queryByLabelText("Link to this answer")).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy link" })).toBeNull();
  });

  it("another failure is a plain error, also with no link", async () => {
    render(<ShareControl create={async () => Promise.reject(new Error("boom"))} copy={vi.fn()} origin="" />);
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not create a link");
    expect(screen.queryByLabelText("Link to this answer")).toBeNull();
  });
});

describe("sharing from the chat (fake mode)", () => {
  async function ask(q: string) {
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: q } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Share" })).toBeEnabled(), { timeout: 3000 });
  }

  it("a normal answer can be shared", async () => {
    render(<ChatScreen />);
    await ask("bail");
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    const box = (await screen.findByLabelText("Link to this answer")) as HTMLInputElement;
    expect(box.value).toMatch(/\/s\/fake-token-/);
  });

  it("an answer shaped by an upload is refused and gets no link", async () => {
    render(<ChatScreen />);
    await ask("upload bail");
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("cannot be shared");
    expect(screen.queryByLabelText("Link to this answer")).toBeNull();
  });
});

describe("the public page", () => {
  const shared: SharedAnswerOut = {
    question: "What is bail?",
    text: FAKE_ANSWER_TEXT,
    citations: FAKE_CITATIONS,
    expires_at: "2026-12-02T00:00:00Z",
    provenance: FAKE_PROVENANCE,
  };

  it("shows the answer with per-citation ticks, the date, the credit and the notice", () => {
    const { container } = render(<SharedAnswerView shared={shared} />);
    expect(screen.getByRole("heading", { name: "What is bail?" })).toBeInTheDocument();
    expect(container.querySelector('[data-mark="tick"]')).not.toBeNull();
    expect(container.querySelector('[data-mark="warning"]')).not.toBeNull();
    expect(screen.getAllByText(/Record found in dataset \(data as of 2026-08-31\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Data as of 2026-08-31/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/CC BY 4.0/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not legal advice/).length).toBeGreaterThan(0);
  });

  it("names nobody and offers no way to act on someone else's answer", () => {
    const { container } = render(<SharedAnswerView shared={shared} />);
    for (const b of ["Copy", "Export", "Rewrite", "Share"]) expect(screen.queryByRole("button", { name: b })).toBeNull();
    expect(container.textContent).not.toMatch(/Sample v\. Sample/); // no judgment title (party names)
    expect(container.textContent).not.toMatch(/@/);
  });

  it("every chip opens a public page that lands on the cited passage (decision A71)", () => {
    const { container } = render(<SharedAnswerView shared={shared} />);
    const hrefs = [...container.querySelectorAll("a[data-mark]")].map((a) => a.getAttribute("href") ?? "");
    expect(hrefs.length).toBeGreaterThan(0);
    for (const c of shared.citations) {
      const want = c.kind === "act" ? `/acts/${c.act_slug}/${c.section}` : `/cases/${encodeURIComponent(c.record_id)}${c.anchor ? `#${c.anchor}` : ""}`;
      expect(hrefs).toContain(want);
    }
    expect(hrefs).toContain("/cases/sc-sample-001#p12"); // a judgment chip lands on its paragraph
    expect(hrefs.some((h) => h === "#" || h.startsWith("http"))).toBe(false); // no dead or off-site chip
  });

  it("an unavailable link says so and shows nothing else", () => {
    const { container } = render(<SharedAnswerView shared={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent("This link is not available. It may have been switched off or expired.");
    expect(container.textContent).not.toMatch(/Sample answer/);
  });

  it("is not for search engines, caches or referrers", () => {
    expect(metadata.robots).toMatchObject({ index: false, follow: false, noarchive: true });
    expect(metadata.referrer).toBe("no-referrer");
  });
});

describe("revoking", () => {
  it("lists my links, switches one off, and the public page is gone at once", async () => {
    const link = await shareMessage("fake-msg-1");
    expect(await getShared(link.token)).toMatchObject({ question: "What is bail?" });
    render(<SharedLinksScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Switch off" }));
    expect(await screen.findByText("Switched off")).toBeInTheDocument();
    await expect(getShared(link.token)).rejects.toMatchObject({ status: 404 }); // the very next read
    expect(screen.queryByRole("button", { name: "Switch off" })).toBeNull();
  });
  it("says so when there is nothing shared", async () => {
    render(<SharedLinksScreen />);
    expect(await screen.findByText("You have not shared any answers.")).toBeInTheDocument();
  });
  it("never shows the link address in the list", async () => {
    const link = await shareMessage("fake-msg-2");
    const { container } = render(<SharedLinksScreen />);
    await screen.findByRole("button", { name: "Switch off" });
    expect(container.textContent).not.toContain(link.token);
  });
});
