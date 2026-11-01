// Maps API error codes and stream outcomes to the failure screens
// (docs/UX-COPY.md "Failure and edge states"). Pure logic, no React.
import type { Outcome } from "./types";

export type FailureKind =
  | "not_found" // no relevant results; no answer was written
  | "out_of_scope" // outside v1 coverage
  | "usage_limit" // monthly answers used up
  | "provider_failed" // sources found, writer failed
  | "service_error"; // anything else went wrong

export interface Failure {
  kind: FailureKind;
  requestId: string | null;
}

export function failureFromError(code: string, requestId: string | null): Failure {
  const kind: FailureKind =
    code === "quota_exceeded"
      ? "usage_limit"
      : code === "out_of_scope"
        ? "out_of_scope"
        : code === "not_found_answer"
          ? "not_found"
          : "service_error";
  return { kind, requestId };
}

/** `answered` is not a failure, so it returns null. */
export function failureFromOutcome(outcome: Outcome): Failure | null {
  if (outcome === "not_found") return { kind: "not_found", requestId: null };
  if (outcome === "out_of_scope") return { kind: "out_of_scope", requestId: null };
  if (outcome === "provider_failed") return { kind: "provider_failed", requestId: null };
  return null;
}
