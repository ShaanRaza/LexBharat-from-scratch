import { render, screen } from "@testing-library/react";
import { ProgressPanel } from "@/components/chat/ProgressPanel";
import { createSseParser } from "@/lib/api/sse";
import { askQuestion } from "@/lib/api/client";
import { applyEvent, newAnswer, toSegments } from "@/lib/chat/state";
import type { StepEventData, StreamEvent } from "@/lib/api/types";

const step = (s: StepEventData["step"], found: number | null = null, kept: number | null = null): StreamEvent => ({
  event: "step",
  data: { step: s, found, kept },
});

describe("progress panel", () => {
  it("shows step names and counts only", () => {
    render(
      <ProgressPanel
        steps={[
          { step: "understanding", found: null, kept: null },
          { step: "searching", found: null, kept: null },
          { step: "checking", found: 23, kept: null },
          { step: "writing", found: 23, kept: 8 },
        ]}
      />,
    );
    expect(screen.getByText("Understanding your question")).toBeInTheDocument();
    expect(screen.getByText("23 passages found, 8 kept")).toBeInTheDocument();
  });

  it("cannot show a case name, citation or id even if the wire sent one", () => {
    // A hostile or buggy server adds extra fields to a step event.
    const evil = {
      step: "searching",
      found: null,
      kept: null,
      case: "Zorblax versus Quuxington",
      citation: "(1987) 41 XYZ 777",
      record_id: "rec-zq-00917",
    } as unknown as StepEventData;
    const { container } = render(<ProgressPanel steps={[evil]} />);
    for (const leak of ["Zorblax", "XYZ 777", "rec-zq-00917"]) {
      expect(container.textContent).not.toContain(leak);
    }
  });

  it("renders nothing before the first step", () => {
    const { container } = render(<ProgressPanel steps={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("step events in the stream", () => {
  it("the SSE parser accepts step events", () => {
    const events = createSseParser()('event: step\ndata: {"step":"searching","found":null,"kept":null}\n\n');
    expect(events).toEqual([step("searching")]);
  });

  it("the reducer collects steps, and an error clears them", () => {
    let s = newAnswer("q");
    s = applyEvent(s, step("understanding"));
    s = applyEvent(s, step("checking", 23));
    expect(s.steps.map((x) => x.step)).toEqual(["understanding", "checking"]);
    s = applyEvent(s, { event: "error", data: { code: "service_unavailable", message: "x", request_id: "r" } });
    expect(s.steps).toEqual([]);
  });

  it("no citation is visible while the answer is still being checked", () => {
    let s = newAnswer("q");
    s = applyEvent(s, step("verifying"));
    s = applyEvent(s, { event: "token", data: { text: "A point [S1]." } });
    expect(toSegments(s.text, s.citations).some((x) => x.type === "cite")).toBe(false);
  });

  it("fake stream order: steps, then tokens, then ONE citations event, then done", async () => {
    const names: string[] = [];
    for await (const ev of askQuestion("c", "bail")) names.push(ev.event);
    const firstToken = names.indexOf("token");
    expect(names.slice(0, firstToken).every((n) => n === "step")).toBe(true);
    expect(names.filter((n) => n === "citations")).toHaveLength(1);
    expect(names.indexOf("citations")).toBeGreaterThan(names.lastIndexOf("token"));
    expect(names.at(-1)).toBe("done");
    expect(names.slice(firstToken).includes("step")).toBe(false);
  });
});
