"use client";
import { useEffect, useState } from "react";
import { getCoverage } from "@/lib/api/client";
import type { CoverageOut } from "@/lib/api/types";

// The coverage statement, loaded from the API. null until loaded, or if the call fails
// (the screens then show their category-free fallback). No styling here.
export function useCoverage(enabled = true): CoverageOut | null {
  const [cov, setCov] = useState<CoverageOut | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    getCoverage().then(
      (c) => live && setCov(c),
      () => {},
    );
    return () => {
      live = false;
    };
  }, [enabled]);
  return cov;
}
