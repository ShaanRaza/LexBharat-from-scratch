import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { applyEvent, newAnswer, toSegments, failureFor } from "@/lib/chat/state";
import { createSseParser } from "@/lib/api/sse";
import { FAKE_CITATIONS } from "@/lib/fake/data";
import { ChatScreen } from "@/components/chat/ChatScreen";
import { FAILURES } from "@/lib/copy";

const ce = { citations: FAKE_CITATIONS, removed_count: 0, data_as_of: "2026-08-31", credit: "c", notice: "n" };

describe("toSegments", () => {
  it("hides markers before the citations event", () => {
    const segs = toSegments("a [S1] b", null);
    expect(segs.every((s) => s.type === "text")).toBe(true);
  });
  it("drops markers whose citation was removed", () => {
    const segs = toSegments("a [S1] b [S5]", ce);
    expect(segs.filter((s) => s.type === "cite")).toHaveLength(1);
  });
});

describe("applyEvent", () => {
  it("ignores a second citations event", () => {
    let s = applyEvent(newAnswer("q"), { event: "citations", data: ce });
    s = applyEvent(s, { event: "citations", data: { ...ce, citations: [] } });
    expect(s.citations?.citations).toHaveLength(2);
  });
  it("maps error codes to failure screens", () => {
    const e = (code: never) => failureFor({ code, message: "", request_id: "" });
    expect(e("quota_exceeded" as never)).toBe("usageLimit");
    expect(e("out_of_scope" as never)).toBe("outsideCoverage");
    expect(e("not_found_in_dataset" as never)).toBe("notFound");
    expect(e("internal_error" as never)).toBe("serviceError");
  });
  it("a refusal writes nothing", () => {
    const s = applyEvent(newAnswer("q"), { event: "done", data: { message_id: null, from_cache: false, refused: true } });
    expect(s.failure).toBe("notFound");
  });
});

describe("sse parser", () => {
  it("handles frames split across chunks", () => {
    const p = createSseParser();
    expect(p('event: token\ndata: {"te')).toEqual([]);
    expect(p('xt":"hi"}\n\n')).toEqual([{ event: "token", data: { text: "hi" } }]);
  });
});

describe("ChatScreen (fake mode)", () => {
  it("shows one tick for verified and a warning for partly, plus notices", async () => {
    render(<ChatScreen />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "section 420" } });
    fireEvent.click(screen.getByText("Ask"));
    await waitFor(() => expect(screen.getAllByText(/Record found in dataset/).length).toBeGreaterThan(0));
    const marks = Array.from(document.querySelectorAll("[data-mark]")).map((e) => e.getAttribute("data-mark"));
    expect(marks).toContain("tick");
    expect(marks).toContain("warning");
    expect(screen.getAllByText(/CC BY 4.0/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Data as of/).length).toBeGreaterThan(0);
  });
  it("shows the exact outside-coverage text", async () => {
    render(<ChatScreen />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "highcourt matter" } });
    fireEvent.click(screen.getByText("Ask"));
    await waitFor(() => expect(screen.getByText(FAILURES.outsideCoverage.body)).toBeInTheDocument());
  });
});
