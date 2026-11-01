import { describe, expect, it } from "vitest";
import { citationFromEvent, citationFromHistory } from "./mappers";
import { readSse, toStreamEvent } from "./sse";

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      chunks.forEach((x) => c.enqueue(enc.encode(x)));
      c.close();
    },
  });
}

async function collect(body: ReadableStream<Uint8Array>) {
  const out = [];
  for await (const m of readSse(body)) out.push(m);
  return out;
}

describe("readSse", () => {
  it("splits messages even when chunks are cut mid-line", async () => {
    const msgs = await collect(streamOf('event: text\ndata: {"te', 'xt":"Hi "}\n\nevent: done\ndata: {}\n\n'));
    expect(msgs).toEqual([
      { event: "text", data: '{"text":"Hi "}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("handles CRLF line ends and ignores comments", async () => {
    const msgs = await collect(streamOf(': keep-alive\r\n\r\nevent: text\r\ndata: {"text":"a"}\r\n\r\n'));
    expect(msgs).toEqual([{ event: "text", data: '{"text":"a"}' }]);
  });
});

describe("toStreamEvent", () => {
  it("maps the API's event kinds (token = answer text)", () => {
    expect(toStreamEvent({ event: "token", data: '{"text":"x"}' })).toEqual({ type: "text", text: "x" });
    expect(toStreamEvent({ event: "done", data: '{"message_id":"m","request_id":"r","answers_left":3}' })).toEqual({
      type: "done", messageId: "m", requestId: "r", answersLeft: 3,
    });
    expect(
      toStreamEvent({ event: "error", data: '{"error":{"code":"quota_exceeded","message":"m","request_id":"r"}}' }),
    ).toEqual({ type: "error", code: "quota_exceeded", message: "m", requestId: "r" });
  });

  it("reads the citations event exactly as the API sends it", () => {
    const data = JSON.stringify({
      citations: [{ source_id: "S1", record_id: "r1", title: "T", citation: "[2019] X", citation_label: "as recorded in the dataset", url: "https://x", status: "verified", status_label: "Record found in dataset" }],
      removed_count: 1,
      unverified_note: "One authority could not be verified and was removed.",
      outcome: "answered",
      provenance: { data_as_of: "2026-08-31", snapshot_version: "v", credit: "c", notice: "n" },
    });
    expect(toStreamEvent({ event: "citations", data })).toMatchObject({
      type: "citations", outcome: "answered", dataAsOf: "2026-08-31", removedCount: 1,
      note: "One authority could not be verified and was removed.",
      citations: [{ source_id: "S1", status: "verified", citation_string: "[2019] X", url: "https://x" }],
    });
  });

  it("ignores unknown events and bad JSON", () => {
    expect(toStreamEvent({ event: "mystery", data: "{}" })).toBeNull();
    expect(toStreamEvent({ event: "token", data: "not json" })).toBeNull();
  });
});

describe("citation status from the wire", () => {
  const raw = { source_id: "S1", record_id: "r1", status: "verified" };
  it("only the exact word 'verified' becomes a tick-status", () => {
    expect(citationFromEvent(raw)?.status).toBe("verified");
    expect(citationFromEvent({ ...raw, status: "partly" })?.status).toBe("partly");
    expect(citationFromEvent({ ...raw, status: "VERIFIED" })?.status).toBe("unverified");
    expect(citationFromEvent({ ...raw, status: true })?.status).toBe("unverified");
    expect(citationFromEvent({ ...raw, status: undefined })?.status).toBe("unverified");
  });

  it("rejects entries without ids", () => {
    expect(citationFromEvent({ status: "verified" })).toBeNull();
    expect(citationFromEvent(null)).toBeNull();
  });

  it("saved history: tick needs verified === true AND support 'supports'", () => {
    const h = (verified: unknown, support: unknown) => citationFromHistory({ source_id: "S1", record_id: "r", verified, support })?.status;
    expect(h(true, "supports")).toBe("verified");
    expect(h(true, "partly")).toBe("partly");
    expect(h(true, "does_not_support")).toBe("unverified");
    expect(h(true, null)).toBe("unverified");
    expect(h(false, "supports")).toBe("unverified");
    expect(h("true", "supports")).toBe("unverified");
  });
});
