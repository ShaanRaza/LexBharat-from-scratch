import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ChatScreen } from "@/components/chat/ChatScreen";
import { answerToText } from "@/lib/chat/answerText";
import { keepQuestions } from "@/lib/chat/followups";
import { applyEvent, newAnswer } from "@/lib/chat/state";
import { FAKE_CITATIONS, FAKE_PROVENANCE } from "@/lib/fake/data";

const copyText = vi.fn<(t: string) => Promise<boolean>>();
const downloadText = vi.fn<(f: string, t: string) => void>();
vi.mock("@/lib/chat/download", () => ({
  copyText: (t: string) => copyText(t),
  downloadText: (f: string, t: string) => downloadText(f, t),
}));

function finished() {
  let s = newAnswer("What is bail?");
  s = applyEvent(s, { event: "token", data: { text: "Bail is the rule [S1]. A second point [S2]." } });
  s = applyEvent(s, {
    event: "citations",
    data: { citations: FAKE_CITATIONS, removed_count: 1, data_as_of: FAKE_PROVENANCE.data_as_of, credit: FAKE_PROVENANCE.credit, notice: FAKE_PROVENANCE.notice },
  });
  return applyEvent(s, { event: "done", data: { message_id: "m1", from_cache: false, refused: false } });
}

describe("follow-up filter in the browser", () => {
  it("keeps short citation-free questions and drops everything else", () => {
    const out = keepQuestions([
      "What is anticipatory bail?",
      "What does [S1] say?",
      "What does S2 hold?",
      'What does "bail is the rule" mean?',
      "Bail is the rule.",
      "The court held it?",
      "What is bail? What is jail?",
      42,
    ]);
    expect(out).toEqual(["What is anticipatory bail?"]);
    expect(keepQuestions("nope")).toEqual([]);
  });
});

describe("copy / export text", () => {
  it("copies the citation string exactly as recorded, with date, credit and notice", () => {
    const t = answerToText(finished())!;
    expect(t).toContain("(2020) 1 SCC 1 (as recorded in the dataset)");
    expect(t).toContain("Data as of 2026-08-31.");
    expect(t).toContain("Data: Open India Law by Vaquill AI, CC BY 4.0");
    expect(t).toContain("This is legal research, not legal advice.");
    expect(t).toContain("One authority could not be verified and was removed.");
    expect(t).toContain("Support not checked"); // the unchecked citation keeps its label
  });
  it("never includes a case title (party names)", () => {
    expect(answerToText(finished())).not.toContain("Sample v. Sample");
  });
  it("gives nothing for an answer that is not verified yet", () => {
    let s = newAnswer("q");
    s = applyEvent(s, { event: "token", data: { text: "A [S1]" } });
    expect(answerToText(s)).toBeNull(); // no citations event: nothing to copy
  });
});

describe("answer row, follow-ups and the improve helper in the chat", () => {
  async function answered() {
    render(<ChatScreen />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "bail" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copy" })).toBeEnabled(), { timeout: 3000 });
  }

  beforeEach(() => {
    copyText.mockReset().mockResolvedValue(true);
    downloadText.mockReset();
  });

  it("shows the row only after verification and Copy hands over the verified text", async () => {
    render(<ChatScreen />);
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "bail" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    // While the answer streams there is no action row (nothing verified yet).
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
    await waitFor(() => expect(screen.getByRole("button", { name: "Copy" })).toBeEnabled(), { timeout: 3000 });
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(copyText).toHaveBeenCalledTimes(1));
    expect(copyText.mock.calls[0][0]).toContain("(2020) 1 SCC 1 (as recorded in the dataset)");
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("Export downloads the same text", async () => {
    await answered();
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(downloadText).toHaveBeenCalledTimes(1);
    const [file, text] = downloadText.mock.calls[0];
    expect(file).toMatch(/-answer\.txt$/);
    expect(text).toContain("as recorded in the dataset");
  });

  it("Rewrite puts the question back in the box and sends nothing", async () => {
    await answered();
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Rewrite" }));
    expect(screen.getByLabelText("Your question")).toHaveValue("bail");
    expect(screen.getAllByRole("region", { name: "Answer" })).toHaveLength(1);
  });

  it("a follow-up is just another question: clicking one starts a new answer", async () => {
    await answered();
    const q = await screen.findByRole("button", { name: /difference between bail and anticipatory bail/ });
    fireEvent.click(q);
    await waitFor(() => expect(screen.getAllByRole("region", { name: "Answer" })).toHaveLength(2));
    expect(screen.getByRole("heading", { name: /difference between bail/ })).toBeInTheDocument();
  });

  it("Improve my question returns editable text and sends nothing until Ask", async () => {
    render(<ChatScreen />);
    const improve = screen.getByRole("button", { name: "Improve my question" });
    expect(improve).toBeDisabled(); // nothing typed yet
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "bail cheque bounce" } });
    fireEvent.click(screen.getByRole("button", { name: "Improve my question" }));
    const box = await screen.findByLabelText("Suggested question (you can edit it)");
    expect((box as HTMLTextAreaElement).value).toContain("bail cheque bounce");
    expect((box as HTMLTextAreaElement).value).not.toMatch(/\[S\d\]/);
    fireEvent.change(box, { target: { value: "Can bail be refused in a cheque dishonour case?" } });
    fireEvent.click(screen.getByRole("button", { name: "Use this" }));
    expect(screen.getByLabelText("Your question")).toHaveValue("Can bail be refused in a cheque dishonour case?");
    expect(screen.queryByRole("region", { name: "Answer" })).toBeNull(); // nothing was sent
    expect(screen.queryByLabelText("Suggested question (you can edit it)")).toBeNull();
  });

  it("dismissing the suggestion leaves the user's own text alone", async () => {
    render(<ChatScreen />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "my rough question" } });
    fireEvent.click(screen.getByRole("button", { name: "Improve my question" }));
    await screen.findByLabelText("Suggested question (you can edit it)");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.getByLabelText("Your question")).toHaveValue("my rough question");
  });
});
