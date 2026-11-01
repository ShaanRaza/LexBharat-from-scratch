// Pure rule for what mark a citation gets. UI-free so it can be tested on its own.
// CLAUDE.md section 5: the tick appears ONLY for status "verified". "partly" gets a
// warning mark. Anything else gets no mark (the server removes failed citations;
// if one ever reaches us we must not tick it).
export type CitationStatus = "verified" | "partly" | string;
export type Mark = "tick" | "warning" | "unchecked" | "none";

export function markFor(status: CitationStatus): Mark {
  if (status === "verified") return "tick";
  if (status === "partly") return "warning";
  if (status === "unchecked") return "unchecked";
  return "none";
}
