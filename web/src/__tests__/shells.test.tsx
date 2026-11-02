const push = vi.fn();
let pathname = "/";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }), usePathname: () => pathname }));

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { AppShell, PageShell, PublicShell } from "@/components/ui";
import { fakeDb, resetFakeDb } from "@/lib/fake/store";

beforeEach(() => {
  resetFakeDb();
  push.mockClear();
  pathname = "/";
});

describe("the app shell (signed in)", () => {
  it("lists the sidebar top to bottom, with the matters list under Matters", async () => {
    render(<AppShell>page</AppShell>);
    const nav = screen.getAllByRole("navigation", { name: "App" })[0];
    const labels = within(nav)
      .getAllByRole("link")
      .map((a) => a.textContent);
    const first = (t: string) => labels.indexOf(t);
    expect(first("New question")).toBeGreaterThan(-1);
    expect(first("New question")).toBeLessThan(first("Matters"));
    expect(first("Matters")).toBeLessThan(first("History"));
    expect(first("History")).toBeLessThan(first("Acts"));
    expect(first("Acts")).toBeLessThan(first("Statistics"));
    expect(first("Statistics")).toBeLessThan(first("Coverage"));
    expect(first("Coverage")).toBeLessThan(first("Help"));
    expect(first("Help")).toBeLessThan(first("Account"));
    expect(within(nav).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    const m = fakeDb.matters[0];
    if (m) expect(await within(nav).findByRole("link", { name: m.title })).toHaveAttribute("href", `/matters/${m.id}`);
  });

  it("never shows the early-access button beside a signed-in list", () => {
    render(<AppShell>page</AppShell>);
    expect(screen.queryByText("Get early access")).toBeNull();
  });

  it("marks the current page", () => {
    pathname = "/history";
    render(<AppShell>page</AppShell>);
    const nav = screen.getAllByRole("navigation", { name: "App" })[0];
    expect(within(nav).getByRole("link", { name: "History" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Acts" })).not.toHaveAttribute("aria-current");
  });

  it("on a phone the same sidebar opens in a Menu sheet", () => {
    render(<AppShell>page</AppShell>);
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    const sheet = screen.getByRole("dialog", { name: "Menu" });
    for (const t of ["New question", "Matters", "History", "Acts", "Statistics", "Coverage", "Help", "Account"]) {
      expect(within(sheet).getByRole("link", { name: t })).toBeInTheDocument();
    }
    expect(within(sheet).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("sign out goes to the sign-in page in fake mode", async () => {
    render(<AppShell>page</AppShell>);
    fireEvent.click(within(screen.getAllByRole("navigation", { name: "App" })[0]).getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/signin"));
  });
});

describe("the public shell (logged out, search engines)", () => {
  it("has no sidebar, no matters, and does have early access", () => {
    render(<PublicShell>page</PublicShell>);
    expect(screen.queryByRole("navigation", { name: "App" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Matters" })).toBeNull();
    expect(screen.getAllByRole("link", { name: "Get early access" }).length).toBeGreaterThan(0);
  });
});

describe("PageShell must be told which shell", () => {
  it("picks the frame from the prop", () => {
    const a = render(
      <PageShell shell="app">x</PageShell>,
    );
    expect(screen.getAllByRole("navigation", { name: "App" }).length).toBeGreaterThan(0);
    a.unmount();
    render(<PageShell shell="public">x</PageShell>);
    expect(screen.queryByRole("navigation", { name: "App" })).toBeNull();
  });
});
