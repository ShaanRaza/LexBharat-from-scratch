"use client";
import { useEffect, useState } from "react";
import { useApiData } from "@/hooks/useApiData";
import { getApi } from "@/lib/api";
import { config } from "@/lib/config";
import { CaseView } from "./CaseView";
import { FailureNotice } from "./FailureNotice";

/** Loads a judgment (login needed) and jumps to the #p<n> paragraph. */
export function CaseScreen({ id }: { id: string }) {
  const loaded = useApiData(() => getApi().getCase(id), id);
  const [hash, setHash] = useState<string | null>(null);

  useEffect(() => {
    const read = () => setHash(window.location.hash.slice(1) || null);
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);

  // Content arrives after the page loads, so scroll to the paragraph ourselves.
  const ready = loaded.status === "ready";
  useEffect(() => {
    if (ready && hash) document.getElementById(hash)?.scrollIntoView?.({ block: "center" });
  }, [ready, hash]);

  if (loaded.status === "loading") return <p className="p-6 text-small text-muted">Loading...</p>;
  if (loaded.status === "error") {
    return (
      <div className="mx-auto w-full max-w-reading px-gutter py-8">
        <FailureNotice kind="service_error" requestId={loaded.error.requestId} />
      </div>
    );
  }
  return <CaseView record={loaded.data} highlight={hash} isSample={config.useFakeApi} />;
}
