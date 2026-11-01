// "Matter" or "Project": a label, not a second feature (PRD-v2 O11, decision A47).
// Advocates get "matter", students get "project"; everyone else gets "matter". The word
// is chosen when the thing is created and stored as `kind`, then shown from `kind`.
import { MATTER_WORDS } from "@/lib/copy";
import type { MatterKind } from "@/lib/api/types";

export function wordsFor(kind: MatterKind) {
  return MATTER_WORDS[kind];
}

export function defaultKind(role: string | null | undefined): MatterKind {
  return role === "student" ? "project" : "matter";
}
