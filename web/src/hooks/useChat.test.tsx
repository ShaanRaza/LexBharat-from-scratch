import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ApiClient } from "@/lib/api";
import { createFakeApi } from "@/lib/fake/fakeApi";
import { sampleCitations } from "@/lib/fake/sampleData";
import type { StreamEvent } from "@/lib/types";
import { useChat } from "./useChat";

// A client whose stream we script by hand, to test the hook's rules.
function scripted(events: StreamEvent[]): ApiClient {
  const base = createFakeApi(0);
  return {
    ...base,
    async *streamMessage() {
      for (const e of events) yield e;
    },
  };
}

const text = (t: string): StreamEvent => ({ type: "text", text: t });
const citations = (list = sampleCitations): StreamEvent => ({
  type: "citations", citations: list, dataAsOf: "2026-08-31", removedCount: 0,
});
const done = (outcome: "answered" | "not_found" = "answered"): StreamEvent => ({
  type: "done", messageId: "m", outcome, answersLeft: 7,
});

const lastMessage = (r: { current: ReturnType<typeof useChat> }) =>
  r.current.messages[r.current.messages.length - 1];

describe("useChat", () => {
  it("streams text first; citations stay null until the citations event", async () => {
    // Pause between events so we can look at the screen state in the middle.
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const api: ApiClient = {
      ...createFakeApi(0),
      async *streamMessage() {
        yield text("Bail is the rule [S1] ");
        await gate;
        yield citations();
        yield done();
      },
    };
    const { result } = renderHook(() => useChat({ api }));
    let sending!: Promise<void>;
    act(() => {
      sending = result.current.send("bail?");
    });
    await waitFor(() => expect(lastMessage(result).text).toContain("Bail is the rule"));
    expect(lastMessage(result).citations).toBeNull(); // nothing citation-shaped yet
    expect(result.current.busy).toBe(true);

    release();
    await act(async () => {
      await sending;
    });
    expect(lastMessage(result).citations).toHaveLength(3);
    expect(lastMessage(result).status).toBe("done");
    expect(result.current.busy).toBe(false);
    expect(result.current.answersLeft).toBe(7);
  });

  it("keeps the verified flag exactly as the API sent it (no tick promoted)", async () => {
    const { result } = renderHook(() => useChat({ api: scripted([text("x"), citations(), done()]) }));
    await act(async () => {
      await result.current.send("q");
    });
    const flags = lastMessage(result).citations!.map((c) => [c.source_id, c.verified]);
    expect(flags).toEqual([["S1", true], ["S2", true], ["S3", false]]);
  });

  it("not-found outcome shows the not-found failure and no text", async () => {
    const { result } = renderHook(() => useChat({ api: scripted([citations([]), done("not_found")]) }));
    await act(async () => {
      await result.current.send("q");
    });
    expect(lastMessage(result).failure?.kind).toBe("not_found");
    expect(lastMessage(result).text).toBe("");
  });

  it("quota_exceeded error becomes the usage-limit screen", async () => {
    const api = scripted([{ type: "error", code: "quota_exceeded", message: "", requestId: "r9" }]);
    const { result } = renderHook(() => useChat({ api }));
    await act(async () => {
      await result.current.send("q");
    });
    expect(lastMessage(result).failure).toEqual({ kind: "usage_limit", requestId: "r9" });
  });

  it("an error mid-answer drops the partial text and any citations", async () => {
    const api = scripted([text("half an ans"), { type: "error", code: "internal_error", message: "", requestId: null }]);
    const { result } = renderHook(() => useChat({ api }));
    await act(async () => {
      await result.current.send("q");
    });
    const m = lastMessage(result);
    expect(m.failure?.kind).toBe("service_error");
    expect(m.text).toBe("");
    expect(m.citations).toBeNull();
  });

  it("a stream that stops without 'done' is a service error, not a silent success", async () => {
    const { result } = renderHook(() => useChat({ api: scripted([text("partial")]) }));
    await act(async () => {
      await result.current.send("q");
    });
    expect(lastMessage(result).failure?.kind).toBe("service_error");
    expect(lastMessage(result).status).toBe("failed");
  });

  it("retry replaces the failed turn with a new one", async () => {
    let calls = 0;
    const api: ApiClient = {
      ...createFakeApi(0),
      async *streamMessage() {
        calls += 1;
        if (calls === 1) yield { type: "error", code: "internal_error", message: "", requestId: null };
        else {
          yield text("ok");
          yield citations();
          yield done();
        }
      },
    };
    const { result } = renderHook(() => useChat({ api }));
    await act(async () => {
      await result.current.send("q");
    });
    await act(async () => {
      await result.current.retry();
    });
    expect(result.current.messages).toHaveLength(2); // one question + one answer
    expect(lastMessage(result).text).toBe("ok");
  });
});

describe("fake API stream order", () => {
  it("sends all text before the single citations event, then done", async () => {
    const api = createFakeApi(0);
    const kinds: string[] = [];
    for await (const e of api.streamMessage("c", "bail question")) kinds.push(e.type);
    expect(kinds.filter((k) => k === "citations")).toHaveLength(1);
    expect(kinds.indexOf("citations")).toBe(kinds.lastIndexOf("text") + 1);
    expect(kinds[kinds.length - 1]).toBe("done");
  });
});
