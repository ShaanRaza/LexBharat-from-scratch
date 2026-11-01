"use client";
import { FailureNotice } from "@/components/FailureNotice";

// Shown when a page crashes: the "service error" screen with a retry button.
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto w-full max-w-reading px-gutter py-8">
      <FailureNotice kind="service_error" requestId={error.digest ?? null} onRetry={reset} />
    </div>
  );
}
