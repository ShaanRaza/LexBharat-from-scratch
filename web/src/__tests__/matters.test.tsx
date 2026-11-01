vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
const push = vi.fn();

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ChatScreen } from "@/components/chat/ChatScreen";
import { ConversationScreen } from "@/components/matters/ConversationScreen";
import { HistoryScreen } from "@/components/matters/HistoryScreen";
import { MatterScreen } from "@/components/matters/MatterScreen";
import { MattersScreen } from "@/components/matters/MattersScreen";
import { fakeDb, resetFakeDb } from "@/lib/fake/store";
import { defaultKind, wordsFor } from "@/lib/matters/label";

beforeEach(() => {
  resetFakeDb();
  push.mockReset();
});

describe("the label rule (A47): Matter or Project is a label, not a second feature", () => {
  it("a student's new thing is a project; everyone else's is a matter", () => {
    expect(defaultKind("student")).toBe("project");
    for (const r of ["advocate", "in-house", "other", null, undefined]) expect(defaultKind(r)).toBe("matter");
    expect(wordsFor("project")).toEqual({ one: "Project", many: "Projects" });
    expect(wordsFor("matter").one).toBe("Matter");
  });
});

describe("matters list", () => {
  it("lists, creates and opens", async () => {
    render(<MattersScreen />);
    expect(await screen.findByText("Sample matter")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("New matter name"), { target: { value: "Roe v Poe" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByText("Roe v Poe")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Roe v Poe/ })).toHaveAttribute("href", expect.stringMatching(/^\/matters\/fake-matter-/));
  });
  it("does not create an empty one", () => {
    render(<MattersScreen />);
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
  });
  it("archived matters are hidden until asked for", async () => {
    fakeDb.matters[0].status = "archived";
    render(<MattersScreen />);
    expect(await screen.findByText("You have no matters yet.")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Show archived"));
    expect(await screen.findByText("Sample matter")).toBeInTheDocument();
  });
});

describe("one matter", () => {
  it("shows its conversations", async () => {
    render(<MatterScreen id="fake-matter-1" />);
    expect(await screen.findByRole("heading", { name: "Sample matter" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "What is bail?" })).toHaveAttribute("href", "/conversations/fake-conv-1");
  });

  it("renames", async () => {
    render(<MatterScreen id="fake-matter-1" />);
    await screen.findByRole("heading", { name: "Sample matter" });
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    fireEvent.change(screen.getByLabelText("Rename"), { target: { value: "Renamed matter" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("heading", { name: "Renamed matter" })).toBeInTheDocument();
    expect(fakeDb.matters[0].title).toBe("Renamed matter");
  });

  it("archives and restores without deleting anything", async () => {
    render(<MatterScreen id="fake-matter-1" />);
    await screen.findByRole("heading", { name: "Sample matter" });
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(await screen.findByRole("button", { name: "Restore" })).toBeInTheDocument();
    expect(fakeDb.matters[0].status).toBe("archived");
    expect(fakeDb.conversations.filter((c) => c.matter_id === "fake-matter-1")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(fakeDb.matters[0].status).toBe("active"));
  });
});

describe("deleting asks which delete is meant", () => {
  async function openDialog() {
    render(<MatterScreen id="fake-matter-1" />);
    await screen.findByRole("heading", { name: "Sample matter" });
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    return screen.findByRole("dialog");
  }

  it("offers both choices, selects neither, and keeps Delete off until one is chosen", async () => {
    const d = await openDialog();
    const radios = within(d).getAllByRole("radio");
    expect(radios).toHaveLength(2);
    expect(radios.every((r) => !(r as HTMLInputElement).checked)).toBe(true);
    expect(within(d).getByText("Delete the matter only, and move its work to unfiled")).toBeInTheDocument();
    expect(within(d).getByText("Delete the matter and everything in it")).toBeInTheDocument();
    expect(within(d).getByRole("button", { name: "Delete" })).toBeDisabled();
    expect(fakeDb.matters).toHaveLength(1); // nothing happened yet
  });

  it("'matter only' deletes the matter and moves its work to unfiled", async () => {
    const d = await openDialog();
    fireEvent.click(within(d).getByLabelText("Delete the matter only, and move its work to unfiled"));
    fireEvent.click(within(d).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/matters"));
    expect(fakeDb.matters).toHaveLength(0);
    expect(fakeDb.conversations.find((c) => c.id === "fake-conv-1")?.matter_id).toBeNull(); // kept, unfiled
  });

  it("'everything' warns, then deletes the matter and its conversations", async () => {
    const d = await openDialog();
    fireEvent.click(within(d).getByLabelText("Delete the matter and everything in it"));
    expect(within(d).getByText(/permanently deletes/)).toBeInTheDocument();
    fireEvent.click(within(d).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/matters"));
    expect(fakeDb.matters).toHaveLength(0);
    expect(fakeDb.conversations.some((c) => c.id === "fake-conv-1")).toBe(false);
    expect(fakeDb.conversations.some((c) => c.id === "fake-conv-2")).toBe(true); // others untouched
  });

  it("Cancel and Escape change nothing", async () => {
    const d = await openDialog();
    fireEvent.click(within(d).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await screen.findByRole("dialog");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(fakeDb.matters).toHaveLength(1);
  });

  it("if the delete fails the matter is kept and the user is told", async () => {
    const d = await openDialog();
    fakeDb.matters = []; // the server will say not found
    fireEvent.click(within(d).getByLabelText("Delete the matter and everything in it"));
    fireEvent.click(within(d).getByRole("button", { name: "Delete" }));
    expect(await within(d).findByRole("alert")).toHaveTextContent(/The matter was kept/);
    expect(push).not.toHaveBeenCalled();
  });
});

describe("a saved conversation", () => {
  it("shows the stored answer with its ticks and moves between matters", async () => {
    render(<ConversationScreen id="fake-conv-1" />);
    expect((await screen.findAllByRole("heading", { name: "What is bail?" })).length).toBe(2); // title + question
    expect(screen.getAllByText(/Record found in dataset \(data as of 2026-08-31\)/).length).toBeGreaterThan(0);
    const picker = await screen.findByLabelText("File this conversation under");
    fireEvent.change(picker, { target: { value: "" } });
    await waitFor(() => expect(fakeDb.conversations.find((c) => c.id === "fake-conv-1")?.matter_id).toBeNull());
  });
});

describe("history and search", () => {
  it("lists recent conversations, then finds words in saved work", async () => {
    render(<HistoryScreen />);
    expect(await screen.findByRole("link", { name: /What is bail\?/ })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "cheating" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect((await screen.findAllByRole("link")).length).toBeGreaterThan(0);
  });
  it("says so when nothing matches", async () => {
    render(<HistoryScreen />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "zebracrossing" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Nothing found in your saved work.")).toBeInTheDocument();
  });
});

describe("filing from the chat", () => {
  it("a new conversation is created under the chosen matter", async () => {
    render(<ChatScreen />);
    const picker = await screen.findByLabelText("File this conversation under");
    await waitFor(() => expect(within(picker).getAllByRole("option").length).toBeGreaterThan(1));
    fireEvent.change(picker, { target: { value: "fake-matter-1" } });
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "bail" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(fakeDb.conversations[0].matter_id).toBe("fake-matter-1"), { timeout: 3000 });
  });
});
