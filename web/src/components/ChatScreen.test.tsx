import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { copy } from "@/lib/copy";
import { ChatScreen } from "./ChatScreen";

// Whole chat screen on the built-in sample API (no backend).
async function ask(question: string) {
  const { container } = render(<ChatScreen />);
  fireEvent.change(screen.getByLabelText(copy.askLabel), { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  return container;
}

describe("ChatScreen on the fake API", () => {
  it("answers with a tick only on the verified source; notices visible", async () => {
    const container = await ask("Can bail be granted?");
    await waitFor(() => expect(container.querySelectorAll("[data-state]").length).toBeGreaterThan(0), { timeout: 3000 });
    // The sample answer has no inline markers (like the real API), so each of
    // the 3 sources shows once, in its own card.
    const states = [...container.querySelectorAll("[data-state]")].map((n) => n.getAttribute("data-state"));
    expect(states.sort()).toEqual(["partial", "unverified", "verified"]);
    expect(screen.getAllByLabelText(copy.verified)).toHaveLength(1); // S1 only
    expect(screen.getByText(copy.credit)).toBeInTheDocument();
    expect(screen.getByText(copy.notAdvice)).toBeInTheDocument();
    expect(screen.getByText(/Data as of/)).toBeInTheDocument();
    expect(screen.getByText("One authority could not be verified and was removed.")).toBeInTheDocument();
  });

  it.each([
    ["no results unknown topic", "not_found"],
    ["i am over my limit", "usage_limit"],
    ["simulate an outage", "service_error"],
    ["high court bail", "out_of_scope"],
  ])("shows the right failure screen for %s", async (question, kind) => {
    const container = await ask(question);
    await waitFor(() => expect(container.querySelector(`[data-failure="${kind}"]`)).not.toBeNull(), { timeout: 3000 });
    expect(container.querySelectorAll("[data-state]")).toHaveLength(0); // no ticks on failures
  });

  it("when the writer fails, sources show with links but never a tick", async () => {
    const container = await ask("writer fails here");
    await waitFor(() => expect(container.querySelector('[data-failure="provider_failed"]')).not.toBeNull(), { timeout: 3000 });
    expect(screen.queryAllByLabelText(copy.verified)).toHaveLength(0);
    expect(container.querySelectorAll('[data-state="unverified"]').length).toBe(3);
  });
});
