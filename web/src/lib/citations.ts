// Pure rules for what a citation looks like on screen. No React here, so the
// trust logic can be tested on its own (and never depends on styling).
import type { Citation } from "./types";

/**
 * - "verified"   -> tick. ONLY when the API's status is exactly "verified".
 * - "partial"    -> warning mark ("partly").
 * - "unverified" -> no tick, ever. Anything else, including a missing status.
 */
export type CitationState = "verified" | "partial" | "unverified";

export function citationState(c: Pick<Citation, "status">): CitationState {
  // Exact match on purpose: a truthy-but-different value is NOT a tick.
  if (c.status === "verified") return "verified";
  if (c.status === "partly") return "partial";
  return "unverified";
}

/** Where the in-site link for a citation goes (judgment page or Act page). */
export function citationHref(c: Citation): string | null {
  if (c.kind === "judgment") {
    const anchor = c.anchor ? `#${c.anchor}` : "";
    return `/cases/${encodeURIComponent(c.record_id)}${anchor}`;
  }
  if (c.kind === "act" && c.act_slug && c.section) {
    return `/acts/${encodeURIComponent(c.act_slug)}/${encodeURIComponent(c.section)}`;
  }
  // Unknown kind: no in-site link rather than a wrong one.
  return null;
}

export type AnswerSegment =
  | { type: "text"; text: string }
  | { type: "cite"; sourceId: string };

const MARKER = /\[(S[1-8])\]/g;
// A marker that is still arriving, e.g. "[S" or "[S3" at the very end.
const PARTIAL_MARKER = /\[S?[1-8]?$/;

/**
 * Turns answer text into text + citation markers.
 *
 * Rule from docs/API.md: nothing citation-shaped may be shown before the one
 * `citations` event. So until it arrives (`knownIds` is null), every [S1]
 * marker (and a half-arrived "[S") is dropped; after it, a marker becomes a
 * chip only if that source ID is in the checked set. A citation therefore can
 * never appear and then vanish.
 */
export function segmentAnswer(
  text: string,
  knownIds: ReadonlySet<string> | null,
): AnswerSegment[] {
  const segments: AnswerSegment[] = [];
  let source = text;
  if (knownIds === null) source = source.replace(PARTIAL_MARKER, "");
  let last = 0;
  for (const m of source.matchAll(MARKER)) {
    const start = m.index ?? 0;
    if (start > last) segments.push({ type: "text", text: source.slice(last, start) });
    if (knownIds !== null && knownIds.has(m[1])) {
      segments.push({ type: "cite", sourceId: m[1] });
    }
    last = start + m[0].length;
  }
  if (last < source.length) segments.push({ type: "text", text: source.slice(last) });
  return segments;
}
