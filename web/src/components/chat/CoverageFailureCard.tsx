"use client";
import Link from "next/link";
import { useCoverage } from "@/lib/chat/useCoverage";
import type { FailureKind } from "@/lib/chat/state";
import { FailureCard } from "./FailureCard";

// The two "outside what we hold" screens. The words come from the API's coverage
// statement (one source), with a category-free fallback if it cannot be loaded.
export function CoverageFailureCard({ kind }: { kind: "outsideCoverage" | "notInDataset" }) {
  const cov = useCoverage();
  const body = cov ? (kind === "notInDataset" ? cov.not_in_dataset_message : cov.sentence) : undefined;
  return (
    <div className="flex flex-col gap-2">
      <FailureCard kind={kind as FailureKind} body={body} />
      <Link href="/coverage" className="text-small font-semibold text-accent underline">
        What the dataset covers
      </Link>
    </div>
  );
}
