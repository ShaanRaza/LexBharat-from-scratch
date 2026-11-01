import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { copy } from "@/lib/copy";
import type { Citation } from "@/lib/types";
import { citationState } from "@/lib/citations";
import { CitationChip } from "./CitationChip";
import { MessageView } from "./MessageView";
import type { ChatMessage } from "@/hooks/chatState";

describe("CitationChip", () => {
  it("shows the tick (Record found in dataset) for a verified citation", () => {
    render(<CitationChip sourceId="S1" state="verified" />);
    expect(screen.getByLabelText(copy.verified)).toBeInTheDocument();
  });

  it("shows a warning, not a tick, for a partly supported citation", () => {
    render(<CitationChip sourceId="S2" state="partial" />);
    expect(screen.queryByLabelText(copy.verified)).toBeNull();
    expect(screen.getByLabelText(copy.partly)).toBeInTheDocument();
  });

  it("shows NO tick for an unverified citation", () => {
    render(<CitationChip sourceId="S3" state="unverified" />);
    expect(screen.queryByLabelText(copy.verified)).toBeNull();
    expect(screen.getByLabelText(copy.notVerified)).toBeInTheDocument();
  });
});

describe("ticks on a whole answer (per citation, never one badge)", () => {
  const cite = (id: string, status: Citation["status"]): Citation => ({
    source_id: id, record_id: `r-${id}`, title: `Title ${id}`, citation_string: null, url: null,
    status, status_label: null, kind: null, anchor: null, act_slug: null, section: null, act_status: null,
  });
  const message: ChatMessage = {
    id: "a1", role: "assistant", text: "One [S1] two [S2] three [S3].", status: "done",
    citations: [cite("S1", "verified"), cite("S2", "partly"), cite("S3", "unverified")],
    dataAsOf: null, removedCount: 0, note: null, outcome: "answered", failure: null,
  };

  it("renders exactly one tick-state for each source, matching its own state", () => {
    const { container } = render(<MessageView message={message} />);
    const states = [...container.querySelectorAll("[data-state]")].map((n) => n.getAttribute("data-state"));
    // Each source appears in the text and in its source card: 2 chips each.
    expect(states.filter((s) => s === "verified")).toHaveLength(2);
    expect(states.filter((s) => s === "partial")).toHaveLength(2);
    expect(states.filter((s) => s === "unverified")).toHaveLength(2);
    expect(message.citations!.map(citationState)).toEqual(["verified", "partial", "unverified"]);
  });

  it("shows no citation chips at all while citations have not arrived", () => {
    const streaming: ChatMessage = { ...message, status: "streaming", citations: null };
    const { container } = render(<MessageView message={streaming} />);
    expect(container.querySelectorAll("[data-state]")).toHaveLength(0);
    expect(container.textContent).not.toContain("[S1]");
  });
});
