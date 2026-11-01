// Turns raw SSE text into typed events. Pure: no network, so it is easy to test.
import type { StreamEvent } from "./types";

const KNOWN = new Set(["token", "citations", "done", "error"]);

// Feed it chunks as they arrive; it keeps the unfinished tail between calls.
export function createSseParser() {
  let buffer = "";
  return function push(chunk: string): StreamEvent[] {
    buffer += chunk.replace(/\r\n/g, "\n");
    const out: StreamEvent[] = [];
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (!KNOWN.has(event) || data.length === 0) continue;
      try {
        out.push({ event, data: JSON.parse(data.join("\n")) } as StreamEvent);
      } catch {
        // A malformed frame is dropped rather than shown.
      }
    }
    return out;
  };
}
