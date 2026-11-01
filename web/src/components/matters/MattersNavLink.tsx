"use client";
import Link from "next/link";
import { useDefaultKind } from "@/lib/matters/useRole";
import { wordsFor } from "@/lib/matters/label";

// The top-bar link says "Matters" for an advocate and "Projects" for a student.
export function MattersNavLink() {
  const kind = useDefaultKind();
  return (
    <Link href="/matters" className="text-ink-soft hover:text-ink">
      {wordsFor(kind).many}
    </Link>
  );
}
