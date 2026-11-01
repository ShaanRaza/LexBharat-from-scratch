// Defence in depth: the server already returns questions only, but the browser keeps
// only short, citation-free questions too, so a bad reply can never put a citation-like
// string on screen. Pure, no styling.
const MARKER = /\[[^\]]*\]|［[^］]*］|\(\s*S\s*\d+[^)]*\)|\bS\s*[1-8]\b/i;
const QUOTES = /["“”‘’`]/;
const STARTS = /^(what|why|how|when|where|which|who|whom|whose|is|are|was|were|can|could|does|do|did|should|would|will|may|might|has|have|had|must|shall)\b/i;

export function keepQuestions(list: unknown, limit = 3): string[] {
  if (!Array.isArray(list)) return [];
  const out: string[] = [];
  for (const raw of list) {
    if (typeof raw !== "string") continue;
    const q = raw.replace(/\s+/g, " ").trim();
    if (!q || q.length > 200) continue;
    if (!q.endsWith("?") || q.split("?").length !== 2) continue;
    if (!STARTS.test(q) || MARKER.test(q) || QUOTES.test(q)) continue;
    if (!out.some((x) => x.toLowerCase() === q.toLowerCase())) out.push(q);
    if (out.length === limit) break;
  }
  return out;
}
