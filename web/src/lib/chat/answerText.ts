// Turns a finished, verified answer into plain text for Copy and Export. No styling and
// no model: it only arranges what the server sent in the single citations event.
// A citation string is copied EXACTLY as recorded, never reformatted or retyped. The case
// title is never used (it holds party names, CLAUDE.md section 6).
import { markFor, meaningFor } from "@/lib/citation";
import { CITATION_AS_RECORDED, SOURCES_HEADING, UNVERIFIED_NOTE } from "@/lib/copy";
import { citationName, isShown, type AnswerState } from "@/lib/chat/state";

export function answerToText(a: AnswerState): string | null {
  const ce = a.citations;
  if (!ce || a.failure || !a.text) return null; // nothing verified yet: nothing to copy
  const lines: string[] = [a.question, "", a.text.trim()];
  if (ce.removed_count > 0) lines.push("", UNVERIFIED_NOTE);
  const shown = ce.citations.filter(isShown);
  if (shown.length) {
    lines.push("", SOURCES_HEADING);
    for (const c of shown) {
      const parts = [`[${c.source_id}] ${citationName(c)}`];
      if (c.citation_string) parts.push(`${c.citation_string} (${CITATION_AS_RECORDED})`);
      parts.push(meaningFor(markFor(c.status), ce.data_as_of));
      if (c.url) parts.push(c.url);
      lines.push(parts.join(" | "));
    }
  }
  lines.push("", ce.notice, `Data as of ${ce.data_as_of}.`, ce.credit);
  return lines.join("\n");
}
